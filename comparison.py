"""Read-only comparison of completed administrative sessions."""
import argparse
import json
from pathlib import Path
from runner import verify_checkpoint

def summarize(scenario, state):
    verify_checkpoint(scenario, state)
    if state["minute"] != scenario["end_minute"]:
        raise ValueError("comparison requires completed sessions")
    return {
        "scenario": scenario["id"],
        "scenario_digest": state["scenario"],
        "minutes": state["minute"],
        "values": state["values"].copy(),
        "milestones": {"passed": sum(c["passed"] for c in state["checks"]),
                       "total": len(state["checks"])},
        "requests": {"submitted": len(state["requests"]),
                     "reviewed": sum(r["status"] == "reviewed" for r in state["requests"]),
                     "pending": sum(r["status"] == "validated_request" for r in state["requests"])},
        "objectives": {aid: {oid: obj["met"] for oid, obj in actor["objectives"].items()}
                       for aid, actor in state["actors"].items()}
    }

def compare(scenario, left, right):
    """Compare two verified sessions of the same pinned scenario."""
    a, b = summarize(scenario, left), summarize(scenario, right)
    return {"scenario": a["scenario"], "scenario_digest": a["scenario_digest"],
            "left": a, "right": b,
            "right_minus_left": {
                "values": {key: b["values"][key] - value for key, value in a["values"].items()},
                "requests": {key: b["requests"][key] - value for key, value in a["requests"].items()}
            },
            "interpretation": "Descriptive differences only; no causal attribution."}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scenario", type=Path)
    p.add_argument("left", type=Path)
    p.add_argument("right", type=Path)
    args = p.parse_args()
    try:
        result = compare(*(json.loads(path.read_text()) for path in
                           (args.scenario, args.left, args.right)))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
