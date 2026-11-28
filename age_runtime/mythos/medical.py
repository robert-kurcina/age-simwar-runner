"""Reviewed ten-minute bandaging, using the existing timed event queue.

Only the Bodypoint component is implemented; no Hitpoint pool exists yet.
Supplies are explicit scenario allocations, not inferred from ambience.
"""
from datetime import datetime, timedelta
from age_runtime.core import dxd_injury, dxd_hitpoints
from random import Random


def pending(state):
    return next((e for e in state.get("timed_detail_events", [])
                 if e.get("authority") == "medical_bandage" and e["status"] == "scheduled"), None)


def eligible(state, rules, nid, location, npc_available):
    npc = state["npcs"][nid]
    return (npc["location"] == location and state["location"] == location
            and npc_available(state, rules, {"npc": nid, "location": location})
            and not npc.get("activity_plan"))


def schedule(state, rules, request, npc_available, text):
    cfg = rules.get("medical_bandaging")
    injury = state["dxd"].get("injury")
    if not cfg or not injury or state["ending"] or not isinstance(request, dict) or set(request) != {"npc", "basis"}:
        raise ValueError("medical bandaging unavailable")
    nid = request["npc"]
    if not isinstance(nid, str) or nid not in cfg["caregivers"]:
        raise ValueError("caregiver not reviewed")
    pool = state["dxd"].get("hitpoints")
    if (not injury["injury"] and not (pool and pool["current"] < pool["capacity"])) or dxd_injury.projection(injury)["status"] == "dead":
        raise ValueError("no treatable living patient")
    if not eligible(state, rules, nid, state["location"], npc_available):
        raise ValueError("caregiver unavailable")
    ledger = state["timed_detail_events"]
    if pending(state) or len(ledger) >= 64 or any(e["npc"] == nid and e["status"] == "scheduled" for e in ledger):
        raise ValueError("conflicting treatment or caregiver commitment")
    if state["medical_supplies"].get(nid, 0) < 1:
        raise ValueError("no reviewed bandage supply")
    due = datetime.fromisoformat(state["time"]) + timedelta(minutes=10)
    if due > datetime.fromisoformat(rules["end"]):
        raise ValueError("treatment exceeds scenario horizon")
    basis = text(request["basis"], 240)
    # Consume at commencement; an interrupted application does not refund it.
    state["medical_supplies"][nid] -= 1
    ledger.append({"id": f"medical:{len(ledger)}", "npc": nid, "object": None,
                   "permission": None, "authority": "medical_bandage",
                   "location": state["location"], "scheduled_at": state["time"],
                   "due": due.isoformat(), "status": "scheduled", "basis": basis})


def interrupt_unavailable(state, rules, npc_available, *, engaged=None, moving=False):
    event = pending(state)
    if event and (moving or engaged == event["npc"] or not eligible(state, rules, event["npc"], event["location"], npc_available)
                  or dxd_injury.projection(state["dxd"]["injury"])["status"] == "dead"):
        event.update(status="interrupted", interrupted_at=state["time"])


def resolve(state, rules, event, npc_available):
    injury = state["dxd"]["injury"]
    if not eligible(state, rules, event["npc"], event["location"], npc_available) or dxd_injury.projection(injury)["status"] == "dead":
        event["status"] = "prerequisite_unmet"
        return
    before = injury["injury"]
    injury["injury"] = max(0, before - 1)
    # Dying remains latched until Bodypoints reach zero, per dedicated rule.
    if injury["injury"] <= injury["capacity"]:
        injury["dying_seconds"] = 0
        injury["dying_latched"] = False
    pool = state["dxd"].get("hitpoints")
    if pool:
        restored = dxd_hitpoints.recover(pool, Random(f"{state['seed']}:{event['id']}:bandage").randint(1, 6))
        event["hitpoints_restored"] = restored
    event.update(status="completed", bodypoints_restored=before - injury["injury"])
    state["observations"].append("Bandaging has restored one Bodypoint." if before else "Bandaging is complete.")
