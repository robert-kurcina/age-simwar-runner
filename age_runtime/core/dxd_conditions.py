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
        state["stress"] = max(0, state["stress"] - minutes // 10 * rr)
    state["weariness"] = max(0, state["weariness"] - minutes // 60 * rr)

def describe(state):
    d = degrees(state)
    return {"fatigue": ("Rested" if not state["fatigue"] else "Physically strained" if not d["fatigue"] else "Exhausted"),
            "stress": ("Composed" if not state["stress"] else "Under pressure" if not d["stress"] else
                       "Irritable" if d["stress"] == 1 else "Anxious" if d["stress"] == 2 else "Emotionally distressed"),
            "weariness": ("Rested" if not state["weariness"] else "Low energy" if not d["weariness"] else "Worn down")}
