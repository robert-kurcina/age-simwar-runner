"""Minimal deterministic scenario runner; standard library only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from actors import validate_actors, evaluate
from observations import validate_views, observe
from actions import validate_catalog

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()

def integer(value):
    return type(value) is int

def validate(s):
    if s.get("version") != 1 or not isinstance(s.get("id"), str):
        raise ValueError("invalid scenario identity")
    if not integer(s["turn_minutes"]) or s["turn_minutes"] <= 0:
        raise ValueError("invalid turn duration")
    if not integer(s["end_minute"]) or s["end_minute"] <= 0:
        raise ValueError("invalid horizon")
    initial = s["initial"]
    if not isinstance(initial, dict) or not all(integer(v) for v in initial.values()):
        raise ValueError("initial values must be integers")
    validate_actors(s)
    validate_views(s)
    validate_catalog(s)
    ids = set()
    for e in s["events"]:
        if not isinstance(e["id"], str) or e["id"] in ids:
            raise ValueError("duplicate or invalid event ID")
        ids.add(e["id"])
        if not integer(e["minute"]) or not 0 < e["minute"] <= s["end_minute"]:
            raise ValueError("event outside horizon")
        if e["key"] not in initial or not integer(e["delta"]):
            raise ValueError("invalid event update")
    for c in s["constraints"]:
        if c["key"] not in initial or not integer(c["equals"]):
            raise ValueError("invalid constraint")
        if not integer(c["minute"]) or not 0 < c["minute"] <= s["end_minute"]:
            raise ValueError("constraint outside horizon")

def initialize(s):
    validate(s)
    return {"scenario": digest(s), "minute": 0, "turn": 0,
            "values": copy.deepcopy(s["initial"]), "ledger": [], "checks": [],
            "actors": evaluate(s, s["initial"])}

def advance(s, state):
    validate(s)
    if state["scenario"] != digest(s):
        raise ValueError("scenario revision mismatch")
    start = state["minute"]
    if start >= s["end_minute"]:
        return copy.deepcopy(state)
    end = min(start + s["turn_minutes"], s["end_minute"])
    result = copy.deepcopy(state)
    times = sorted({x["minute"] for x in s["events"] + s["constraints"]
                    if start < x["minute"] <= end})
    for minute in times:
        for event in s["events"]:
            if event["minute"] == minute:
                key = event["key"]
                result["values"][key] += event["delta"]
                result["ledger"].append({"id": event["id"], "minute": minute,
                    "key": key, "delta": event["delta"], "value": result["values"][key]})
        for check in s["constraints"]:
            if check["minute"] == minute:
                actual = result["values"][check["key"]]
                result["checks"].append({**check, "actual": actual,
                    "passed": actual == check["equals"]})
    result.update(minute=end, turn=state["turn"] + 1,
                  actors=evaluate(s, result["values"]))
    return result

def verify_checkpoint(s, state):
    expected = initialize(s)
    if not integer(state.get("turn")) or not 0 <= state["turn"] <= (s["end_minute"] + s["turn_minutes"] - 1) // s["turn_minutes"]:
        raise ValueError("invalid checkpoint turn")
    for _ in range(state["turn"]):
        expected = advance(s, expected)
    if expected != state:
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
    p.add_argument("checkpoint", type=Path)
    p.add_argument("--turns", type=int, default=1)
    p.add_argument("--actor", help="Print only this actor’s observation; checkpoint remains referee-only")
    args = p.parse_args()
    if args.turns < 0:
        p.error("turns must be nonnegative")
    s = json.loads(args.scenario.read_text())
    state = initialize(s)
    if args.actor is not None and args.actor not in s.get("actors", {}):
        p.error("unknown actor")
    if args.checkpoint.exists():
        state = json.loads(args.checkpoint.read_text())
        verify_checkpoint(s, state)
    for _ in range(args.turns):
        if state["minute"] >= s["end_minute"]:
            break
        state = advance(s, state)
    save(args.checkpoint, state)
    if args.actor is not None:
        print(json.dumps(observe(s, state, args.actor), indent=2))
        return 0  # do not leak private historical constraint status via exit code
    print(json.dumps(state, indent=2))
    return 0 if all(c["passed"] for c in state["checks"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
