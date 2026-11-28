"""Persistent NPC objectives and reviewed social adjudication.

Objectives are subjective commitments, never world facts or commands.
All changes use the existing establishment/replay history.
"""
import copy
import re
from age_runtime.core import dxd, dxd_conditions, dxd_modifiers

def initialize(state, rules):
    cfg = rules.get("npc_agency")
    if not cfg and not rules.get("npc_objective_continuity"):
        return
    state["npc_objectives"] = []
    if not cfg:
        return
    state["npc_social_tests"] = []
    for nid, npc in state["npcs"].items():
        npc["favor"] = cfg["favor"]["initial"][nid]

def source_record(state, npc, source):
    """Resolve a cited source to actor-owned evidence, not world truth."""
    if not isinstance(source, dict) or set(source) != {"kind", "id"}:
        return None
    kind, sid = source["kind"], source["id"]
    if kind == "claim" and type(sid) is int:
        return next((e for e in state.get("dialogue", []) if e["id"] == sid
                     and npc in (e["speaker"], e["listener"])), None)
    if kind in ("observation", "pattern", "expectation", "test", "activity", "social_test"):
        ledger = {"observation": "action_observations", "pattern": "behavioral_recognition",
                  "expectation": "npc_expectations", "test": "timed_detail_events",
                  "activity": "timed_detail_events", "social_test": "npc_social_tests"}[kind]
        for e in state.get(ledger, []):
            if e["id"] != sid:
                continue
            if kind == "social_test":
                if npc in (e["npc"], e["target"]):
                    return e
                continue
            if e["npc"] != npc:
                continue
            if kind == "expectation" and e["operation"] != "assess":
                continue
            if kind == "test" and (e["status"] != "completed" or "test" not in e):
                continue
            if kind == "activity" and e["status"] not in (
                    "completed", "interrupted", "cancelled", "prerequisite_unmet", "record_limit"):
                continue
            return e
    return None


def owned_source(state, npc, source):
    return source_record(state, npc, source) is not None


def objective_context(state, goal):
    """Retain initial and latest decision evidence alongside the objective.

    Activity status is live, not a snapshot of the historical decision.
    Never expose another actor's private reaction or testimony provenance.
    """
    npc = goal["npc"]
    refs = goal["sources"] + goal.get("latest_review", {}).get("sources", [])
    selected = []
    for ref in refs:
        if any(item["source"] == ref for item in selected):
            continue
        record = source_record(state, npc, ref)
        if record is None:
            # A previously interrupted activity may have resumed.
            selected.append({"source": copy.deepcopy(ref), "historical_reference": True})
            continue
        fields = {
            "claim": ("speaker", "listener", "claim", "at", "turn", "location"),
            "observation": ("kind", "object", "outcome", "condition", "function", "actor", "at", "turn"),
            "pattern": ("kind", "interpretation", "evidence", "at", "turn"),
            "expectation": ("outcome", "interpretation", "evidence", "at", "turn"),
            "test": ("status", "assessment", "object", "due"),
            "activity": ("status", "assessment", "object", "due", "interruption"),
            "social_test": ("npc", "target", "assessment", "at", "turn"),
        }[ref["kind"]]
        selected.append({"source": copy.deepcopy(ref), "record": {
            k: copy.deepcopy(record[k]) for k in fields if k in record}})
    return {**copy.deepcopy(goal), "decision_evidence": selected}


def project(state):
    result = {}
    for e in state.get("npc_objectives", []):
        if e["operation"] == "create":
            result[e["id"]] = dict(copy.deepcopy(e), status="active")
        else:
            current = result[e["id"]]
            current.update(status=e["status"], priority=e["priority"],
                           intention=e["intention"], latest_review=copy.deepcopy(e))
    return result

