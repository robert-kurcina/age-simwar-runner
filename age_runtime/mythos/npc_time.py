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
        if rules.get("npc_lifecycle"):
            npc["daily_schedule"] = []
            npc["last_awaken_attempt"] = None
            npc["morning_until"] = None
    state["npc_activity_history"] = []

def record(state, rules, request, npc_available, text):
    if not rules.get("npc_temporal") or not isinstance(request, dict) or set(request) != {"npc", "mode", "safe", "minutes", "basis"}:
        raise ValueError("invalid NPC activity")
    nid, mode, safe, minutes = (request[k] for k in ("npc", "mode", "safe", "minutes"))
    if (not isinstance(nid, str) or nid not in state["npcs"]
            or state["npcs"][nid]["location"] != state["location"]
            or not npc_available(state, rules, {"npc": nid, "location": state["location"]})):
        raise ValueError("NPC activity requires available local participant")
    if mode not in (("active", "quiet", "rest", "low_energy", "restorative") if rules.get("npc_lifecycle") else ("active", "quiet", "rest", "low_energy")) or type(safe) is not bool or (safe and mode == "active"):
        raise ValueError("unsupported NPC activity mode or safety")
    if type(minutes) is not int or not 1 <= minutes <= (480 if rules.get("npc_lifecycle") else 60):
        raise ValueError("NPC activity interval outside supported bounds")
    until = datetime.fromisoformat(state["time"]) + timedelta(minutes=minutes)
    if until > datetime.fromisoformat(rules["end"]):
        raise ValueError("NPC activity exceeds horizon")
    npc = state["npcs"][nid]
    if npc["activity_plan"] is not None or pending_work(state, nid):
        raise ValueError("NPC activity already planned; interrupt through interaction")
    if len(state["npc_activity_history"]) >= 256:
        raise ValueError("NPC activity record limit")
    event = {"npc": nid, "mode": mode, "safe": safe, "at": state["time"],
             "until": until.isoformat(), "location": state["location"],
             "basis": text(request["basis"], 240), "turn": state["turn"]}
    npc["activity_plan"] = copy.deepcopy(event)
    state["npc_activity_history"].append(event)

def lifecycle(state, rules, request, npc_available, text):
    if not rules.get("npc_lifecycle") or not isinstance(request, dict):
        raise ValueError("NPC lifecycle unavailable")
    op = request.get("operation")
    fields = {"operation", "npc", "basis"}
    if op == "schedule":
        fields |= {"windows"}
    elif op == "duress":
        fields |= {"minutes", "interval_minutes"}
    elif op not in ("sleep", "awaken", "end_activity"):
        raise ValueError("unsupported NPC lifecycle operation")
    if set(request) != fields:
        raise ValueError("invalid NPC lifecycle fields")
    nid = request["npc"]
    if not isinstance(nid, str) or nid not in state["npcs"]:
        raise ValueError("unknown NPC")
    npc = state["npcs"][nid]
    location, clock = npc["location"], npc["activity"]
    if location is None:
        raise ValueError("NPC lifecycle requires established anchor")
    now = datetime.fromisoformat(state["time"])
    basis = text(request["basis"], 240)
    history = state["npc_activity_history"]
    if len(history) >= 256:
        raise ValueError("NPC activity record limit")
    entry = {"npc": nid, "operation": op, "at": state["time"], "location": location,
             "basis": basis, "turn": state["turn"]}
    if op == "awaken":
        # An actual local attempt, not a remote command to become awake.
        if location != state["location"] or clock["status"] != "asleep" or clock["sleep_seconds"] < 3600:
            raise ValueError("awakening requires local sleeping NPC and minimum sleep")
        previous = npc["last_awaken_attempt"]
        if previous and (now - datetime.fromisoformat(previous)).total_seconds() < 60:
            raise ValueError("awakening checks require one minute between attempts")
        before = dxd_conditions.degrees(npc["concerns"])["stress"]
        npc["last_awaken_attempt"] = state["time"]
        woke = dxd_conditions.wake(npc["concerns"], clock, npc["dxd_attributes"],
                                   seed=f"{state['seed']}:npc:{nid}", forced=True)
        entry["woke"] = woke
        if woke:
            mark_morning(npc, now)
            dxd_morale.calm(npc["morale"], stress_degrees_removed=before-dxd_conditions.degrees(npc["concerns"])["stress"])
    else:
        if not npc_available(state, rules, {"npc": nid, "location": location}):
            raise ValueError("NPC lifecycle requires available anchored NPC")
        if op == "sleep":
            interrupt(state, nid, reason="voluntary_sleep")
            dxd_conditions.begin_sleep(npc["concerns"], clock, npc["dxd_attributes"])
            npc["morning_until"] = None
            npc["last_awaken_attempt"] = None
            entry["required_sleep_seconds"] = clock["required_sleep_seconds"]
        elif op == "end_activity":
            if npc["activity_plan"] is None:
                raise ValueError("no explicit activity to end")
            interrupt(state, nid, reason="activity_ended")
        elif op == "schedule":
            windows = request["windows"]
            if not isinstance(windows, list) or len(windows) > 4:
                raise ValueError("schedule requires zero to four daily windows")
            validated = []
            for w in windows:
                if not isinstance(w, dict) or set(w) != {"start_minute", "end_minute", "mode", "label"}:
                    raise ValueError("invalid schedule window")
                start, end = w["start_minute"], w["end_minute"]
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= 1440 or end-start > 720:
                    raise ValueError("invalid same-day occupational window")
                if w["mode"] not in ("active", "low_energy"):
                    raise ValueError("occupational mode must be active or low_energy")
                if any(start < v["end_minute"] and end > v["start_minute"] for v in validated):
                    raise ValueError("overlapping occupational windows")
                validated.append({"start_minute": start, "end_minute": end, "mode": w["mode"],
                                  "label": text(w["label"], 120), "location": location})
            npc["daily_schedule"] = sorted(validated, key=lambda v: v["start_minute"])
            entry["windows"] = copy.deepcopy(npc["daily_schedule"])
        else:
            minutes, interval = request["minutes"], request["interval_minutes"]
            if type(minutes) is not int or not 1 <= minutes <= 480 or type(interval) is not int or interval not in (1, 10, 60):
                raise ValueError("invalid sustained environmental Stress interval")
            if npc["activity_plan"] or pending_work(state, nid):
                raise ValueError("NPC already has an explicit activity")
            until = now + timedelta(minutes=minutes)
            if until > datetime.fromisoformat(rules["end"]):
                raise ValueError("activity exceeds scenario horizon")
            entry.update(mode="active", safe=False, until=until.isoformat(),
                         stress_interval_seconds=interval*60)
            npc["activity_plan"] = copy.deepcopy(entry)
            npc["activity_plan"]["exposure_seconds"] = 0
    history.append(entry)

