"""Sparse weekly expectations; never authoritative whereabouts or a scheduler."""
from datetime import datetime
import copy

from age_runtime.mythos import npc_travel, spatial


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
                       "weekly_windows": copy.deepcopy(windows),
                       "offscreen_since": npc.get("offscreen_since")}
    return result


def depart(state, rules, request, npc_available, text):
    """GM selects a prospective agenda trip; use ordinary travel authority.

    No retroactive arrival, automatic departures or interruption of a
    committed activity merely because a routine window has begun.
    """
    if not isinstance(request, dict) or set(request) != {"npc", "destination", "basis"}:
        raise ValueError("invalid agenda departure")
    nid = request["npc"]
    if not isinstance(nid, str) or nid not in rules.get("npc_agendas", {}):
        raise ValueError("NPC has no reviewed agenda")
    if state["npcs"][nid].get("activity_plan"):
        raise ValueError("agenda departure conflicts with committed activity")
    # Existing travel validates route, elapsed time, eligibility, sleep,
    # pending tasks, horizon and conflicting travel. A motivated deviation
    # may select any reviewed eligible destination, not just today's routine.
    npc_travel.record(state, rules, request, npc_available, text)


def initialize_presence(state, rules):
    """A single conservative lower bound on uncommitted off-screen time."""
    if rules.get("npc_contextual_presence"):
        if not rules.get("npc_agendas"):
            raise ValueError("contextual presence requires reviewed agendas")
        for nid in rules["npc_agendas"]:
            state["npcs"][nid]["offscreen_since"] = None


def observe_boundary(state, rules, *, engaged=None):
    """Track only uninterrupted opportunities, not a schedule or position log.

    Co-location is conservatively treated as potential observation. Reset
    on any explicit commitment, sleep, or unavailable anchor. During PC
    travel the old node remains authoritative until arrival.
    """
    for nid in rules.get("npc_agendas", {}):
        npc = state["npcs"][nid]
        if "offscreen_since" not in npc:
            continue
        blocked = (nid == engaged or npc["location"] is None
                   or npc["location"] == state["location"]
                   or npc.get("activity", {}).get("status") != "awake"
                   or npc.get("activity_plan") or npc_travel.pending(state, nid)
                   or any(e["npc"] == nid and e["status"] == "scheduled"
                          for e in state.get("timed_detail_events", [])))
        if blocked:
            npc["offscreen_since"] = None
        elif npc["offscreen_since"] is None:
            npc["offscreen_since"] = state["time"]


def materialize(state, rules, request, npc_available, text):
    """Resolve ordinary off-screen movement at the current time.

    Consume already elapsed, uncommitted time once. This is an abstract
    relocation, not a detailed journey or an award of recovery.
    """
    if not rules.get("npc_contextual_presence") or not isinstance(request, dict) or set(request) != {"npc", "destination", "basis"}:
        raise ValueError("invalid contextual presence")
    nid, destination = request["npc"], request["destination"]
    if not isinstance(nid, str) or nid not in rules["npc_agendas"] or not isinstance(destination, str):
        raise ValueError("invalid contextual NPC or destination")
    npc = state["npcs"][nid]
    origin = npc["location"]
    since = npc.get("offscreen_since")
    if (not since or origin is None or origin == state["location"] or destination == origin
            or npc.get("activity_plan") or npc_travel.pending(state, nid)
            or not npc_available(state, rules, {"npc": nid, "location": origin})
            or any(e["npc"] == nid and e["status"] == "scheduled"
                   for e in state.get("timed_detail_events", []))):
        raise ValueError("no uninterrupted off-screen movement opportunity")
    if destination not in rules["npcs"][nid]["eligible_locations"]:
        raise ValueError("destination outside reviewed NPC locations")
    # Exclude gated edges: PC knowledge is not NPC knowledge.
    config = dict(rules["spatial"], edges=[e for e in rules["spatial"]["edges"]
                  if not e.get("requires_flags") and not e.get("opens") and not e.get("closes")])
    route = spatial.route(config, origin, destination, since, [])
    elapsed = (datetime.fromisoformat(state["time"]) - datetime.fromisoformat(since)).total_seconds()
    if not route or not route["seconds"] or route["seconds"] > elapsed:
        raise ValueError("insufficient off-screen travel time")
    if len(state["npc_travel"]) >= 128:
        raise ValueError("NPC travel record limit")
    basis = text(request["basis"], 240)
    state["npc_travel"].append({"npc": nid, "origin": origin, "destination": destination,
        "route": route, "at": since, "due": state["time"], "status": "completed",
        "resolved_at": state["time"], "basis": basis, "abstract": True})
    npc["location"] = destination
    npc["offscreen_since"] = None
