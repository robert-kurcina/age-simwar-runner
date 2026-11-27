"""Major NPC activity on the existing fictional clock; no independent scheduler."""
from datetime import datetime, timedelta
import copy
from age_runtime.core import dxd_conditions, dxd_morale

def initialize(state, rules):
    cfg = rules.get("npc_temporal")
    if not cfg:
        return
    if not rules.get("activity") or set(cfg["initial_awake_seconds"]) != set(state["npcs"]):
        raise ValueError("NPC temporal coverage mismatch")
    for nid, npc in state["npcs"].items():
        npc["activity"] = dxd_conditions.activity_initial(npc["dxd_attributes"], cfg["initial_awake_seconds"][nid])
        npc["morale"] = dxd_morale.initial()
        npc["activity_plan"] = None
    state["npc_activity_history"] = []

def record(state, rules, request, npc_available, text):
    if not rules.get("npc_temporal") or not isinstance(request, dict) or set(request) != {"npc", "mode", "safe", "minutes", "basis"}:
        raise ValueError("invalid NPC activity")
    nid, mode, safe, minutes = (request[k] for k in ("npc", "mode", "safe", "minutes"))
    if (not isinstance(nid, str) or nid not in state["npcs"]
            or state["npcs"][nid]["location"] != state["location"]
            or not npc_available(state, rules, {"npc": nid, "location": state["location"]})):
        raise ValueError("NPC activity requires available local participant")
    if mode not in ("active", "quiet", "rest", "low_energy") or type(safe) is not bool or (safe and mode == "active"):
        raise ValueError("unsupported NPC activity mode or safety")
    if type(minutes) is not int or not 1 <= minutes <= 60:
        raise ValueError("NPC activity interval must be 1 to 60 minutes")
    until = datetime.fromisoformat(state["time"]) + timedelta(minutes=minutes)
    if until > datetime.fromisoformat(rules["end"]):
        raise ValueError("NPC activity exceeds horizon")
    npc = state["npcs"][nid]
    if npc["activity_plan"] is not None:
        raise ValueError("NPC activity already planned; interrupt through interaction")
    if len(state["npc_activity_history"]) >= 256:
        raise ValueError("NPC activity record limit")
    event = {"npc": nid, "mode": mode, "safe": safe, "at": state["time"],
             "until": until.isoformat(), "location": state["location"],
             "basis": text(request["basis"], 240), "turn": state["turn"]}
    npc["activity_plan"] = copy.deepcopy(event)
    state["npc_activity_history"].append(event)

def interrupt(state, nid):
    if nid in state["npcs"] and "activity" in state["npcs"][nid]:
        npc = state["npcs"][nid]
        npc["activity_plan"] = None
        clock = npc.get("activity")
        if clock and clock["status"] == "awake":
            clock["remainder"].clear()
            clock["activity"] = "active"

def next_boundary(state, cursor, finish):
    for npc in state["npcs"].values():
        plan = npc.get("activity_plan")
        if plan:
            end = datetime.fromisoformat(plan["until"])
            if cursor < end < finish:
                finish = end
    return finish

def advance(state, rules, seconds):
    if not rules.get("npc_temporal") or not seconds:
        return
    # No assumed safe rest during unknown off-screen activity. The default
    # awake assumption is explicit scenario policy, not an occupation schedule.
    end = datetime.fromisoformat(state["time"])
    for nid, npc in sorted(state["npcs"].items()):
        clock, concerns, attrs = npc["activity"], npc["concerns"], npc["dxd_attributes"]
        seed = f"{state['seed']}:npc:{nid}"
        remaining = seconds
        while remaining:
            before = dxd_conditions.degrees(concerns)["stress"]
            if clock["status"] == "asleep":
                span = min(remaining, clock["required_sleep_seconds"] - clock["sleep_seconds"])
                dxd_conditions.advance_activity(concerns, clock, span, "sleep", seed=seed, attributes=attrs)
                remaining -= span
                if clock["sleep_seconds"] >= clock["required_sleep_seconds"]:
                    dxd_conditions.wake(concerns, clock, attrs, seed=seed)
                dxd_morale.calm(npc["morale"], stress_degrees_removed=before-dxd_conditions.degrees(concerns)["stress"])
                continue
            plan = npc["activity_plan"]
            cursor = end - timedelta(seconds=remaining)
            if plan and (npc["location"] != plan["location"] or cursor >= datetime.fromisoformat(plan["until"])):
                npc["activity_plan"] = plan = None
            span = min(remaining, int((datetime.fromisoformat(plan["until"])-cursor).total_seconds())) if plan else remaining
            mode, safe = (plan["mode"], plan["safe"]) if plan else ("active", False)
            actual = dxd_conditions.advance_activity(concerns, clock, span, mode, safe=safe, seed=seed, attributes=attrs)
            remaining -= actual
            dxd_morale.calm(npc["morale"], safe=safe, stress_degrees_removed=before-dxd_conditions.degrees(concerns)["stress"])
            if clock["pending_sleep_seconds"] == 0:
                npc["activity_plan"] = None
                dxd_conditions.begin_sleep(concerns, clock, attrs)
            elif actual != span:
                raise ValueError("unexpected NPC activity interruption")
        if npc["activity_plan"] and end >= datetime.fromisoformat(npc["activity_plan"]["until"]):
            npc["activity_plan"] = None

def projection(state, participants):
    return {nid: {"activity": copy.deepcopy(state["npcs"][nid]["activity"]),
                  "plan": copy.deepcopy(state["npcs"][nid]["activity_plan"]),
                  "morale": copy.deepcopy(state["npcs"][nid]["morale"])}
            for nid in sorted(participants) if "activity" in state["npcs"][nid]}
