"""Bounded reviewed narrative event: an NPC tends their incidental object.

Scheduling is not fulfillment. Resolve once at the native time boundary;
no PC-presence assumption, hidden clue, inventory or mechanical effect.
"""
from datetime import datetime, timedelta
import copy
import re

def record(state, rules, request, npc_available, local_entities, text):
    cfg = rules.get("timed_detail_event")
    if not cfg or not isinstance(request, dict) or set(request) != {"id", "object", "permission", "delay_minutes", "basis"}:
        raise ValueError("invalid timed detail event")
    from age_runtime.mythos import agreements
    eid, oid, aid = request["id"], request["object"], request["permission"]
    if not isinstance(eid, str) or not re.fullmatch(r"evt:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid event identity")
    if not isinstance(oid, str) or not isinstance(aid, str):
        raise ValueError("invalid event references")
    ledger = state["timed_detail_events"]
    if len(ledger) >= 64 or any(e["id"] == eid or e["permission"] == aid for e in ledger):
        raise ValueError("duplicate event or record limit")
    a = agreements.project(state).get(aid)
    obj = local_entities(state).get(oid)
    delay = request["delay_minutes"]
    if type(delay) is not int or delay not in cfg["delays_minutes"]:
        raise ValueError("unsupported delay")
    due = datetime.fromisoformat(state["time"]) + timedelta(minutes=delay)
    if due > datetime.fromisoformat(rules["end"]):
        raise ValueError("event outside scenario horizon")
    if (not a or a["kind"] != "commitment" or a["issuer"] != a["npc"]
            or a["status"] != "active" or a["condition"] is not None
            or a["location"] != state["location"] or a["turn"] != state["turn"]
            or not obj or obj["kind"] != "object" or obj.get("custodian") != a["npc"]
            or not npc_available(state, rules, {"npc": a["npc"], "location": state["location"]})
            or obj.get("properties", {}).get("condition") != cfg["before"]):
        raise ValueError("event requires current NPC commitment and matching object condition")
    ledger.append({"id": eid, "object": oid, "permission": aid, "npc": a["npc"],
                   "location": state["location"], "scheduled_at": state["time"],
                   "due": due.isoformat(), "status": "scheduled",
                   "basis": text(request["basis"], 240)})

def next_boundary(state, cursor, finish):
    due = [datetime.fromisoformat(e["due"]) for e in state.get("timed_detail_events", [])
           if e["status"] == "scheduled" and cursor < datetime.fromisoformat(e["due"]) <= finish]
    return min(due) if due else finish

def resolve(state, rules, elapsed, npc_available, local_entities):
    from age_runtime.mythos import agreements
    cfg = rules.get("timed_detail_event")
    if not cfg:
        return
    for e in sorted(state.get("timed_detail_events", []), key=lambda x: (x["due"], x["id"])):
        if e["status"] != "scheduled" or datetime.fromisoformat(e["due"]) > elapsed:
            continue
        # Evaluate NPC and object at event location, not at the PC's
        # possibly in-transit anchor. Never mutate the real PC location.
        scope = dict(state, location=e["location"])
        obj = local_entities(scope).get(e["object"])
        a = agreements.project(state).get(e["permission"])
        eligible = (a and a["status"] == "active" and obj
                    and obj.get("custodian") == e["npc"]
                    and state["npcs"][e["npc"]]["location"] == e["location"]
                    and npc_available(state, rules, {"npc": e["npc"], "location": e["location"]})
                    and obj.get("properties", {}).get("condition") == cfg["before"])
        if not eligible:
            e["status"] = "prerequisite_unmet"
            continue
        changes = state["detail_changes"]
        # Maintain the same bounded property history; no other effects.
        if len(changes) >= 512:
            e["status"] = "record_limit"
            continue
        changes.append({"change_id": len(changes) + 1, "id": e["object"],
                        "property": "condition", "before": cfg["before"],
                        "after": cfg["after"], "sequence": len(state["history"]),
                        "basis": e["basis"], "turn": state["turn"], "at": e["due"],
                        "location": e["location"], "source": "timed_event",
                        "event": e["id"]})
        e["status"] = "completed"

def projection(state):
    return copy.deepcopy(state.get("timed_detail_events", []))
