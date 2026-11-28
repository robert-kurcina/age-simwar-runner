"""Bounded Great War rehearsal: continuous Event Plays, native Manafount rules.

No PR economy, combat, annual turns or canonical scoring. All card quantities
and setup values belong to the explicitly illustrative scenario.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import os
import tempfile
from age_runtime.core.runner import digest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "scenarios/great-war/manafount/scenario.json"


def marker(pl):
    return 3 if pl <= 3 else 10 if pl <= 10 else 30


def validate(s):
    if s.get("qualification") != "unreviewed-rehearsal":
        raise ValueError("only unreviewed Great War rehearsal supported")
    actors = s["deities"]
    if not isinstance(actors, list) or not 2 <= len(actors) <= 6 or len(set(actors)) != len(actors):
        raise ValueError("distinct Deities required")
    if "motivations" in s:
        motivations = s["motivations"]
        if (not isinstance(motivations, dict) or set(motivations) != set(actors)
                or any(not isinstance(v, str) or not v.strip() or len(v) > 1000
                       for v in motivations.values())):
            raise ValueError("invalid Deity motivations")
    if type(s["hand_size"]) is not int or s["hand_size"] < 1:
        raise ValueError("positive hand size required")
    if type(s["endpoint"]) is not int or not 1 <= s["endpoint"] <= 5:
        raise ValueError("invalid Time! endpoint")
    regions = s["regions"]
    hexes = [h for cells in regions.values() for h in cells]
    if len(hexes) != len(set(hexes)) or any(not cells for cells in regions.values()):
        raise ValueError("distinct regional hexes required")
    for pid, p in s["piles"].items():
        if p["deity"] not in actors or p["region"] not in regions or type(p["pl"]) is not int or not 1 <= p["pl"] <= 30:
            raise ValueError("invalid Prominence")
    for card in s["cards"].values():
        if set(card) != ({"event", "region", "tap", "time", "duration"} if card["event"] == "experiment" else {"event", "region", "tap", "time"}) or card["event"] not in ("manafount", "quiet", "experiment", "conclude-experiment"):
            raise ValueError("invalid Event")
        if card["region"] not in regions or card["tap"] not in ("none", "optional", "required") or type(card["time"]) is not int or not 0 <= card["time"] <= 5:
            raise ValueError("invalid Event scope")
        if card["event"] == "experiment" and (type(card["duration"]) is not int or not 1 <= card["duration"] <= 5):
            raise ValueError("invalid illustrative Experiment duration")
    if len(s["cards"]) < len(actors) * s["hand_size"] or sum(c["time"] for c in s["cards"].values()) < s["endpoint"]:
        raise ValueError("insufficient Event pool")


def initialize(s, seed):
    validate(s)
    if type(seed) is not int:
        raise ValueError("integer seed required")
    deck = sorted(s["cards"])
    random.Random(seed).shuffle(deck)
    state = {"year": 0, "active": 0, "piles": deepcopy(s["piles"]),
             "founts": {}, "commitments": {}, "commitment_history": [], "tapped": [], "deck": deck,
             "hands": {a: [] for a in s["deities"]}, "discard": [], "log": []}
    for actor in s["deities"]:
        replenish(s, state, actor)
    return state


def replenish(s, state, actor):
    hand = state["hands"][actor]
    while len(hand) < s["hand_size"] and state["deck"]:
        hand.append(state["deck"].pop(0))


def complete(s, state):
    return state["year"] >= s["endpoint"] or not (state["deck"] or any(state["hands"].values()))


def tap(s, state, actor, choice, region):
    if not isinstance(choice, dict) or set(choice) != {"fount", "pile", "disposition"}:
        raise ValueError("invalid Tap Fount choice")
    f = state["founts"].get(choice["fount"])
    p = state["piles"].get(choice["pile"])
    if (not f or not p or p["deity"] != actor or p["region"] != region or f["region"] != region
            or (f["status"] == "hidden" and f["controller"] != actor)
            or [actor, region] in state["tapped"]):
        raise ValueError("Tap Fount unavailable")
    disposition = choice["disposition"]
    if f["status"] == "hidden":
        if disposition == "remove":
            del state["founts"][choice["fount"]]
            if choice["fount"] not in state["discard"]:
                state["discard"].append(choice["fount"])
        elif disposition in s["regions"][region] and not any(
                other.get("hex") == disposition for other in state["founts"].values()):
            f.update(status="wondrous", hex=disposition)
            del f["controller"]
            if choice["fount"] not in state["discard"]:
                state["discard"].append(choice["fount"])
        else:
            raise ValueError("invalid revelation hex")
    elif disposition is not None:
        raise ValueError("public Fount has automatic disposition")
    elif f["status"] == "wondrous":
        f["status"] = "emitter"
    else:
        del state["founts"][choice["fount"]]
    p["pl"] = min(30, p["pl"] + {3: 1, 10: 2, 30: 3}[marker(p["pl"])])
    state["tapped"].append([actor, region])


def end_commitment(state, key, reason, year):
    record = state["commitments"].pop(key)
    state["commitment_history"].append({"card": key, **record, "reason": reason, "ended_year": year})
    state["discard"].append(key)


def play(s, state, actor, command):
    if complete(s, state) or actor != s["deities"][state["active"]]:
        raise ValueError("not active Deity")
    if not isinstance(command, dict) or set(command) != {"card", "tap"}:
        raise ValueError("invalid Play")
    result = deepcopy(state)
    replenish(s, result, actor)
    cid = command["card"]
    if cid not in result["hands"][actor]:
        raise ValueError("Event not in hand")
    c = s["cards"][cid]
    result["hands"][actor].remove(cid)
    if c["event"] == "manafount":
        result["founts"][cid] = {"region": c["region"], "status": "hidden", "controller": actor}
    if c["event"] == "experiment":
        if not any(p["deity"] == actor and p["region"] == c["region"] for p in result["piles"].values()):
            raise ValueError("Experiment requires local Prominence")
        if any(p["owner"] == actor and p["region"] == c["region"] for p in result["commitments"].values()):
            raise ValueError("Experiment already maintained in Region")
        result["commitments"][cid] = {"owner": actor, "region": c["region"],
                                       "remaining": c["duration"], "started_year": result["year"]}
    elif c["event"] == "conclude-experiment":
        target = next((key for key, p in result["commitments"].items()
                       if p["owner"] == actor and p["region"] == c["region"]), None)
        # This illustrative Event explicitly permits a quiet resolution if no
        # own regional Experiment exists. No universal pass rule is implied.
        if target is not None:
            end_commitment(result, target, "voluntary", result["year"])
    if command["tap"] is not None:
        if c["tap"] == "none":
            raise ValueError("Event does not permit Tap Fount")
        tap(s, result, actor, command["tap"], c["region"])
    elif c["tap"] == "required":
        raise ValueError("required opportunity omitted")
    if cid not in result["commitments"] and cid not in result["discard"] and (cid not in result["founts"] or result["founts"][cid]["status"] != "hidden"):
        result["discard"].append(cid)
    if c["time"]:
        old_year = result["year"]
        result["year"] = min(s["endpoint"], old_year + c["time"])
        for year in range(old_year + 1, result["year"] + 1):
            for key in sorted(result["commitments"]):
                p = result["commitments"][key]
                p["remaining"] -= 1
                if p["remaining"] == 0:
                    end_commitment(result, key, "completed", year)
        result["tapped"] = []
        for f in result["founts"].values():
            if f["status"] == "emitter":
                f["status"] = "wondrous"
    result["log"].append({"actor": actor, "command": deepcopy(command)})
    # Exhausted hands are skipped only when no replenishment is possible.
    for offset in range(1, len(s["deities"]) + 1):
        idx = (state["active"] + offset) % len(s["deities"])
        if result["deck"] or result["hands"][s["deities"][idx]]:
            result["active"] = idx
            break
    return result


def start(s, seed):
    return {"spec_digest": digest(s), "seed": seed, "state": initialize(s, seed)}


def verify(s, session):
    if session["spec_digest"] != digest(s):
        raise ValueError("scenario changed")
    state = initialize(s, session["seed"])
    for record in session["state"]["log"]:
        state = play(s, state, record["actor"], record["command"])
    if state != session["state"]:
        raise ValueError("checkpoint replay mismatch")
    return session


def legal_choices(s, state, actor):
    """Enumerate bounded authored commands using the same resolver as commit."""
    if complete(s, state) or actor != s["deities"][state["active"]]:
        return []
    projected = deepcopy(state)
    replenish(s, projected, actor)
    choices = []
    for cid in projected["hands"][actor]:
        c = s["cards"][cid]
        candidates = [None] if c["tap"] != "required" else []
        if c["tap"] != "none" and [actor, c["region"]] not in state["tapped"]:
            founts = deepcopy(state["founts"])
            if c["event"] == "manafount":
                founts[cid] = {"region": c["region"], "status": "hidden", "controller": actor}
            for fid, f in sorted(founts.items()):
                if f["region"] != c["region"] or (f["status"] == "hidden" and f["controller"] != actor):
                    continue
                dispositions = (["remove"] + s["regions"][c["region"]]
                                if f["status"] == "hidden" else [None])
                for pid, pile in sorted(state["piles"].items()):
                    if pile["deity"] == actor and pile["region"] == c["region"]:
                        candidates.extend({"fount": fid, "pile": pid, "disposition": d}
                                          for d in dispositions)
        for choice in candidates:
            command = {"card": cid, "tap": choice}
            try:
                play(s, state, actor, command)
            except ValueError:
                continue
            choices.append(command)
    return choices


def assess_choice(s, state, actor, command):
    """Describe immediate, deterministic consequences; no forecast of future draws."""
    after = play(s, state, actor, command)
    changes = []
    for pid, pile in state["piles"].items():
        if pile["deity"] == actor:
            new = after["piles"][pid]["pl"]
            if new != pile["pl"]:
                changes.append({"pile": pid, "before": pile["pl"], "after": new,
                                "gain": new - pile["pl"], "public_marker_after": marker(new)})
    founts = []
    for fid in sorted(set(state["founts"]) | set(after["founts"])):
        old = state["founts"].get(fid)
        new = after["founts"].get(fid)
        if old != new:
            founts.append({"fount": fid, "before": deepcopy(old), "after": deepcopy(new)})
    choice = command["tap"]
    card = s["cards"][command["card"]]
    tapped = None
    if choice is not None:
        f = state["founts"].get(choice["fount"])
        if f is None and card["event"] == "manafount" and choice["fount"] == command["card"]:
            f = {"region": card["region"], "status": "hidden", "controller": actor}
        tapped = {"fount": choice["fount"], "prior_status": f["status"],
                  "effect": ("remove-hidden" if choice["disposition"] == "remove" else
                             "reveal-public" if f["status"] == "hidden" else
                             "drain-public" if f["status"] == "wondrous" else "remove-drained")}
    return {"year_after": after["year"], "time_advance": after["year"] - state["year"],
            "remaining_years": s["endpoint"] - after["year"],
            "own_prominence_changes": changes, "public_fount_changes": founts,
            "tap": tapped, "regional_tap_limits_reset": bool(card["time"]),
            "establishes_fount": command["card"] if card["event"] == "manafount" else None,
            "ends_rehearsal": complete(s, after),
            "commitments_after": deepcopy(after["commitments"]),
            "commitments_ended": deepcopy(after["commitment_history"][len(state["commitment_history"]):])}


def decision_packet(s, session, actor):
    observation = observe(s, session, actor)
    if observation["complete"] or observation["active"] != actor:
        raise ValueError("no active decision for Deity")
    if not observation["choices"]:
        raise ValueError("no legal Event; scenario requires an explicit fallback rule")
    packet = {"version": 1, "observation": observation,
              "instruction": "Choose one offered command by index. Weigh your own motivation, "
                             "immediate gains, shared access, time and future uncertainty. "
                             "Motivation is advisory, not compulsory. Do not invent effects or opposing PL."}
    return {**packet, "packet_id": digest(packet)}


def resolve_choice(s, session, actor, response):
    packet = decision_packet(s, session, actor)
    if (not isinstance(response, dict) or set(response) != {"packet_id", "choice"}
            or response["packet_id"] != packet["packet_id"]
            or type(response["choice"]) is not int
            or not 0 <= response["choice"] < len(packet["observation"]["choices"])):
        raise ValueError("invalid or stale Deity choice")
    return commit(s, session, actor, packet["observation"]["revision"],
                  packet["observation"]["choices"][response["choice"]])


def observe(s, session, actor):
    verify(s, session)
    if actor not in s["deities"]:
        raise ValueError("unknown Deity")
    state = session["state"]
    # Preview replenishment only for the active Deity; never expose future deck.
    projected = deepcopy(state)
    if not complete(s, state) and actor == s["deities"][state["active"]]:
        replenish(s, projected, actor)
    choices = legal_choices(s, state, actor)
    return {"actor": actor, "active": s["deities"][state["active"]], "year": state["year"],
            "complete": complete(s, state), "revision": digest(session),
            "hand": {cid: deepcopy(s["cards"][cid]) for cid in projected["hands"][actor]},
            "piles": {pid: {**p, "pl": p["pl"]} if p["deity"] == actor else
                      {"deity": p["deity"], "region": p["region"], "marker": marker(p["pl"])}
                      for pid, p in state["piles"].items()},
            "founts": deepcopy(state["founts"]),
            "commitments": deepcopy(state["commitments"]),
            "commitment_history": deepcopy(state["commitment_history"]),
            "tapped": deepcopy(state["tapped"]),
            "choices": choices,
            "choice_assessments": [assess_choice(s, state, actor, c) for c in choices],
            **({"motivation": s["motivations"][actor]} if "motivations" in s else {}),
            "assessment_basis": "Immediate deterministic resolution only; no forecast of future draws or opponent decisions.",
            "remaining_years": s["endpoint"] - state["year"],
            "recent_plays": deepcopy(state["log"][-3:]),
            "plays": len(state["log"]), "qualification": s["qualification"],
            "conclusion": "Time! endpoint" if state["year"] >= s["endpoint"] else
                          "Event pool exhausted" if complete(s, state) else None}


def commit(s, session, actor, revision, command):
    verify(s, session)
    if revision != digest(session):
        raise ValueError("stale Play")
    return {**session, "state": play(s, session["state"], actor, command)}


def discovery(root=None):
    """Public launch metadata only; do not expose the referee configuration."""
    path = SPEC if root is None else Path(root) / SPEC.relative_to(ROOT)
    s = json.loads(path.read_text(encoding="utf-8"))
    validate(s)
    # Exercise every perspective's observation without publishing opening state.
    opening = start(s, 0)
    for actor in s["deities"]:
        observe(s, opening, actor)
    return {"id": "great-war", "title": "Great War",
            "framework": "great-war", "qualification": s["qualification"],
            "episodes": [{"id": s["id"], "title": "Manafount rehearsal",
                          "availability": "available", "play_mode": "great-war",
                          "perspectives": [{"id": a, "label": a.title()} for a in s["deities"]],
                          "duration": {"clock": "event-driven-Time!", "endpoint_year": s["endpoint"]},
                          "conclusion": {"mode": "state-summary", "competitive_scoring": False},
                          "launcher": "python -m age_runtime.core.great_war",
                          "guide": "scenarios/great-war/manafount/README.md"}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list")
    for name in ("start", "observe", "play", "packet", "choose"):
        p = sub.add_parser(name)
        p.add_argument("session", type=Path)
        if name == "start":
            p.add_argument("--seed", type=int, required=True)
            p.add_argument("--actor")
        else:
            p.add_argument("actor")
        if name == "play":
            p.add_argument("revision")
            p.add_argument("command", type=Path)
        if name == "choose":
            p.add_argument("response", type=Path)
    args = parser.parse_args()
    if args.operation == "list":
        print(json.dumps(discovery(), indent=2))
        return
    s = json.loads(SPEC.read_text(encoding="utf-8"))
    if args.operation == "start":
        actor = args.actor or s["deities"][0]
        if actor not in s["deities"]:
            parser.error("unknown Deity")
        session = start(s, args.seed)
        with os.fdopen(os.open(args.session, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
            json.dump(session, stream)
    else:
        session = json.loads(args.session.read_text(encoding="utf-8"))
        actor = args.actor
        if args.operation == "packet":
            print(json.dumps(decision_packet(s, session, actor), indent=2))
            return
        if args.operation in ("play", "choose"):
            if args.operation == "play":
                session = commit(s, session, actor, args.revision,
                                 json.loads(args.command.read_text(encoding="utf-8")))
            else:
                session = resolve_choice(s, session, actor,
                                         json.loads(args.response.read_text(encoding="utf-8")))
            fd, temporary = tempfile.mkstemp(dir=args.session.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(session, stream)
                os.replace(temporary, args.session)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    print(json.dumps(observe(s, session, actor), indent=2))


if __name__ == "__main__":
    main()
