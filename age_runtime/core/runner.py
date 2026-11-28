"""Minimal deterministic scenario runner; standard library only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from age_runtime.core.actors import validate_actors, evaluate
from age_runtime.core.events import validate_dependent_events, resolve_dependent_events
from age_runtime.core.economy import validate_projects, resolve_projects, validate_capacity_actions
from age_runtime.core.observations import validate_views, observe
from age_runtime.core.actions import validate_catalog, register_request, validate_review_capacity, resolve_reviews, validate_service_rule, validate_civic_rules, validate_transfers, validate_agreements, agreement_actions, resolve_agreements

from age_runtime.core import negotiation, communications, diplomacy, establishment, event_generator, phase_memory, reserve_accounting, stock_accounting

CHECKPOINT_VERSION = 2
GAME_LENGTHS = {"Short": 6, "Standard": 12, "Extended": 24}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()

def integer(value):
    return type(value) is int

def validate(s):
    if not isinstance(s, dict):
        raise ValueError("scenario must be an object")
    required = {"version", "id", "turn_minutes", "end_minute", "initial", "events", "constraints"}
    optional = {"actors", "action_catalog", "administrative_reviews_per_turn", "service_restoration", "community_assistance", "civic_agreement", "assistance_capacity", "dependent_events", "economy_projects", "capacity_actions", "model_factions", "game_length", "resource_transfers", "agreements", "dynamic_negotiation", "funding_reserves", "material_communications", "communication_propositions", "runtime_propositions", "communication_delay_minutes", "diplomatic_history", "strategic_establishment", "permission_terms", "event_templates", "phase_memory", "project_dependencies", "project_permissions", "reserve_accounts", "reserve_actions", "stock_accounts", "stock_actions", "stock_flows"}
    if required - s.keys():
        raise ValueError("missing scenario fields: " + ", ".join(sorted(required - s.keys())))
    if s.keys() - required - optional:
        raise ValueError("unknown scenario fields: " + ", ".join(sorted(s.keys() - required - optional)))
    if type(s.get("version")) is not int or s["version"] != 1 or not isinstance(s.get("id"), str) or not s["id"].strip():
        raise ValueError("invalid scenario identity")
    if not integer(s["turn_minutes"]) or s["turn_minutes"] <= 0:
        raise ValueError("invalid turn duration")
    if not integer(s["end_minute"]) or s["end_minute"] <= 0:
        raise ValueError("invalid horizon")
    if "game_length" in s and (not isinstance(s["game_length"], str) or s["game_length"] not in GAME_LENGTHS):
        raise ValueError("invalid game length")
    initial = s["initial"]
    if not isinstance(initial, dict) or not all(integer(v) for v in initial.values()):
        raise ValueError("initial values must be integers")
    validate_actors(s)
    validate_views(s)
    validate_catalog(s)
    validate_review_capacity(s)
    if not isinstance(s["events"], list) or not isinstance(s["constraints"], list):
        raise ValueError("events and constraints must be arrays")
    ids = set()
    for e in s["events"]:
        if not isinstance(e, dict) or set(e) != {"id", "minute", "key", "delta"}:
            raise ValueError("invalid event fields")
        if not isinstance(e["id"], str) or e["id"] in ids:
            raise ValueError("duplicate or invalid event ID")
        ids.add(e["id"])
        if not integer(e["minute"]) or not 0 < e["minute"] <= s["end_minute"]:
            raise ValueError("event outside horizon")
        if e["key"] not in initial or not integer(e["delta"]):
            raise ValueError("invalid event update")
    for c in s["constraints"]:
        if not isinstance(c, dict) or set(c) != {"minute", "key", "equals"}:
            raise ValueError("invalid constraint fields")
        if c["key"] not in initial or not integer(c["equals"]):
            raise ValueError("invalid constraint")
        if not integer(c["minute"]) or not 0 < c["minute"] <= s["end_minute"]:
            raise ValueError("constraint outside horizon")
    validate_service_rule(s)
    validate_civic_rules(s)
    validate_dependent_events(s)
    validate_projects(s)
    validate_capacity_actions(s)
    validate_transfers(s)
    validate_agreements(s)
    negotiation.validate(s)
    communications.validate(s)
    establishment.validate(s)
    event_generator.validate(s)
    phase_memory.validate(s)
    reserve_accounting.validate(s)
    stock_accounting.validate(s)
    factions = s.get("model_factions", [])
    if not isinstance(factions, list) or any(not isinstance(a, str) or a not in s.get("actors", {}) for a in factions) or len(set(factions)) != len(factions):
        raise ValueError("invalid model faction IDs")
    if factions and not (s.get("economy_projects") or s.get("agreements") or s.get("reserve_accounts") or s.get("stock_accounts")):
        raise ValueError("model factions require reviewed civilian projects or institutional commitments")
    for actor in factions:
        if any(name not in (s.get("capacity_actions", {}).keys() | s.get("resource_transfers", {}).keys() | s.get("reserve_actions", {}).keys() | s.get("stock_actions", {}).keys() | agreement_actions(s)) for name, spec in s.get("action_catalog", {}).items() if actor in spec["actors"]):
            raise ValueError("model factions may select only supported capacity, transfer or consent actions")

def initialize(s):
    validate(s)
    state = {"checkpoint_version": CHECKPOINT_VERSION, "scenario": digest(s), "minute": 0, "turn": 0,
            "values": copy.deepcopy(s["initial"]), "ledger": [], "checks": [],
            "actors": evaluate(s, s["initial"]), "requests": []}
    if "dependent_events" in s:
        state["background_events"] = []
    if "economy_projects" in s:
        state["project_results"] = []
    if "agreements" in s:
        state["agreement_results"] = []
    if s.get("dynamic_negotiation"):
        state["negotiations"] = {}
    if "event_templates" in s:
        state["generated_events"] = {}
    return state

def check_identity(s, state):
    if not isinstance(state, dict) or type(state.get("checkpoint_version")) is not int or state["checkpoint_version"] != CHECKPOINT_VERSION:
        raise ValueError("unsupported checkpoint version; recreate the prototype session")
    if state.get("scenario") != digest(s):
        raise ValueError("scenario revision mismatch")

def advance(s, state):
    validate(s)
    check_identity(s, state)
    start = state["minute"]
    if start >= s["end_minute"]:
        return copy.deepcopy(state)
    missing = set(s.get("model_factions", [])) - {r["actor"] for r in state["requests"] if r["turn"] == state["turn"] and r.get("origin") == "model"}
    if missing:
        raise ValueError("model faction choices required before advancing")
    end = min(start + s["turn_minutes"], s["end_minute"])
    result = copy.deepcopy(state)
    times = sorted({x["minute"] for x in s["events"] + s["constraints"] + s.get("dependent_events", [])
                    if start < x["minute"] <= end} | {end})
    for minute in times:
        for event in s["events"]:
            if event["minute"] == minute:
                key = event["key"]
                result["values"][key] += event["delta"]
                result["ledger"].append({"id": event["id"], "minute": minute,
                    "key": key, "delta": event["delta"], "value": result["values"][key]})
        if minute == end:
            if s.get("reserve_accounts") or s.get("stock_accounts"):
                # Accounting requests adjudicate as one batch, not FIFO.
                reviewed = [r for r in result["requests"] if r["status"] == "validated_request"]
                for r in reviewed:
                    r.update(status="reviewed", reviewed_minute=end)
                reserve_accounting.resolve(s, result, end, reviewed)
                stock_accounting.resolve(s, result, end, reviewed)
            else:
                resolve_reviews(s, result, end)
            resolve_agreements(s, result, end)
            negotiation.resolve(s, result, end)
        resolve_dependent_events(s, result, minute)
        event_generator.resolve(s, result, minute)
        if minute == end:
            resolve_projects(s, result, minute)
        for check in s["constraints"]:
            if check["minute"] == minute:
                actual = result["values"][check["key"]]
                result["checks"].append({**check, "actual": actual,
                    "passed": actual == check["equals"]})
    result.update(minute=end, turn=state["turn"] + 1,
                  actors=evaluate(s, result["values"]))
    return result

def submit_request(s, state, actor_id, proposal):
    """Append an administrative request to a new checkpoint, without effects."""
    verify_checkpoint(s, state)
    if actor_id in s.get("model_factions", []):
        raise ValueError("model faction requires its own decision exchange")
    return _append_request(s, state, actor_id, proposal)

def commit_decision(s, state, actor_id, revision, decision_id, intent, action=None, *, negotiation_command=None):
    """Record a consequential commitment with one order, negotiation or abstention."""
    verify_checkpoint(s, state)
    if digest(state) != revision:
        raise ValueError("stale decision revision")
    result = _append_decision(s, state, actor_id, decision_id, intent, action, negotiation_command)
    verify_checkpoint(s, result)
    return result


def _append_decision(s, state, actor_id, decision_id, intent, action, negotiation_command=None):
    if "game_length" not in s:
        raise ValueError("scenario has no decision pacing target")
    if actor_id not in s.get("actors", {}) or actor_id in s.get("model_factions", []):
        raise ValueError("invalid player decision actor")
    if state["minute"] >= s["end_minute"]:
        raise ValueError("session ended")
    if not isinstance(decision_id, str) or not decision_id.strip() or len(decision_id) > 128:
        raise ValueError("invalid decision ID")
    if not isinstance(intent, str) or not intent.strip() or len(intent) > 2000:
        raise ValueError("invalid decision intent")
    if any(r.get("decision_id") == decision_id and r["actor"] == actor_id for r in state["requests"]):
        raise ValueError("duplicate decision ID")
    if negotiation_command is not None:
        if action is not None:
            raise ValueError("decision permits only one order or negotiation")
        result = _append_negotiation(s, state, actor_id, negotiation_command, "critical_decision")
    elif action is None:
        result = copy.deepcopy(state)
        result["requests"].append({"actor": actor_id, "action": None, "status": "abstained",
                                   "turn": state["turn"], "minute": state["minute"],
                                   "sequence": len(state["requests"]) + 1})
    else:
        result = _append_request(s, state, actor_id, {"action": action})
    result["requests"][-1].update(origin="critical_decision", decision_id=decision_id, intent=intent)
    return result


def _append_request(s, state, actor_id, proposal):
    record = register_request(s, state, actor_id, proposal)
    result = copy.deepcopy(state)
    record["sequence"] = len(result["requests"]) + 1
    result["requests"].append(record)
    return result

def _append_negotiation(s, state, actor, command, origin):
    result = copy.deepcopy(state)
    negotiation.apply(s, result, actor, command)
    result["requests"].append({"actor": actor, "action": None, "status": "negotiated",
        "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "origin": origin,
        "negotiation": copy.deepcopy(command)})
    return result


def negotiate(s, state, actor, revision, command):
    verify_checkpoint(s, state)
    if digest(state) != revision or actor in s.get("model_factions", []):
        raise ValueError("stale negotiation revision or invalid player")
    result = _append_negotiation(s, state, actor, command, "negotiation")
    verify_checkpoint(s, result)
    return result


def _append_model_choice(s, state, actor_id, action):
    if actor_id not in s.get("model_factions", []):
        raise ValueError("not a model faction")
    if state["minute"] >= s["end_minute"]:
        raise ValueError("session ended")
    if any(r["actor"] == actor_id and r["turn"] == state["turn"] and r.get("origin") not in ("communication", "assessment", "diplomatic_record") for r in state["requests"]):
        raise ValueError("faction already decided this turn")
    if isinstance(action, dict):
        return _append_negotiation(s, state, actor_id, action, "model")
    if action is None:
        result = copy.deepcopy(state)
        result["requests"].append({"actor": actor_id, "action": None, "status": "abstained",
                                   "turn": state["turn"], "minute": state["minute"],
                                   "sequence": len(state["requests"]) + 1, "origin": "model"})
    else:
        result = _append_request(s, state, actor_id, {"action": action})
        result["requests"][-1]["origin"] = "model"
    return result

def faction_packet(s, state, actor_id):
    verify_checkpoint(s, state)
    if actor_id not in s.get("model_factions", []):
        raise ValueError("not a model faction")
    if state["minute"] >= s["end_minute"]:
        raise ValueError("session ended")
    if any(r["actor"] == actor_id and r["turn"] == state["turn"] and r.get("origin") not in ("communication", "assessment", "diplomatic_record") for r in state["requests"]):
        raise ValueError("faction already decided this turn")
    body = {"actor": actor_id, "observation": observe(s, state, actor_id)}
    return {"packet_id": digest(body), **body}

def accept_faction_choice(s, state, actor_id, packet, response):
    if packet != faction_packet(s, state, actor_id):
        raise ValueError("stale or altered faction packet")
    if not isinstance(response, dict) or set(response) != {"packet_id", "action"} or response["packet_id"] != packet["packet_id"]:
        raise ValueError("invalid faction response")
    action = response["action"]
    if action is not None and not isinstance(action, dict) and (not isinstance(action, str) or action not in packet["observation"]["available_requests"]):
        raise ValueError("unsupported faction action")
    result = _append_model_choice(s, state, actor_id, action)
    verify_checkpoint(s, result)
    return result

def communicate(s, state, actor, revision, command):
    """Trusted referee routes actual authorized faction speech, not an order."""
    verify_checkpoint(s, state)
    if revision != digest(state):
        raise ValueError("stale communication revision")
    result = communications.append(s, state, actor, command)
    verify_checkpoint(s, result)
    return result


def assess_proposition(s, state, actor, revision, command):
    verify_checkpoint(s, state)
    if revision != digest(state):
        raise ValueError("stale assessment revision")
    result = communications.assess(s, state, actor, command)
    verify_checkpoint(s, result)
    return result


def record_diplomacy(s, state, actor, revision, command):
    verify_checkpoint(s, state)
    if revision != digest(state):
        raise ValueError("stale diplomatic revision")
    result = diplomacy.append(s, state, actor, command)
    verify_checkpoint(s, result)
    return result


def schedule_development(s, state, revision, command):
    verify_checkpoint(s, state)
    if revision != digest(state):
        raise ValueError("stale development revision")
    result = event_generator.append(s, state, command)
    verify_checkpoint(s, result)
    return result


def establish_context(s, state, revision, command):
    """Trusted referee only: establish bounded descriptive session context."""
    verify_checkpoint(s, state)
    if revision != digest(state):
        raise ValueError("stale establishment revision")
    result = establishment.append(s, state, command)
    verify_checkpoint(s, result)
    return result


def verify_checkpoint(s, state):
    expected = initialize(s)
    check_identity(s, state)
    if not integer(state.get("turn")) or not 0 <= state["turn"] <= (s["end_minute"] + s["turn_minutes"] - 1) // s["turn_minutes"]:
        raise ValueError("invalid checkpoint turn")
    records = state.get("requests")
    if not isinstance(records, list):
        raise ValueError("missing request ledger")
    index = 0
    for turn in range(state["turn"] + 1):
        while index < len(records):
            record = records[index]
            if not isinstance(record, dict) or not integer(record.get("turn")):
                raise ValueError("invalid request record")
            if record["turn"] != turn:
                break
            if record.get("origin") == "assessment":
                expected = communications.assess(s, expected, record["actor"],
                    {k: v for k, v in record["assessment"].items() if k != "report_evidence"})
            elif record.get("origin") == "diplomatic_record":
                expected = diplomacy.append(s, expected, record["actor"],
                    {k: v for k, v in record["diplomatic_record"].items() if k != "evidence"})
            elif record.get("origin") == "generated_development":
                expected = event_generator.append(s, expected, record["development"])
            elif record.get("origin") == "strategic_establishment":
                expected = establishment.append(s, expected, record["establishment"])
            elif record.get("origin") == "communication":
                expected = communications.append(s, expected, record["actor"], record["communication"])
            elif record.get("origin") == "model":
                expected = _append_model_choice(s, expected, record["actor"], record.get("negotiation", record["action"]))
            elif record.get("origin") == "negotiation":
                if record["actor"] in s.get("model_factions", []):
                    raise ValueError("model negotiation requires model origin")
                expected = _append_negotiation(s, expected, record["actor"], record["negotiation"], "negotiation")
            elif record.get("origin") == "critical_decision":
                expected = _append_decision(s, expected, record["actor"], record["decision_id"], record["intent"], record["action"], record.get("negotiation"))
            else:
                if record["actor"] in s.get("model_factions", []):
                    raise ValueError("model faction choice requires model origin")
                expected = _append_request(s, expected, record["actor"], {"action": record["action"]})
            index += 1
        if turn < state["turn"]:
            expected = advance(s, expected)
    if index != len(records) or digest(expected) != digest(state):
        raise ValueError("checkpoint differs from deterministic replay")

def save(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("scenario", type=Path)
    p.add_argument("checkpoint", type=Path, nargs="?")
    p.add_argument("--validate", action="store_true", help="Validate scenario without creating a checkpoint")
    p.add_argument("--turns", type=int, default=1)
    p.add_argument("--actor", help="Print only this actor’s observation; checkpoint remains referee-only")
    p.add_argument("--inspect", action="store_true", help="Read existing checkpoint without advancing or saving")
    p.add_argument("--request", help="Record a permitted administrative request before advancing; requires --actor")
    p.add_argument("--faction-packet", metavar="ACTOR", help="Read model faction observation without advancing")
    p.add_argument("--faction-choice", type=Path, help="Submit model response JSON for --actor without advancing")
    args = p.parse_args()
    if args.faction_packet is not None or args.faction_choice is not None:
        if args.validate or args.inspect or args.request is not None or args.checkpoint is None or not args.checkpoint.is_file():
            p.error("faction exchange requires an existing checkpoint and no other operation")
        if args.scenario.resolve() == args.checkpoint.resolve():
            p.error("scenario and checkpoint must be different files")
        if args.faction_packet is not None and (args.faction_choice is not None or args.actor is not None):
            p.error("choose a single faction exchange operation")
        if args.faction_choice is not None and args.actor is None:
            p.error("faction choice requires --actor")
        try:
            s = json.loads(args.scenario.read_text())
            state = json.loads(args.checkpoint.read_text())
            if args.faction_packet is not None:
                result = faction_packet(s, state, args.faction_packet)
            else:
                packet = faction_packet(s, state, args.actor)
                result_state = accept_faction_choice(s, state, args.actor, packet, json.loads(args.faction_choice.read_text()))
                save(args.checkpoint, result_state)
                result = observe(s, result_state, args.actor)
            print(json.dumps(result, indent=2))
            return 0
        except (ValueError, KeyError, TypeError, OSError) as exc:
            p.error(str(exc))
    if args.validate:
        if args.checkpoint is not None or args.actor is not None or args.request is not None or args.inspect:
            p.error("--validate is a scenario-only operation")
        try:
            s = json.loads(args.scenario.read_text())
            validate(s)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            p.error(str(exc))
        print(json.dumps({"scenario": s["id"], "valid": True, "digest": digest(s)}))
        return 0
    if args.checkpoint is None:
        p.error("checkpoint required unless --validate is used")
    if args.scenario.resolve() == args.checkpoint.resolve():
        p.error("scenario and checkpoint must be different files")
    if args.inspect and args.request is not None:
        p.error("--inspect cannot submit requests")
    if args.inspect and not args.checkpoint.is_file():
        p.error("--inspect requires an existing checkpoint")
    if args.request is not None and args.actor is None:
        p.error("--request requires --actor")
    if args.turns < 0:
        p.error("turns must be nonnegative")
    s = json.loads(args.scenario.read_text())
    state = initialize(s)
    if args.actor is not None and args.actor not in s.get("actors", {}):
        p.error("unknown actor")
    if args.checkpoint.exists():
        state = json.loads(args.checkpoint.read_text())
        verify_checkpoint(s, state)
    if args.request is not None:
        state = submit_request(s, state, args.actor, {"action": args.request})
    for _ in range(0 if args.inspect else args.turns):
        if state["minute"] >= s["end_minute"]:
            break
        state = advance(s, state)
    if not args.inspect:
        save(args.checkpoint, state)
    if args.actor is not None:
        print(json.dumps(observe(s, state, args.actor), indent=2))
        return 0  # do not leak private historical constraint status via exit code
    print(json.dumps(state, indent=2))
    return 0 if all(c["passed"] for c in state["checks"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
