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
    if any(e.get("authority") == "npc_initiative" and e["status"] == "scheduled" and (e["object"] == oid or (a and e["npc"] == a["npc"])) for e in ledger):
        raise ValueError("conflicting pending NPC initiative")
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
            or not obj or obj["kind"] != "object" or obj.get("lifecycle", "intact") != "intact" or obj.get("custodian") != a["npc"]
            or not npc_available(state, rules, {"npc": a["npc"], "location": state["location"]})
            or obj.get("properties", {}).get("condition") != cfg["before"]):
        raise ValueError("event requires current NPC commitment and matching object condition")
    ledger.append({"id": eid, "object": oid, "permission": aid, "npc": a["npc"],
                   "location": state["location"], "scheduled_at": state["time"],
                   "due": due.isoformat(), "status": "scheduled",
                   "basis": text(request["basis"], 240)})

def initiative(state, rules, request, npc_available, local_entities, text):
    """Reviewed autonomous mundane action; the existing event queue owns execution."""
    cfg = rules.get("npc_initiative")
    if not cfg or not isinstance(request, dict):
        raise ValueError("NPC initiative unavailable")
    op = request.get("operation")
    expected = {"operation", "id", "npc", "object", "delay_minutes", "basis"} if op == "schedule" else {"operation", "id", "npc", "basis"}
    if op not in ("schedule", "cancel") or set(request) != expected:
        raise ValueError("invalid initiative fields")
    eid, npc = request["id"], request["npc"]
    if not isinstance(eid, str) or not re.fullmatch(r"evt:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid initiative identity")
    if not isinstance(npc, str) or npc not in state["npcs"]:
        raise ValueError("unknown NPC")
    location = state["npcs"][npc]["location"]
    if location is None or not npc_available(state, rules, {"npc": npc, "location": location}):
        raise ValueError("initiative requires available anchored NPC")
    ledger = state["timed_detail_events"]
    existing = next((e for e in ledger if e["id"] == eid), None)
    basis = text(request["basis"], 240)
    if op == "cancel":
        if not existing or existing.get("authority") != "npc_initiative" or existing["npc"] != npc or existing["status"] != "scheduled":
            raise ValueError("initiative not pending for NPC")
        existing.update(status="cancelled", cancelled_at=state["time"], cancellation_basis=basis)
        return
    if existing or len(ledger) >= 64:
        raise ValueError("duplicate event or record limit")
    oid, delay = request["object"], request["delay_minutes"]
    if not isinstance(oid, str) or type(delay) is not int or delay not in cfg["delays_minutes"]:
        raise ValueError("invalid initiative object or delay")
    if any(e["status"] == "scheduled" and (e["object"] == oid or e["npc"] == npc) for e in ledger):
        raise ValueError("conflicting pending NPC event")
    due = datetime.fromisoformat(state["time"]) + timedelta(minutes=delay)
    if due > datetime.fromisoformat(rules["end"]):
        raise ValueError("initiative outside scenario horizon")
    obj = local_entities(dict(state, location=location)).get(oid)
    if (not obj or obj["kind"] != "object" or obj.get("custodian") != npc
            or obj.get("lifecycle", "intact") != "intact"
            or obj.get("properties", {}).get("condition") != cfg["before"]):
        raise ValueError("initiative requires matching intact NPC-held object")
    ledger.append({"id": eid, "object": oid, "permission": None, "npc": npc,
                   "authority": "npc_initiative", "location": location,
                   "scheduled_at": state["time"], "due": due.isoformat(),
                   "status": "scheduled", "basis": basis})

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
        independent = e.get("authority") == "npc_initiative"
        effect = rules["npc_initiative"] if independent else cfg
        authorized = independent or (a and a["status"] == "active")
        eligible = (authorized and obj and obj.get("lifecycle", "intact") == "intact"
                    and obj.get("custodian") == e["npc"]
                    and state["npcs"][e["npc"]]["location"] == e["location"]
                    and npc_available(state, rules, {"npc": e["npc"], "location": e["location"]})
                    and obj.get("properties", {}).get("condition") == effect["before"])
        if not eligible:
            e["status"] = "prerequisite_unmet"
            continue
        changes = state["detail_changes"]
        # Maintain the same bounded property history; no other effects.
        if len(changes) >= 512:
            e["status"] = "record_limit"
            continue
        changes.append({"change_id": len(changes) + 1, "id": e["object"],
                        "property": "condition", "before": effect["before"],
                        "after": effect["after"], "sequence": len(state["history"]),
                        "basis": e["basis"], "turn": state["turn"], "at": e["due"],
                        "location": e["location"], "source": "timed_event",
                        "event": e["id"]})
        e["status"] = "completed"

def projection(state):
    return copy.deepcopy(state.get("timed_detail_events", []))
