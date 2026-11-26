"""Repeatable public library demonstration; no external model or services."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from age_runtime.core.runner import initialize, advance, submit_request, save, verify_checkpoint
from age_runtime.core.observations import observe

def run_demo():
    scenario = json.loads((Path(__file__).resolve().parents[2] / "scenarios/demo.json").read_text())
    state = initialize(scenario)
    state = submit_request(scenario, state, "library", {"action": "request_room_inspection"})
    state = submit_request(scenario, state, "maintenance", {"action": "request_maintenance_review"})
    timeline = []
    def snapshot(current):
        return {"turn": current["turn"], "minute": current["minute"],
                "actual_rooms": current["values"]["available_rooms"],
                "reported_rooms": observe(scenario, current, "library")["values"].get("available_rooms"),
                "pending_reviews": sum(r["status"] == "validated_request" for r in current["requests"]),
                "reviewed": sum(r["status"] == "reviewed" for r in current["requests"])}
    timeline.append(snapshot(state))
    with TemporaryDirectory() as folder:
        path = Path(folder) / "session.json"
        while state["minute"] < scenario["end_minute"]:
            state = advance(scenario, state)
            save(path, state)
            state = json.loads(path.read_text())
            verify_checkpoint(scenario, state)
            timeline.append(snapshot(state))
    return {"scenario": scenario["id"], "timeline": timeline,
            "constraints_passed": all(c["passed"] for c in state["checks"]),
            "final_objectives": state["actors"]}

if __name__ == "__main__":
    result = run_demo()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["constraints_passed"] else 1)
