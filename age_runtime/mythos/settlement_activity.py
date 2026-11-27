"""Read-only settlement ambience; population is not an NPC roster."""
from datetime import datetime
import copy

LEVELS = ("quiet", "sparse", "ordinary", "busy")


def validate(rules):
    profiles = rules.get("settlement_activity", {})
    if not isinstance(profiles, dict):
        raise ValueError("invalid settlement activity profiles")
    if not profiles:
        return
    if "spatial" not in rules or set(profiles) - set(rules["spatial"]["zones"]):
        raise ValueError("settlement activity requires reviewed spatial zones")
    for zone, profile in profiles.items():
        if not isinstance(profile, dict) or set(profile) != {"default", "windows", "basis"}:
            raise ValueError("invalid settlement activity fields")
        if not isinstance(profile["basis"], str) or not profile["basis"].strip() or len(profile["basis"]) > 240:
            raise ValueError("invalid settlement activity basis")
        if profile["default"] not in LEVELS or not isinstance(profile["windows"], list) or len(profile["windows"]) > 24:
            raise ValueError("invalid settlement activity default or windows")
        occupied = {day: [] for day in range(7)}
        for w in profile["windows"]:
            if not isinstance(w, dict) or set(w) != {"days", "start_minute", "end_minute", "level", "examples"}:
                raise ValueError("invalid settlement window fields")
            days, start, end = w["days"], w["start_minute"], w["end_minute"]
            if (not isinstance(days, list) or not days or any(type(d) is not int or not 0 <= d <= 6 for d in days)
                    or len(set(days)) != len(days) or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= 1440 or w["level"] not in LEVELS):
                raise ValueError("invalid settlement activity calendar")
            examples = w["examples"]
            if (not isinstance(examples, list) or len(examples) > 6
                    or any(not isinstance(x, str) or not x.strip() or len(x) > 120 for x in examples)):
                raise ValueError("invalid settlement activity examples")
            for day in days:
                if any(start < b and end > a for a, b in occupied[day]):
                    raise ValueError("overlapping settlement activity windows")
                occupied[day].append((start, end))


def projection(state, rules):
    """Resolve nearest reviewed zone profile, never instantiate a resident."""
    profiles = rules.get("settlement_activity", {})
    if not profiles:
        return None
    spatial = rules["spatial"]
    zone = spatial["nodes"][state["location"]]["zone"]
    while zone is not None and zone not in profiles:
        zone = spatial["zones"][zone].get("parent")
    if zone is None:
        return None
    profile = profiles[zone]
    now = datetime.fromisoformat(state["time"])
    minute = now.hour * 60 + now.minute
    window = next((w for w in profile["windows"] if now.weekday() in w["days"]
                   and w["start_minute"] <= minute < w["end_minute"]), None)
    return {"zone": zone, "level": window["level"] if window else profile["default"],
            "possible_activity": copy.deepcopy(window["examples"]) if window else [],
            "basis": profile["basis"], "authority": "ambience_only",
            "guidance": "Possible background activity, not established people, witnesses, services or events. "
                        "Respect established circumstances; materialize only relevant details."}
