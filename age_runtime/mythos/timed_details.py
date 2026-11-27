"""Bounded reviewed narrative event: an NPC tends their incidental object.

Scheduling is not fulfillment. Resolve once at the native time boundary;
no PC-presence assumption, hidden clue, inventory or mechanical effect.
"""
from datetime import datetime, timedelta
import copy
import re
from age_runtime.core import dxd, dxd_conditions, dxd_modifiers

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
    if any(e.get("authority") in ("npc_initiative", "npc_native_test") and e["status"] == "scheduled" and (e["object"] == oid or (a and e["npc"] == a["npc"])) for e in ledger):
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

def native_test(state, rules, request, npc_available, local_entities, text):
    """Schedule a reviewed NPC-owned examination, not an arbitrary Test or effect."""
    cfg = rules.get("npc_native_test")
    if not cfg or not isinstance(request, dict) or set(request) != {"id", "npc", "object", "basis"}:
        raise ValueError("invalid NPC native Test")
    eid, nid, oid = request["id"], request["npc"], request["object"]
    if not isinstance(eid, str) or not re.fullmatch(r"evt:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid NPC Test identity")
    if nid != cfg["npc"] or not isinstance(oid, str):
        raise ValueError("unsupported NPC Test actor or object")
    npc = state["npcs"][nid]
    location = npc["location"]
    if location is None or not npc_available(state, rules, {"npc": nid, "location": location}):
        raise ValueError("NPC Test requires available anchored actor")
    ledger = state["timed_detail_events"]
    if len(ledger) >= 64 or any(e["id"] == eid or
            (e.get("authority") == "npc_native_test" and e["npc"] == nid and e["object"] == oid) or
            (e["status"] == "scheduled" and (e["npc"] == nid or e["object"] == oid)) for e in ledger):
        raise ValueError("duplicate or conflicting NPC Test")
    obj = local_entities(dict(state, location=location)).get(oid)
    if not obj or obj["kind"] != "object" or obj.get("custodian") != nid or obj.get("lifecycle", "intact") != "intact":
        raise ValueError("NPC Test requires intact object in own custody")
    if obj.get("properties", {}).get("appearance") != cfg["appearance"]:
        raise ValueError("NPC Test requires reviewed visible marking")
    due = datetime.fromisoformat(state["time"]) + timedelta(minutes=cfg["minutes"])
    if due > datetime.fromisoformat(rules["end"]):
        raise ValueError("NPC Test exceeds scenario horizon")
    from age_runtime.mythos import npc_time
    basis = text(request["basis"], 240)
    npc_time.interrupt(state, nid)
    ledger.append({"id": eid, "object": oid, "permission": None, "npc": nid,
                   "authority": "npc_native_test", "location": location,
                   "scheduled_at": state["time"], "due": due.isoformat(),
                   "status": "scheduled", "basis": basis})

def resolve_native_test(state, rules, e, obj, npc_available):
    cfg = rules["npc_native_test"]
    npc = state["npcs"][e["npc"]]
    if (not obj or obj["kind"] != "object" or obj.get("custodian") != e["npc"]
            or obj.get("lifecycle", "intact") != "intact"
            or obj.get("properties", {}).get("appearance") != cfg["appearance"]
            or npc["location"] != e["location"]
            or not npc_available(state, rules, {"npc": e["npc"], "location": e["location"]})):
        e["status"] = "prerequisite_unmet"
        return
    spec = cfg["test"]
    gathered = dxd_modifiers.gather(npc["dxd_attributes"], npc.get("skills", {}),
                                   npc.get("dxd_traits", {}), spec, player=False)
    mods = dxd_modifiers.totals(gathered)
    condition = dxd_conditions.penalty_dice(npc["concerns"], decision=spec.get("decision", False))
    args = {"tn": spec["tn"], "dm": mods["dm"], "bonus": mods["bonus"],
            "penalty": mods["penalty"] + condition}
    result = dxd.test(f"{state['seed']}:npc-test:{e['npc']}:{e['object']}", **args)
    e.update(status="completed", test={"inputs": args, "gathered": gathered,
             "condition_penalty_dice": condition, "result": result},
             assessment=cfg["success"] if result["passed"] else cfg["failure"])

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
        if e.get("authority") == "npc_native_test":
            resolve_native_test(state, rules, e, obj, npc_available)
            continue
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
