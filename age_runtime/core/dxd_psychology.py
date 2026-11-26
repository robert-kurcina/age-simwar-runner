"""DXD Book IV Insane X and a bounded paired Psychology Disability.

Only Paranoid is mechanically supported here. Other Disabilities require
their own source-backed rules. This is fictional character state, not diagnosis.
"""
from age_runtime.core import dxd_conditions

def acquire(morale, concerns, *, revelation, understood, destabilized, disability, turn):
    if understood is not True or destabilized is not True:
        raise ValueError("cosmic acquisition requires comprehension and destabilization")
    if not isinstance(revelation, str) or not revelation.strip():
        raise ValueError("revelation required")
    if disability != "Paranoid":
        raise ValueError("unsupported paired Psychology Disability")
    if any(r["revelation"] == revelation for r in morale["revelations"]):
        raise ValueError("revelation already acquired")
    traits = morale.setdefault("psychology", {})
    level = traits.get(disability, 0)
    if level >= 3:
        raise ValueError("paired Disability limit reached")
    traits[disability] = level + 1
    morale["revelations"].append({"revelation": revelation, "disability": disability, "turn": turn})
    morale["fear"] = max(4, morale["fear"])
    # One minStress per Psychology Disability, not per level or Insane X.
    concerns["min_stress"] = len(traits)
    if concerns["stress"] < concerns["min_stress"]:
        dxd_conditions.add(concerns, stress=concerns["min_stress"] - concerns["stress"])

def effects(morale, context):
    """Paranoid: -XD first meeting regarding friendliness, -3X trusting others.
    Context is authored explicitly; never penalize every social Test.
    """
    level = morale.get("psychology", {}).get("Paranoid", 0)
    if context == "first_friendliness":
        return {"dm": 0, "penalty": level}
    if context == "trust_decision":
        return {"dm": -3 * level, "penalty": 0}
    if context is not None:
        raise ValueError("unknown Psychology context")
    return {"dm": 0, "penalty": 0}
