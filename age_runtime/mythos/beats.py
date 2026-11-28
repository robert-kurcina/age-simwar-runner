"""Optional local danger: decisive objectives, existing Zones, no AP loop."""
from datetime import datetime, timedelta
import copy
from age_runtime.mythos import epistemic
from age_runtime.core import dxd_physical_disability, dxd_hitpoints


def outcome(cfg, spec, key, default=None):
    return copy.deepcopy(spec.get(key, cfg.get(key, default)))


def prerequisites(state, cfg, spec, rules=None):
    return (all(epistemic.action_flag(state, rules or {}, f) for f in cfg.get("requires_flags", []) + spec.get("requires_flags", []))
            and not any(f in state["flags"] for f in cfg.get("excludes_flags", []) + spec.get("excludes_flags", []))
            and all(item in state["inventory"] for item in spec.get("items", [])))


def completion_available(state, rules, action):
    if not action.get("danger_beat"):
        return True
    cfg = rules["danger_beats"][action["id"]]
    spec = cfg["approaches"][action["beat_approach"]]
    return state["location"] == cfg["location"] and prerequisites(state, cfg, spec, rules)

def available(state, rules):
    if state["ending"] or dxd_hitpoints.incapacitated(state["dxd"]) or state["dxd"].get("activity", {}).get("status") != "awake":
        return []
    result = []
    for key, cfg in rules.get("danger_beats", {}).items():
        if state["location"] != cfg["location"] or key in state["used"]:
            continue
        if datetime.fromisoformat(state["time"]) + timedelta(seconds=cfg["seconds"]) > datetime.fromisoformat(rules["end"]):
            continue
        for approach, spec in cfg["approaches"].items():
            if not prerequisites(state, cfg, spec, rules):
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
    injury = outcome(cfg, spec, "resolved_injury_on_dof", 0)
    if type(injury) is not int or injury < 0:
        raise ValueError("invalid resolved Beat Injury")
    if injury and ("injury" not in state["dxd"] or injury >= state["dxd"]["injury"]["capacity"] or state["dxd"]["injury"]["injury"] + 1 >= state["dxd"]["injury"]["capacity"]):
        if not (rules.get("native_injury_lifecycle") and spec.get("allow_incapacity") is True and "injury" in state["dxd"]):
            raise ValueError("potentially incapacitating Injury requires explicit consequence authority")
    hp = outcome(cfg, spec, "hitpoint_loss_on_dof", 0)
    subdue = outcome(cfg, spec, "resolved_subdue_on_dof", 0)
    if any(type(n) is not int or n < 0 for n in (hp, subdue)) or (hp and subdue) or (subdue and injury):
        raise ValueError("invalid reviewed Hitpoint consequence")
    if hp or subdue:
        pool = state["dxd"].get("hitpoints")
        if not rules.get("native_hitpoints") or not pool or hp > pool["current"]:
            raise ValueError("Hitpoint consequence unavailable")
        if subdue and (spec.get("allow_incapacity") is not True or "injury" not in state["dxd"]):
            raise ValueError("Subdue requires explicit incapacity authority")
    stun = outcome(cfg, spec, "resolved_stun_on_dof", False)
    if type(stun) is not bool or (stun and (not rules.get("native_awakening") or not injury or subdue or spec.get("allow_incapacity") is not True or not state["dxd"].get("hitpoints"))):
        raise ValueError("Stun requires reviewed Injury and incapacity authority")
    permanent = outcome(cfg, spec, "permanent_location_on_dof")
    if permanent is not None:
        dxd_physical_disability.validate(permanent)
        if not injury or not rules.get("native_permanent_locations"):
            raise ValueError("permanent loss requires reviewed resolved Injury authority")
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
    injury = outcome(cfg, spec, "resolved_injury_on_dof", 0)
    if not result["passed"] and result["dof"] and injury:
        from age_runtime.core import dxd_injury
        dxd_injury.apply(state["dxd"]["injury"], injury)
        permanent = outcome(cfg, spec, "permanent_location_on_dof")
        if permanent is not None and dxd_injury.projection(state["dxd"]["injury"])["status"] != "dead":
            dxd_physical_disability.record(state["dxd"]["injury"], permanent)
    if not result["passed"] and result["dof"]:
        hp = outcome(cfg, spec, "hitpoint_loss_on_dof", 0)
        subdue = outcome(cfg, spec, "resolved_subdue_on_dof", 0)
        if hp:
            dxd_hitpoints.lose(state["dxd"]["hitpoints"], hp)
        if subdue:
            dxd_hitpoints.subdue(state["dxd"], subdue)
        if (outcome(cfg, spec, "resolved_stun_on_dof", False) and not state["dxd"]["hitpoints"]["current"]
                and not dxd_hitpoints.incapacitated(state["dxd"]) and not state["dxd"]["hitpoints"].get("stun_pending")):
            dxd_hitpoints.stun_resistance(state["dxd"], f"{state['seed']}:{state['turn']}:beat")
    if result["passed"]:
        state["observations"].append(outcome(cfg, spec, "success_observation"))
        degree = outcome(cfg, spec, "degree_observation")
        if result["dos"] and degree:
            state["observations"].append(degree)
    elif result["dof"]:
        # Additional concern only for an explicitly established severe stake.
        from age_runtime.core import dxd_conditions
        dxd_conditions.add(state["dxd"]["concerns"], **outcome(cfg, spec, "degree_failure_concern", {}))