def objective(state, rules, request, npc_available, text):
    if not (rules.get("npc_agency") or rules.get("npc_objective_continuity")) or not isinstance(request, dict):
        raise ValueError("NPC objectives unavailable")
    op = request.get("operation")
    base = {"operation", "id", "npc", "priority", "intention", "basis", "sources"}
    if op not in ("create", "review") or set(request) != base | ({"goal"} if op == "create" else {"status"}):
        raise ValueError("invalid objective fields")
    oid, nid = request["id"], request["npc"]
    if not isinstance(oid, str) or not re.fullmatch(r"goal:[a-z][a-z0-9_]{0,63}", oid):
        raise ValueError("invalid objective identity")
    if not isinstance(nid, str) or nid not in state["npcs"]:
        raise ValueError("unknown NPC")
    npc = state["npcs"][nid]
    if npc["location"] is None or not npc_available(state, rules, {"npc": nid, "location": npc["location"]}):
        raise ValueError("objective requires available anchored NPC")
    if rules.get("dialogue_requires_encounter"):
        from age_runtime.mythos.epistemic import conversation_available
        if not conversation_available(state, rules, nid, npc_available):
            raise ValueError("objective requires current authored encounter")
    priority = request["priority"]
    if priority not in ("low", "normal", "urgent"):
        raise ValueError("invalid objective priority")
    sources = request["sources"]
    if not isinstance(sources, list) or len(sources) > 4 or any(not owned_source(state, nid, s) for s in sources):
        raise ValueError("objective source not available to NPC")
    current = project(state)
    ledger = state["npc_objectives"]
    if len(ledger) >= 128:
        raise ValueError("objective record limit")
    entry = {"operation": op, "id": oid, "npc": nid, "priority": priority,
             "intention": text(request["intention"], 240), "basis": text(request["basis"], 240),
             "sources": copy.deepcopy(sources), "at": state["time"], "turn": state["turn"]}
    if op == "create":
        if oid in current or sum(e["npc"] == nid and e["status"] in ("active", "deferred") for e in current.values()) >= 4:
            raise ValueError("duplicate objective or active objective limit")
        entry["goal"] = text(request["goal"], 240)
    else:
        old = current.get(oid)
        status = request["status"]
        if not old or old["npc"] != nid or old["status"] in ("achieved", "abandoned") or status not in ("active", "deferred", "achieved", "abandoned"):
            raise ValueError("invalid objective transition")
        # Achievement is explicitly the NPC's assessment, not objective truth.
        if status == "achieved" and not sources:
            raise ValueError("achievement requires actor-scoped evidence")
        if (status, priority, entry["intention"]) == (old["status"], old["priority"], old["intention"]):
            raise ValueError("objective review does not change its decision")
        entry["status"] = status
    ledger.append(entry)
    if op == "review":
        review_activities(state, entry)

def active_objective(state, nid, oid):
    goal = project(state).get(oid) if isinstance(oid, str) else None
    return bool(goal and goal["npc"] == nid and goal["status"] == "active")


def objective_link(state, nid, request):
    if "objective" not in request:
        return {}
    if not active_objective(state, nid, request["objective"]):
        raise ValueError("activity requires own active objective")
    return {"objective": request["objective"]}


def linked_activities(state, oid):
    return [e for e in state.get("timed_detail_events", []) if e.get("objective") == oid]


def review_activities(state, entry):
    """A suspended/closed objective cannot silently continue its linked work."""
    if entry.get("status") not in ("deferred", "achieved", "abandoned"):
        return
    for event in linked_activities(state, entry["id"]):
        if event["status"] not in ("scheduled", "interrupted"):
            continue
        if entry["status"] == "deferred" and event.get("authority") == "npc_native_test":
            if event["status"] == "scheduled":
                event.update(status="interrupted", interrupted_at=state["time"],
                             interruption="objective_deferred")
                if "task_history" in event:
                    event["task_history"].append({"operation": "interrupt", "at": state["time"],
                        "reason": "objective_deferred", "work_seconds": event.get("work_seconds", 0)})
        else:
            event.update(status="cancelled", cancelled_at=state["time"],
                         cancellation_basis="Objective " + entry["status"])


def modifiers(state, rules, nid, spec, significance):
    npc = state["npcs"][nid]
    gathered = dxd_modifiers.gather(npc["dxd_attributes"], npc["skills"], npc["dxd_traits"], spec, player=False)
    mods = dxd_modifiers.totals(gathered)
    condition = dxd_conditions.penalty_dice(npc["concerns"], decision=spec.get("decision", False))
    policy = rules["npc_agency"]["favor"]
    favor = dxd.automatic_favor(available=npc["favor"], maximum=policy["maximum"],
                               significance=significance, desired=policy["desired"])
    emicted = dxd.emicted_favor(available=npc["favor"], maximum=policy["maximum"], enabled=policy["emicted"])
    net = mods["bonus"] - mods["penalty"] - condition
    return {"dm": mods["dm"]+emicted, "bonus": min(policy["maximum"], max(0, net)),
            "penalty": max(0, -net), "favor": favor}, {"gathered": gathered,
            "condition_penalty_dice": condition, "emicted": emicted}

