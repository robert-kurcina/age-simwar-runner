"""Reviewed persistent location consequences, DXD Book VII SL_7344/7377/7410.

Only already-resolved permanent loss is supported here. Temporary location
injury, bleeding, hit location selection and damage resolution are distinct.
"""
import copy
from age_runtime.core import dxd_injury

# Bounded human anatomy pilot. A side is part of the identity.
FUNCTIONS = {
    "left_eye": ("vision",), "right_eye": ("vision",),
    "left_ear": ("hearing",), "right_ear": ("hearing",),
    "left_hand": ("attack",), "right_hand": ("attack",),
    "left_arm": ("attack", "structure"), "right_arm": ("attack", "structure"),
    "left_foot": ("mobility",), "right_foot": ("mobility",),
    "left_leg": ("mobility", "structure"), "right_leg": ("mobility", "structure"),
}


def validate(effect):
    if not isinstance(effect, dict) or set(effect) != {"location", "severity"}:
        raise ValueError("invalid reviewed permanent location consequence")
    if effect["location"] not in FUNCTIONS or effect["severity"] != "dismembered":
        raise ValueError("unsupported permanent location consequence")


def record(injury, effect):
    validate(effect)
    if not injury["injury"] or dxd_injury.projection(injury)["status"] == "dead":
        raise ValueError("permanent consequence requires living injured character")
    # A repeated record of the same loss must not stack penalties.
    injury.setdefault("permanent_locations", {})[effect["location"]] = "dismembered"


def projection(injury):
    return copy.deepcopy(injury.get("permanent_locations", {}))


def penalties(injury, spec):
    """Apply only to explicitly reviewed participating locations.

    Assistance must be reviewed in the Test, not merely asserted by player.
    Functional cues are descriptive; never independently add another penalty.
    """
    used = spec.get("participating_locations", [])
    assisted = spec.get("assisted_locations", [])
    if (not isinstance(used, list) or not isinstance(assisted, list)
            or any(not isinstance(x, str) or x not in FUNCTIONS for x in used + assisted)
            or not set(assisted) <= set(used)):
        raise ValueError("invalid reviewed Test location participation")
    return [{"location": loc, "penalty": 2 if loc in assisted else 3}
            for loc in sorted(set(used)) if loc in injury.get("permanent_locations", {})]
