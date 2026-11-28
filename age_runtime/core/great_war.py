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
        if set(card) != {"event", "region", "tap", "time"} or card["event"] not in ("manafount", "quiet"):
            raise ValueError("invalid Event")
        if card["region"] not in regions or card["tap"] not in ("none", "optional", "required") or type(card["time"]) is not int or not 0 <= card["time"] <= 5:
            raise ValueError("invalid Event scope")
    if len(s["cards"]) < len(actors) * s["hand_size"] or sum(c["time"] for c in s["cards"].values()) < s["endpoint"]:
        raise ValueError("insufficient Event pool")


def initialize(s, seed):
    validate(s)
    if type(seed) is not int:
        raise ValueError("integer seed required")
    deck = sorted(s["cards"])
    random.Random(seed).shuffle(deck)
    state = {"year": 0, "active": 0, "piles": deepcopy(s["piles"]),
             "founts": {}, "tapped": [], "deck": deck,
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
    if command["tap"] is not None:
        if c["tap"] == "none":
            raise ValueError("Event does not permit Tap Fount")
        tap(s, result, actor, command["tap"], c["region"])
    elif c["tap"] == "required":
        raise ValueError("required opportunity omitted")
    if cid not in result["discard"] and (cid not in result["founts"] or result["founts"][cid]["status"] != "hidden"):
        result["discard"].append(cid)
    if c["time"]:
        result["year"] = min(s["endpoint"], result["year"] + c["time"])
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


def observe(s, session, actor):
    verify(s, session)
    if actor not in s["deities"]:
        raise ValueError("unknown Deity")
    state = session["state"]
    # Preview replenishment only for the active Deity; never expose future deck.
    projected = deepcopy(state)
    if not complete(s, state) and actor == s["deities"][state["active"]]:
        replenish(s, projected, actor)
    return {"actor": actor, "active": s["deities"][state["active"]], "year": state["year"],
            "complete": complete(s, state), "revision": digest(session),
            "hand": {cid: deepcopy(s["cards"][cid]) for cid in projected["hands"][actor]},
            "piles": {pid: {**p, "pl": p["pl"]} if p["deity"] == actor else
                      {"deity": p["deity"], "region": p["region"], "marker": marker(p["pl"])}
                      for pid, p in state["piles"].items()},
            "founts": deepcopy(state["founts"]),
            "tapped": deepcopy(state["tapped"]),
            "plays": len(state["log"]), "qualification": s["qualification"],
            "conclusion": "Time! endpoint" if state["year"] >= s["endpoint"] else
                          "Event pool exhausted" if complete(s, state) else None}


def commit(s, session, actor, revision, command):
    verify(s, session)
    if revision != digest(session):
        raise ValueError("stale Play")
    return {**session, "state": play(s, session["state"], actor, command)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("start", "observe", "play"):
        p = sub.add_parser(name)
        p.add_argument("session", type=Path)
        if name == "start":
            p.add_argument("--seed", type=int, required=True)
        else:
            p.add_argument("actor")
        if name == "play":
            p.add_argument("revision")
            p.add_argument("command", type=Path)
    args = parser.parse_args()
    s = json.loads(SPEC.read_text(encoding="utf-8"))
    if args.operation == "start":
        session = start(s, args.seed)
        with os.fdopen(os.open(args.session, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
            json.dump(session, stream)
        actor = s["deities"][0]
    else:
        session = json.loads(args.session.read_text(encoding="utf-8"))
        actor = args.actor
        if args.operation == "play":
            session = commit(s, session, actor, args.revision,
                             json.loads(args.command.read_text(encoding="utf-8")))
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
