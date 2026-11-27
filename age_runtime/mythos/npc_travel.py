"""Bounded NPC travel using authored point-map routes and the shared clock."""
from datetime import datetime, timedelta
import copy
from age_runtime.mythos import spatial, npc_time, continuity

def pending(state, nid):
    return next((e for e in state.get("npc_travel", []) if e["npc"] == nid and e["status"] == "traveling"), None)

def record(state, rules, request, npc_available, text):
    if not rules.get("npc_travel") or not isinstance(request, dict) or set(request) != {"npc", "destination", "basis"}:
        raise ValueError("invalid NPC travel")
    nid, destination = request["npc"], request["destination"]
    if not isinstance(nid, str) or nid not in state["npcs"] or not isinstance(destination, str):
        raise ValueError("invalid traveler or destination")
    npc, cfg = state["npcs"][nid], rules["npcs"][nid]
    origin = npc["location"]
    if origin is None or not npc_available(state, rules, {"npc": nid, "location": origin}):
        raise ValueError("travel requires available anchored NPC")
    if destination == origin or destination not in cfg.get("eligible_locations", [origin]):
        raise ValueError("destination outside reviewed NPC locations")
    if any(e["npc"] == nid and e["status"] == "scheduled" for e in state.get("timed_detail_events", [])):
        raise ValueError("NPC has conflicting pending event")
    # Pilot permits only ungated routes: PC-earned route knowledge is not NPC knowledge.
    config = dict(rules["spatial"], edges=[e for e in rules["spatial"]["edges"]
                  if not e.get("requires_flags") and not e.get("opens") and not e.get("closes")])
    route = spatial.route(config, origin, destination, state["time"], [])
    if not route or not route["seconds"]:
        raise ValueError("no reviewed NPC route")
    due = datetime.fromisoformat(state["time"]) + timedelta(seconds=route["seconds"])
    if due > datetime.fromisoformat(rules["end"]) or len(state["npc_travel"]) >= 128:
        raise ValueError("NPC travel horizon or record limit")
    basis = text(request["basis"], 240)
    npc_time.interrupt(state, nid)
    state["npc_travel"].append({"npc": nid, "origin": origin, "destination": destination,
        "route": route, "at": state["time"], "due": due.isoformat(), "status": "traveling", "basis": basis})

def next_boundary(state, cursor, finish):
    return min([finish] + [datetime.fromisoformat(e["due"]) for e in state.get("npc_travel", [])
                if e["status"] == "traveling" and cursor < datetime.fromisoformat(e["due"]) <= finish])

def resolve(state, rules, cursor):
    for e in state.get("npc_travel", []):
        if e["status"] != "traveling" or datetime.fromisoformat(e["due"]) > cursor:
            continue
        npc, cfg = state["npcs"][e["npc"]], rules["npcs"][e["npc"]]
        if (npc["location"] != e["origin"] or npc["activity"]["status"] != "awake"
                or continuity.blocked(state, cfg) or not all(f in state["flags"] for f in cfg.get("requires_flags", []))):
            e["status"] = "interrupted"
        else:
            npc["location"] = e["destination"]
            e["status"] = "completed"
        e["resolved_at"] = cursor.isoformat()

def projection(state):
    return copy.deepcopy(state.get("npc_travel", [])[-12:])
