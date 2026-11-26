"""DXD Book VII Morale outcomes for bounded narrative scenes."""
from age_runtime.core import dxd_conditions

TRIGGERS = {"bravery": ("harm", "rectitude", "risk"),
            "fear": ("injury", "mortified", "brutality", "steadfast"),
            "shock": ("horrifying", "surprise", "amazement")}
CAP = {"bravery": 1, "shock": 2, "fear": 4}
LABELS = ("Ordered", "Nervous", "Disordered", "Panicked", "Broken")

def initial():
    return {"fear": 0, "events": [], "revelations": [], "psychology": {}}

def specification(kind, trigger):
    if kind not in TRIGGERS or trigger not in TRIGGERS[kind]:
        raise ValueError("invalid Morale trigger")
    return {"attribute": "POW", "tn": 7, "fixed_dm": -3,
            "decision": True, "significance": "important"}

def apply(state, concerns, *, kind, trigger, result, event, turn, grit=0):
    specification(kind, trigger)
    if any(x["event"] == event for x in state["events"]):
        raise ValueError("Morale event already resolved")
    before = dxd_conditions.degrees(concerns)["stress"]
    if not result["passed"]:
        # Misses are the shortfall in score, not Degrees of Failure.
        dxd_conditions.add(concerns, stress=max(0, -result["margin"]))
        gained = dxd_conditions.degrees(concerns)["stress"] - before
        if kind == "bravery":
            state["fear"] = max(state["fear"], 1)
        elif kind == "fear":
            state["fear"] = max(state["fear"], min(CAP[kind], state["fear"] + max(0, gained - grit)))
        # Shock contributes Stress; its explicit immediate effect is hesitation.
        # Do not manufacture Fear tokens merely because a Shock Test failed.
    record = {"event": event, "turn": turn, "kind": kind, "trigger": trigger,
              "passed": result["passed"],
              "hesitation_combat_turns": 0 if result["passed"] or kind != "shock" else 1 + result["dof"]}
    state["events"].append(record)
    return record

def calm(state, *, safe=False, stress_degrees_removed=0):
    if safe:
        state["fear"] = 0
    else:
        state["fear"] = max(0, state["fear"] - stress_degrees_removed)

def describe(state):
    return LABELS[state["fear"]]
