"""DXD Book VII whole-body injury and dedicated Alive/Dying/Dead rules.

Resolved Injury only. No raw Damage, automatic healing or tactical combat.
The dedicated lifecycle thresholds take precedence over the general overview.
"""
def initial(bodypoints, size=None, recovery_rate=None):
    if type(bodypoints) is not int or bodypoints < 1:
        raise ValueError("explicit positive Bodypoints required")
    if size is None:
        return {"capacity": bodypoints, "injury": 0}
    if type(size) is not int or size < 1 or type(recovery_rate) is not int or recovery_rate < 1:
        raise ValueError("explicit positive SIZ and Recovery Rate required")
    return {"capacity": bodypoints, "injury": 0, "size": size,
            "recovery_rate": recovery_rate, "dying_seconds": 0}


def apply(state, injury):
    if type(injury) is not int or injury < 1:
        raise ValueError("positive resolved Injury required")
    if projection(state)["status"] == "dead":
        raise ValueError("character already dead")
    state["injury"] = max(injury, state["injury"] + 1)


def projection(state):
    capacity, injury = state["capacity"], state["injury"]
    remaining = capacity - injury
    size = state.get("size")
    if size is None:
        status = "dying" if remaining <= 0 else "severely_injured" if 2 * injury >= capacity else "injured" if injury else "uninjured"
    else:
        status = ("dead" if remaining <= -2 * size else "dying" if remaining <= -size
                  else "coma" if remaining < 0 else "severely_injured" if 2 * injury >= capacity
                  else "injured" if injury else "uninjured")
    return {"capacity": capacity, "injury": injury, "bodypoints": remaining, "status": status}


def incapacitated(state):
    return bool(state and projection(state)["status"] in ("coma", "dying", "dead"))


def penalty_dice(state):
    return int(projection(state)["status"] in ("severely_injured", "coma", "dying", "dead"))


def advance(state, seconds):
    """Credit elapsed deterioration once, stopping exactly at death."""
    if type(seconds) is not int or seconds < 0:
        raise ValueError("invalid injury interval")
    if "size" not in state or projection(state)["status"] != "dying":
        return 0
    interval = 60 * state["recovery_rate"]
    remaining = state["capacity"] + 2 * state["size"] - state["injury"]
    actual = min(seconds, remaining * interval - state["dying_seconds"])
    loss, state["dying_seconds"] = divmod(state["dying_seconds"] + actual, interval)
    state["injury"] += loss
    return actual


def next_boundary(state):
    if state and "size" in state and projection(state)["status"] == "dying":
        return 60 * state["recovery_rate"] - state["dying_seconds"]
    return None
