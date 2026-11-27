"""Whole-body injury accounting; DXD Book VII, SL_7124 and SL_7134.

Accept resolved Injury, not raw attack Damage. Hitpoint buffering, armour,
FOR reductions and damage rolls belong to the exchange that resolves Damage.
No tactical combat, automatic healing or death adjudication.
"""

def initial(bodypoints):
    if type(bodypoints) is not int or bodypoints < 1:
        raise ValueError("explicit positive Bodypoints required")
    return {"capacity": bodypoints, "injury": 0}


def apply(state, injury):
    """One distinct resolved injury; replace higher severity, else increment."""
    if type(injury) is not int or injury < 1:
        raise ValueError("positive resolved Injury required")
    state["injury"] = max(injury, state["injury"] + 1)


def projection(state):
    capacity, injury = state["capacity"], state["injury"]
    remaining = capacity - injury
    return {"capacity": capacity, "injury": injury, "bodypoints": remaining,
            "status": "dying" if remaining <= 0 else
                      "severely_injured" if 2 * injury >= capacity else
                      "injured" if injury else "uninjured"}


def penalty_dice(state):
    return int(projection(state)["status"] in ("severely_injured", "dying"))