def mark_morning(npc, at):
    if "morning_until" in npc:
        from age_runtime.core import dxd
        minutes = max(1, 10 + dxd.attribute_dm(npc["dxd_attributes"]["FOR"]))
        npc["morning_until"] = (at + timedelta(minutes=minutes)).isoformat()

def occupational_window(npc, at):
    minute = at.hour*60 + at.minute
    return next((w for w in npc.get("daily_schedule", []) if w["location"] == npc["location"]
                 and w["start_minute"] <= minute < w["end_minute"]), None)

def pending_work(state, nid):
    return next((e for e in state.get("timed_detail_events", [])
                 if e["npc"] == nid and e.get("authority") == "npc_native_test"
                 and e["status"] == "scheduled" and "work_seconds" in e), None)

def interrupt_work(state, nid, at, reason):
    task = pending_work(state, nid)
    if task:
        task.update(status="interrupted", interrupted_at=at, interruption=reason)
        if "task_history" in task:
            task["task_history"].append({"operation": "interrupt", "at": at, "reason": reason, "work_seconds": task["work_seconds"]})

def interrupt(state, nid, reason="interaction"):
    interrupt_work(state, nid, state["time"], reason)
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
        if "daily_schedule" not in npc:
            continue
        clock = npc["activity"]
        if clock["status"] == "asleep":
            wake = cursor + timedelta(seconds=clock["required_sleep_seconds"]-clock["sleep_seconds"])
            if cursor < wake < finish:
                finish = wake
        elif clock["pending_sleep_seconds"]:
            onset = cursor + timedelta(seconds=clock["pending_sleep_seconds"])
            if cursor < onset < finish:
                finish = onset
        midnight = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        for day in (midnight, midnight + timedelta(days=1)):
            for w in npc["daily_schedule"]:
                for minute in (w["start_minute"], w["end_minute"]):
                    boundary = day + timedelta(minutes=minute)
                    if cursor < boundary < finish:
                        finish = boundary
    return finish

