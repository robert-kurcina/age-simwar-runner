"""Optional local danger: decisive objectives, existing Zones, no AP loop."""
from datetime import datetime, timedelta

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
            if not all(item in state["inventory"] for item in spec.get("items", [])):
                continue
            result.append({"action": key, "approach": approach, "objective": cfg["objective"],
                           "stakes": cfg["stakes"], "terrain": cfg["terrain"], "objects": cfg["objects"],
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
    return {"id": offer["action"], "label": cfg["objective"], "location": loc,
            "duration_seconds": cfg["seconds"], "local_seconds": cfg["seconds"],
            "interval_seconds": 60, "activity": "active", "narrative_beat": True,
            "danger_beat": True, "test": dict(spec["test"]),
            "grant": list(cfg.get("grant", [])), "grant_failure": list(cfg.get("grant_failure", [])),
            "concern_failure": dict(cfg.get("concern_failure", {})),
            "failure_observation": cfg["failure_observation"],
            "route": {"nodes": [loc], "seconds": 0, "minutes": 0, "terrain": []}}

def record(state, rules, action, result):
    cfg = rules["danger_beats"][action["id"]]
    if result["passed"]:
        state["observations"].append(cfg["success_observation"])
        if result["dos"] and cfg.get("degree_observation"):
            state["observations"].append(cfg["degree_observation"])
    elif result["dof"]:
        # Additional concern only for an explicitly established severe stake.
        from age_runtime.core import dxd_conditions
        dxd_conditions.add(state["dxd"]["concerns"], **cfg.get("degree_failure_concern", {}))
