"""Optional local danger: decisive objectives, existing Zones, no AP loop."""
from datetime import datetime, timedelta
import copy


OUTCOMES = ("grant", "grant_failure", "concern_failure", "degree_failure_concern",
            "success_observation", "failure_observation", "degree_observation")


def outcome(cfg, spec, key, default=None):
    return copy.deepcopy(spec.get(key, cfg.get(key, default)))


def prerequisites(state, cfg, spec):
    return (all(f in state["flags"] for f in cfg.get("requires_flags", []) + spec.get("requires_flags", []))
            and not any(f in state["flags"] for f in cfg.get("excludes_flags", []) + spec.get("excludes_flags", []))
            and all(item in state["inventory"] for item in spec.get("items", [])))


def completion_available(state, rules, action):
    if not action.get("danger_beat"):
        return True
    cfg = rules["danger_beats"][action["id"]]
    spec = cfg["approaches"][action["beat_approach"]]
    return state["location"] == cfg["location"] and prerequisites(state, cfg, spec)

def available(state, rules):
    if state["ending"] or state["dxd"].get("activity", {}).get("status") != "awake":
        return []
    result = []
    for key, cfg in rules.get("danger_beats", {}).items():
        if state["location"] != cfg["location"] or key in state["used"]:
            continue
        if not all(f in state["flags"] for f in cfg.get("requires_flags", [])):
            continue
        if any(f in state["flags"] for f in cfg.get("excludes_flags", [])):
            continue
        if datetime.fromisoformat(state["time"]) + timedelta(seconds=cfg["seconds"]) > datetime.fromisoformat(rules["end"]):
            continue
        for approach, spec in cfg["approaches"].items():
            if not prerequisites(state, cfg, spec):
                continue
            result.append({"action": key, "approach": approach, "objective": spec.get("objective", cfg["objective"]),
                           "stakes": spec.get("stakes", cfg["stakes"]), "terrain": cfg["terrain"], "objects": cfg["objects"],
                           "seconds": cfg["seconds"], "description": spec["description"]})
    return result

def compile_beat(state, rules, request):
    if not isinstance(request, dict) or set(request) != {"action", "approach", "intent"} or any(not isinstance(v, str) for v in request.values()):
        raise ValueError("invalid Beat proposal")
    if not request["intent"].strip() or len(request["intent"]) > 240 or any(ord(c) < 32 for c in request["intent"]):
        raise ValueError("invalid Beat intent")
    offer = next((x for x in available(state, rules) if x["action"] == request["action"] and x["approach"] == request["approach"]), None)
    if offer is None:
        raise ValueError("Beat unavailable")
    cfg = rules["danger_beats"][offer["action"]]
    spec = cfg["approaches"][offer["approach"]]
    loc = state["location"]
    return {"id": offer["action"], "label": offer["objective"], "location": loc,
            "duration_seconds": cfg["seconds"], "local_seconds": cfg["seconds"],
            "interval_seconds": 60, "activity": "active", "narrative_beat": True,
            "danger_beat": True, "beat_approach": offer["approach"], "test": dict(spec["test"]),
            "grant": outcome(cfg, spec, "grant", []), "grant_failure": outcome(cfg, spec, "grant_failure", []),
            "concern_failure": outcome(cfg, spec, "concern_failure", {}),
            "failure_observation": outcome(cfg, spec, "failure_observation"),
            "route": {"nodes": [loc], "seconds": 0, "minutes": 0, "terrain": []}}

def record(state, rules, action, result):
    cfg = rules["danger_beats"][action["id"]]
    spec = cfg["approaches"][action["beat_approach"]]
    if result["passed"]:
        state["observations"].append(outcome(cfg, spec, "success_observation"))
        degree = outcome(cfg, spec, "degree_observation")
        if result["dos"] and degree:
            state["observations"].append(degree)
    elif result["dof"]:
        # Additional concern only for an explicitly established severe stake.
        from age_runtime.core import dxd_conditions
        dxd_conditions.add(state["dxd"]["concerns"], **outcome(cfg, spec, "degree_failure_concern", {}))
