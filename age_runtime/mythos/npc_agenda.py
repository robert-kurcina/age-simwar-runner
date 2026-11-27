"""Sparse weekly expectations; never authoritative whereabouts or a scheduler."""
from datetime import datetime
import copy

from age_runtime.mythos import npc_travel, npc_time


def validate(rules):
    agendas = rules.get("npc_agendas", {})
    if not isinstance(agendas, dict) or set(agendas) - set(rules["npcs"]):
        raise ValueError("invalid NPC agenda owners")
    if agendas and not (rules.get("npc_lifecycle") and rules.get("npc_travel")):
        raise ValueError("agendas require existing lifecycle and travel")
    for nid, windows in agendas.items():
        if not isinstance(windows, list) or not 1 <= len(windows) <= 24:
            raise ValueError("invalid agenda window count")
        locations = rules["npcs"][nid].get("eligible_locations", [])
        occupied = {day: [] for day in range(7)}
        for w in windows:
            if not isinstance(w, dict) or set(w) != {"days", "start_minute", "end_minute", "location", "label"}:
                raise ValueError("invalid agenda window fields")
            days, start, end = w["days"], w["start_minute"], w["end_minute"]
            if (not isinstance(days, list) or not days or any(type(d) is not int or not 0 <= d <= 6 for d in days)
                    or len(set(days)) != len(days) or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= 1440):
                raise ValueError("invalid agenda calendar")
            if w["location"] not in locations or w["location"] not in rules["spatial"]["nodes"]:
                raise ValueError("agenda location outside reviewed NPC locations")
            if not isinstance(w["label"], str) or not w["label"].strip() or len(w["label"]) > 120:
                raise ValueError("invalid agenda activity label")
            for day in days:
                if any(start < b and end > a for a, b in occupied[day]):
                    raise ValueError("overlapping weekly agenda windows")
                occupied[day].append((start, end))


def expected(windows, at):
    minute = at.hour * 60 + at.minute
    return next((copy.deepcopy(w) for w in windows if at.weekday() in w["days"]
                 and w["start_minute"] <= minute < w["end_minute"]), None)


def projection(state, rules):
    """Private read-only guidance. Missing windows mean unknown, not absence."""
    now = datetime.fromisoformat(state["time"])
    result = {}
    for nid, windows in sorted(rules.get("npc_agendas", {}).items()):
        npc = state["npcs"][nid]
        routine = expected(windows, now)
        travel = npc_travel.pending(state, nid)
        pending = any(e["npc"] == nid and e["status"] == "scheduled"
                      for e in state.get("timed_detail_events", []))
        constraints = []
        if npc.get("activity", {}).get("status") == "asleep":
            constraints.append("asleep")
        if travel:
            constraints.append("committed_travel")
        if npc.get("activity_plan"):
            constraints.append("committed_activity")
        if pending:
            constraints.append("committed_task")
        if routine and npc["location"] != routine["location"]:
            constraints.append("different_established_location")
        result[nid] = {"expected": routine, "established_location": npc["location"],
                       "constraints": constraints, "authority": "advisory_only",
                       "weekly_windows": copy.deepcopy(windows)}
    return result