def advance(state, rules, seconds, engaged=None):
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
                interrupt_work(state, nid, (end - timedelta(seconds=remaining)).isoformat(), "sleep")
                span = min(remaining, clock["required_sleep_seconds"] - clock["sleep_seconds"])
                dxd_conditions.advance_activity(concerns, clock, span, "sleep", seed=seed, attributes=attrs)
                remaining -= span
                if clock["sleep_seconds"] >= clock["required_sleep_seconds"]:
                    dxd_conditions.wake(concerns, clock, attrs, seed=seed)
                    mark_morning(npc, end - timedelta(seconds=remaining))
                dxd_morale.calm(npc["morale"], stress_degrees_removed=before-dxd_conditions.degrees(concerns)["stress"])
                continue
            plan = npc["activity_plan"]
            cursor = end - timedelta(seconds=remaining)
            if plan and (npc["location"] != plan["location"] or cursor >= datetime.fromisoformat(plan["until"])):
                npc["activity_plan"] = plan = None
            span = min(remaining, int((datetime.fromisoformat(plan["until"])-cursor).total_seconds())) if plan else remaining
            traveling = next((e for e in state.get("npc_travel", []) if e["npc"] == nid and e["status"] == "traveling"), None)
            task = pending_work(state, nid)
            window = occupational_window(npc, cursor)
            mode, safe = (plan["mode"], plan["safe"]) if plan else (
                "travel" if traveling else "active" if task or nid == engaged else window["mode"] if window else "active", False)
            exposure = plan.get("stress_interval_seconds") if plan else None
            if exposure:
                span = min(span, exposure - plan["exposure_seconds"] % exposure)
            if traveling and rules.get("npc_lifecycle"):
                span = min(span, 600 - traveling.get("walk_seconds", 0) % 600)
            if task and (mode != "active" or npc["location"] != task["location"]):
                interrupt_work(state, nid, cursor.isoformat(), "activity_changed")
                task = None
            actual = dxd_conditions.advance_activity(concerns, clock, span, mode, safe=safe, seed=seed, attributes=attrs)
            if task:
                task["work_seconds"] += actual
            if exposure:
                prior = plan["exposure_seconds"]
                plan["exposure_seconds"] += actual
                dxd_conditions.add(concerns, stress=plan["exposure_seconds"]//exposure-prior//exposure)
                dxd_conditions.refresh_sleep_limit(concerns, clock, attrs)
            if traveling and rules.get("npc_lifecycle"):
                prior = traveling.get("walk_seconds", 0)
                traveling["walk_seconds"] = prior + actual
                dxd_conditions.add(concerns, fatigue=traveling["walk_seconds"]//600-prior//600)
                dxd_conditions.refresh_sleep_limit(concerns, clock, attrs)
            remaining -= actual
            dxd_morale.calm(npc["morale"], safe=safe, stress_degrees_removed=before-dxd_conditions.degrees(concerns)["stress"])
            if clock["pending_sleep_seconds"] == 0:
                npc["activity_plan"] = None
                dxd_conditions.begin_sleep(concerns, clock, attrs)
                if "morning_until" in npc:
                    npc["morning_until"] = None
                    npc["last_awaken_attempt"] = None
                interrupt_work(state, nid, (end - timedelta(seconds=remaining)).isoformat(), "involuntary_sleep")
                if traveling:
                    traveling["status"] = "interrupted"
                    traveling["resolved_at"] = (end - timedelta(seconds=remaining)).isoformat()
            elif actual != span:
                raise ValueError("unexpected NPC activity interruption")
        if npc["activity_plan"] and end >= datetime.fromisoformat(npc["activity_plan"]["until"]):
            npc["activity_plan"] = None

def projection(state, participants):
    return {nid: {"activity": copy.deepcopy(state["npcs"][nid]["activity"]),
                  "plan": copy.deepcopy(state["npcs"][nid]["activity_plan"]),
                  "morale": copy.deepcopy(state["npcs"][nid]["morale"]),
                  **({"schedule": copy.deepcopy(state["npcs"][nid]["daily_schedule"]),
                      "morning_until": state["npcs"][nid]["morning_until"],
                      "current_occupation": copy.deepcopy(occupational_window(state["npcs"][nid], datetime.fromisoformat(state["time"]))) if state["npcs"][nid]["activity"]["status"] == "awake" and not state["npcs"][nid]["activity_plan"] and not pending_work(state, nid) and not any(e["npc"] == nid and e["status"] == "traveling" for e in state.get("npc_travel", [])) else None,
                      "location": state["npcs"][nid]["location"]} if "daily_schedule" in state["npcs"][nid] else {})}
            for nid in sorted(participants) if "activity" in state["npcs"][nid]}
