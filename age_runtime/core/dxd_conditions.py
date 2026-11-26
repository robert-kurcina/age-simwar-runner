"""DXD concern thresholds and bounded recovery (Books III and VII)."""
from age_runtime.core.dxd import attribute_dm, validate_attributes

def capacities(attributes):
    validate_attributes(attributes)
    return {"endurance": 3 + attributes["FOR"],
            "resilience": 3 + 2 * attributes["POW"] // 3,
            "recovery_rate": max(1, 3 + attribute_dm(attributes["POW"])
                                 + attribute_dm(attributes["FOR"])) + attributes["SIZ"] // 5}

def initial(attributes):
    return {"capacity": capacities(attributes), "fatigue": 0, "stress": 0,
            "weariness": 0}

def degrees(state):
    c = state["capacity"]
    return {"fatigue": state["fatigue"] // c["endurance"],
            "stress": state["stress"] // c["resilience"],
            "weariness": state["weariness"] // c["endurance"]}

def add(state, *, fatigue=0, stress=0, weariness=0):
    if any(type(n) is not int or n < 0 for n in (fatigue, stress, weariness)):
        raise ValueError("concern increments must be nonnegative integers")
    before = degrees(state)
    state["fatigue"] += fatigue
    state["stress"] += stress
    after = degrees(state)
    state["weariness"] += (weariness + after["fatigue"] - before["fatigue"]
                           + after["stress"] - before["stress"])

def penalty_dice(state, *, decision=False):
    d = degrees(state)
    return d["fatigue"] + d["weariness"] + (d["stress"] if decision else 0)

def recover(state, minutes, *, safe=False, restful=False):
    """One explicit restful interval; use the 10-minute Fatigue alternative.

    No automatic recovery for unclassified activities. Safety is required
    for Stress recovery. Fractional intervals are not carried across actions.
    """
    if type(minutes) is not int or minutes < 0:
        raise ValueError("invalid recovery minutes")
    if not restful:
        return
    rr = state["capacity"]["recovery_rate"]
    fatigue = minutes // 10 * rr if minutes >= 10 else minutes
    state["fatigue"] = max(0, state["fatigue"] - fatigue)
    if safe:
        state["stress"] = max(state.get("min_stress", 0), state["stress"] - minutes // 10 * rr)
    state["weariness"] = max(0, state["weariness"] - minutes // 60 * rr)

def describe(state):
    d = degrees(state)
    return {"fatigue": ("Rested" if not state["fatigue"] else "Physically strained" if not d["fatigue"] else "Exhausted"),
            "stress": ("Composed" if not state["stress"] else "Under pressure" if not d["stress"] else
                       "Irritable" if d["stress"] == 1 else "Anxious" if d["stress"] == 2 else "Emotionally distressed"),
            "weariness": ("Rested" if not state["weariness"] else "Low energy" if not d["weariness"] else "Worn down")}

# Opt-in second-resolution activity accounting. Legacy callers retain recover().
from random import Random
from age_runtime.core import dxd
from age_runtime.core.dxd_character import sleep_limit_hours

ACTIVITIES = ("active", "quiet", "rest", "low_energy", "restorative", "travel", "sleep")

def activity_initial(attributes, awake_seconds=0):
    if type(awake_seconds) is not int or awake_seconds < 0:
        raise ValueError("invalid sleep timing")
    return {"awake_seconds": awake_seconds, "limit_seconds": sleep_limit_hours(attributes["FOR"]) * 3600,
            "overdue_seconds": 0,
            "sleep_seconds": 0, "required_sleep_seconds": 0, "status": "awake",
            "remainder": {}, "activity": None, "checks": [], "pending_sleep_seconds": None,
            "sleep_episode": 0, "early_stress": 0}

def refresh_sleep_limit(state, clock, attributes):
    d = degrees(state)
    clock["limit_seconds"] = sleep_limit_hours(attributes["FOR"], d["weariness"], d["stress"]) * 3600
    if clock["status"] != "awake" or clock["awake_seconds"] <= clock["limit_seconds"]:
        clock["overdue_seconds"] = 0

def required_sleep(state, attributes):
    return max(1, 8 + dxd.attribute_dm(attributes["INT"]) + degrees(state)["weariness"]) * 3600

def _interval(clock, key, seconds, unit, eligible):
    if not eligible:
        clock["remainder"].pop(key, None)
        return 0
    count, remainder = divmod(clock["remainder"].get(key, 0) + seconds, unit)
    clock["remainder"][key] = remainder
    return count

def advance_activity(state, clock, seconds, activity, *, safe=False, seed="", attributes=None):
    """Advance one homogeneous interval; return actual seconds before forced sleep.

    Minute Fatigue recovery is the selected native alternative. Full quiet
    rest uses Recovery Rate Weariness; low-energy activity uses one/hour.
    Sleep recovery is handled at waking, not stacked with ordinary rest.
    """
    if type(seconds) is not int or seconds < 0 or activity not in ACTIVITIES:
        raise ValueError("invalid activity")
    refresh_sleep_limit(state, clock, attributes)
    if activity == "sleep":
        if clock["status"] != "asleep":
            raise ValueError("not asleep")
        clock["sleep_seconds"] += seconds
        clock["activity"] = "sleep"
        clock["remainder"].clear()
        return seconds
    if clock["status"] != "awake":
        raise ValueError("character is asleep")
    rr = state["capacity"]["recovery_rate"]
    remaining = seconds
    while remaining:
        awake = clock["awake_seconds"]
        limit = clock["limit_seconds"]
        overdue = awake >= limit
        chunk = min(remaining, 3600 - clock["overdue_seconds"] if overdue else limit - awake)
        pending = clock["pending_sleep_seconds"]
        if pending is not None:
            if pending == 0:
                return seconds - remaining
            chunk = min(chunk, pending)
        quiet = activity in ("quiet", "rest", "low_energy", "restorative")
        weariness_rate = rr if activity in ("quiet", "rest") else 1
        # Preserve fractional progress only while the same recovery mode applies.
        if clock["activity"] != activity:
            clock["remainder"].pop("weariness", None)
        # Recovery can change either Degree and therefore the Sleep Limit.
        if quiet:
            chunk = min(chunk, 3600 - clock["remainder"].get("weariness", 0))
        if quiet and safe:
            chunk = min(chunk, 600 - clock["remainder"].get("stress", 0))
        if activity == "restorative":
            chunk = min(chunk, 3600 - clock["remainder"].get("restorative", 0))
        fatigue = _interval(clock, "fatigue", chunk, 60, quiet)
        stress = _interval(clock, "stress", chunk, 600, quiet and safe) * rr
        weariness = _interval(clock, "weariness", chunk, 3600, quiet) * weariness_rate
        restorative = _interval(clock, "restorative", chunk, 3600, activity == "restorative")
        for _ in range(restorative):
            n = clock.get("restorative_rolls", 0)
            stress += Random(f"{seed}:restorative:{n}").randint(1, 6)
            clock["restorative_rolls"] = n + 1
        state["fatigue"] = max(0, state["fatigue"] - fatigue)
        state["stress"] = max(state.get("min_stress", 0), state["stress"] - stress)
        state["weariness"] = max(0, state["weariness"] - weariness)
        clock["awake_seconds"] += chunk
        clock["activity"] = activity
        remaining -= chunk
        if overdue:
            clock["overdue_seconds"] += chunk
        if pending is not None:
            clock["pending_sleep_seconds"] -= chunk
        if clock["overdue_seconds"] == 3600:
            clock["overdue_seconds"] = 0
            add(state, weariness=1)
            next_hour = clock["awake_seconds"]
            if degrees(state)["weariness"] and clock["pending_sleep_seconds"] is None:
                result = dxd.test(f"{seed}:sleep:{clock['sleep_episode']}:{next_hour}",
                                  tn=7, dm=dxd.attribute_dm(attributes["FOR"]),
                                  penalty=penalty_dice(state))
                clock["checks"].append({"awake_seconds": next_hour, "result": result})
                if not result["passed"]:
                    clock["pending_sleep_seconds"] = 60 * (rr + Random(f"{seed}:onset:{clock['sleep_episode']}:{next_hour}").randint(1, 6))
        refresh_sleep_limit(state, clock, attributes)
        if clock["pending_sleep_seconds"] == 0:
            return seconds - remaining
    return seconds

def begin_sleep(state, clock, attributes):
    if clock["status"] != "awake":
        raise ValueError("already asleep")
    clock.update(status="asleep", sleep_seconds=0,
                 required_sleep_seconds=required_sleep(state, attributes),
                 pending_sleep_seconds=None, activity="sleep", remainder={}, overdue_seconds=0)
    clock["sleep_episode"] += 1

def wake(state, clock, attributes, *, seed, forced=False):
    if clock["status"] != "asleep" or clock["sleep_seconds"] < 3600:
        raise ValueError("at least one hour of sleep required")
    slept = clock["sleep_seconds"]
    required = clock["required_sleep_seconds"]
    if slept < required and not forced:
        raise ValueError("premature waking requires forced awakening")
    rng = Random(f"{seed}:wake:{clock['sleep_episode']}:{slept}")
    if forced and slept < required:
        result = dxd.test(f"{seed}:awaken:{clock['sleep_episode']}:{slept}",
                          tn=7, dm=dxd.attribute_dm(attributes["FOR"]))
        clock["checks"].append({"sleep_seconds": slept, "awakening": result})
        if not result["passed"]:
            return False
    state["fatigue"] = max(0, state["fatigue"] - slept // 60)
    state["weariness"] = max(0, state["weariness"] - sum(rng.randint(1, 6) for _ in range(slept // 3600)))
    state["stress"] = max(state.get("min_stress", 0), state["stress"] - rng.randint(1, 6))
    if slept < required:
        # Duration of the resulting floor is not specified in the source.
        # Retain it until the next fully completed sleep episode.
        missed = (required - slept + 3599) // 3600
        extra = sum(rng.randint(1, 6) for _ in range(missed))
        clock["early_stress"] += extra
        state["min_stress"] = state.get("min_stress", 0) + extra
        add(state, stress=max(0, state["min_stress"] - state["stress"]))
    elif clock["early_stress"]:
        state["min_stress"] = max(0, state.get("min_stress", 0) - clock["early_stress"])
        clock["early_stress"] = 0
    clock.update(status="awake", awake_seconds=0, sleep_seconds=0,
                 required_sleep_seconds=0, activity=None, remainder={}, overdue_seconds=0)
    refresh_sleep_limit(state, clock, attributes)
    return True