def social_test(state, rules, request, npc_available, text):
    cfg = rules.get("npc_agency")
    if not cfg or not isinstance(request, dict) or set(request) != {"id", "claim", "basis"}:
        raise ValueError("invalid NPC social Test")
    sid, cid = request["id"], request["claim"]
    if not isinstance(sid, str) or not re.fullmatch(r"social:[a-z][a-z0-9_]{0,63}", sid) or type(cid) is not int:
        raise ValueError("invalid social Test identity")
    claim = next((e for e in state["dialogue"] if e["id"] == cid and "testimony_source" in e), None)
    if not claim or state["dialogue"][-1]["id"] != cid or claim["turn"] != state["turn"] or claim["at"] != state["time"]:
        raise ValueError("social Test requires current NPC testimony")
    nid, target = claim["speaker"], claim["listener"]
    spec = next((s for s in cfg["social_tests"] if s["npc"] == nid and s["target"] == target), None)
    if not spec:
        raise ValueError("unreviewed social Test participants")
    location = claim["location"]
    if any(state["npcs"][a]["location"] != location or not npc_available(state, rules, {"npc": a, "location": location}) for a in (nid, target)):
        raise ValueError("social Test requires available co-located actors")
    ledger = state["npc_social_tests"]
    # A repeated relay of the same source cannot be used to fish for a result.
    if len(ledger) >= 64 or any(e["id"] == sid or (e["npc"], e["target"], e["source"]) == (nid, target, claim["testimony_source"]) for e in ledger):
        raise ValueError("duplicate social Test or record limit")
    basis = text(request["basis"], 240)
    a, audit_a = modifiers(state, rules, nid, spec["active"], spec["significance"])
    b, audit_b = modifiers(state, rules, target, spec["opposition"], spec["significance"])
    ar = state["npcs"][nid]["dxd_attributes"][spec["active"]["attribute"]]
    br = state["npcs"][target]["dxd_attributes"][spec["opposition"]["attribute"]]
    args = {"active_raw": ar, "target_raw": br,
            "active_dm": a["dm"]-dxd.attribute_dm(ar), "target_dm": b["dm"]-dxd.attribute_dm(br)}
    for side, values in (("active", a), ("target", b)):
        args.update({side+"_"+key: values[key] for key in ("bonus", "penalty", "favor")})
    seed = f"{state['seed']}:npc-social:{nid}:{target}:{claim['testimony_source']['kind']}:{claim['testimony_source']['id']}"
    result = dxd.opposed(seed, **args)
    state["npcs"][nid]["favor"] -= a["favor"]
    state["npcs"][target]["favor"] -= b["favor"]
    ledger.append({"id": sid, "claim": cid, "source": copy.deepcopy(claim["testimony_source"]),
                   "npc": nid, "target": target, "at": state["time"], "turn": state["turn"],
                   "location": location, "basis": basis, "inputs": args,
                   "active_audit": audit_a, "target_audit": audit_b, "result": result,
                   "assessment": spec["success"] if result["passed"] else spec["failure"]})

def projection(state):
    current = project(state)
    return {nid: {"objectives": [objective_context(state, e) for e in current.values() if e["npc"] == nid and e["status"] in ("active", "deferred")],
                  "pursuit": [{"id": e["id"], "objective": e["objective"], "status": e["status"],
                               "authority": e["authority"], "object": e["object"], "due": e["due"]}
                              for e in state.get("timed_detail_events", []) if e["npc"] == nid and "objective" in e],
                  "journeys": [{"destination": e["destination"], "objective": e["objective"],
                                "status": e["status"], "due": e["due"]}
                               for e in state.get("npc_travel", []) if e["npc"] == nid and "objective" in e][-6:],
                  "recent_closed": [copy.deepcopy(e) for e in current.values() if e["npc"] == nid and e["status"] in ("achieved", "abandoned")][-4:],
                  **({"favor": npc["favor"]} if "favor" in npc else {}),
                  "social_tests": [copy.deepcopy(e) for e in state.get("npc_social_tests", []) if nid in (e["npc"], e["target"])][-6:]}
            for nid, npc in sorted(state["npcs"].items())}
