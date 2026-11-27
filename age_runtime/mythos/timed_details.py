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
    if op not in ("schedule", "cancel") or (set(request) != expected and not (op == "schedule" and set(request) == expected | {"objective"})):
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
    objective = objective_link(state, rules, npc, request)
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
                   "status": "scheduled", "basis": basis, **objective})


def objective_link(state, rules, npc, request):
    if "objective" not in request:
        return {}
    from age_runtime.mythos import npc_agency
    if not rules.get("npc_agency") or not npc_agency.active_objective(state, npc, request["objective"]):
        raise ValueError("activity requires own active objective")
    return {"objective": request["objective"]}


def test_config(rules, nid):
    cfg = rules.get("npc_native_test")
    if cfg and cfg["npc"] == nid:
        return cfg
    return rules.get("npc_agency", {}).get("examinations", {}).get(nid)

def native_test(state, rules, request, npc_available, local_entities, text):
    """Schedule a reviewed NPC-owned examination, not an arbitrary Test or effect."""
    required = {"id", "npc", "object", "basis"}
    if not isinstance(request, dict) or set(request) not in (required, required | {"objective"}):
        raise ValueError("invalid NPC native Test")
    eid, nid, oid = request["id"], request["npc"], request["object"]
    if not isinstance(eid, str) or not re.fullmatch(r"evt:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid NPC Test identity")
    cfg = test_config(rules, nid) if isinstance(nid, str) else None
    if not cfg or not isinstance(oid, str):
        raise ValueError("unsupported NPC Test actor or object")
    objective = objective_link(state, rules, nid, request)
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
                   "status": "scheduled", "basis": basis, **objective,
                   **({"work_seconds": 0} if rules.get("npc_task_continuity") else {}),
                   **({"object_revision": object_revision(state, oid), "task_history": []} if rules.get("npc_lifecycle") else {})})

def object_revision(state, oid):
    return [sum(1 for e in state.get(key, []) if e.get("id" if key != "object_actions" else "object") == oid)
            for key in ("detail_changes", "custody_transfers", "object_actions")]

def task_control(state, rules, request, npc_available, local_entities, text):
    if not rules.get("npc_lifecycle") or not isinstance(request, dict) or set(request) != {"operation", "id", "npc", "basis"}:
        raise ValueError("invalid NPC task control")
    op, eid, nid = request["operation"], request["id"], request["npc"]
    e = next((e for e in state["timed_detail_events"] if e["id"] == eid and e["npc"] == nid and e.get("authority") == "npc_native_test"), None)
    if not e or e["status"] not in ("scheduled", "interrupted"):
        raise ValueError("NPC task not controllable")
    basis = text(request["basis"], 240)
    history = e.setdefault("task_history", [])
    if len(history) >= 16:
        raise ValueError("NPC task control record limit")
    if op == "cancel":
        e.update(status="cancelled", cancelled_at=state["time"], cancellation_basis=basis)
    elif op == "resume":
        if e["status"] != "interrupted":
            raise ValueError("only interrupted task can resume")
        if "objective" in e:
            objective_link(state, rules, nid, e)
        npc = state["npcs"][nid]
        location = npc["location"]
        if location is None or location != e["location"] or not npc_available(state, rules, {"npc": nid, "location": location}):
            raise ValueError("task requires available NPC at original location")
        if any(other["status"] == "scheduled" and (other["npc"] == nid or other["object"] == e["object"]) for other in state["timed_detail_events"]):
            raise ValueError("conflicting pending event")
        cfg = test_config(rules, nid)
        obj = local_entities(dict(state, location=location)).get(e["object"])
        if (not obj or obj.get("custodian") != nid or obj.get("lifecycle", "intact") != "intact"
                or obj.get("properties", {}).get("appearance") != cfg["appearance"]
                or e["object_revision"] != object_revision(state, e["object"])):
            raise ValueError("task object changed; cannot resume prior work")
        remaining = cfg["minutes"]*60-e["work_seconds"]
        due = datetime.fromisoformat(state["time"]) + timedelta(seconds=remaining)
        if remaining <= 0 or due > datetime.fromisoformat(rules["end"]):
            raise ValueError("invalid remaining work or horizon")
        from age_runtime.mythos import npc_time
        npc_time.interrupt(state, nid, reason="task_resume")
        e.update(status="scheduled", due=due.isoformat(), resumed_at=state["time"])
    else:
        raise ValueError("unsupported task control")
    history.append({"operation": op, "at": state["time"], "basis": basis, "work_seconds": e["work_seconds"]})

def resolve_native_test(state, rules, e, obj, npc_available):
    cfg = test_config(rules, e["npc"])
    if rules.get("npc_task_continuity") and e.get("work_seconds") != cfg["minutes"] * 60:
        e.update(status="interrupted", interrupted_at=state["time"], interruption="insufficient_work")
        return
    npc = state["npcs"][e["npc"]]
    if rules.get("npc_lifecycle") and e["object_revision"] != object_revision(state, e["object"]):
        e["status"] = "prerequisite_unmet"
        return
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
    if rules.get("npc_agency") and "significance" in cfg:
        from age_runtime.mythos import npc_agency
        inputs, audit = npc_agency.modifiers(state, rules, e["npc"], spec, cfg["significance"])
        args = dict(inputs, tn=spec["tn"])
        npc["favor"] -= inputs["favor"]
    result = dxd.test(f"{state['seed']}:npc-test:{e['npc']}:{e['object']}", **args)
    e.update(status="completed", test={"inputs": args, "gathered": gathered,
             "condition_penalty_dice": condition, "result": result,
             **({"resource_audit": audit} if rules.get("npc_agency") and "significance" in cfg else {})},
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
        if "objective" in e:
            from age_runtime.mythos import npc_agency
            if not npc_agency.active_objective(state, e["npc"], e["objective"]):
                e.update(status="cancelled", cancelled_at=state["time"], cancellation_basis="Objective no longer active")
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
