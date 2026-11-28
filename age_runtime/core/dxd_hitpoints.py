"""DXD Book III Hitpoints and Book VII recovery/Subdue.

Only resolved superficial loss or reviewed Subdue exchanges. No raw Damage
rolls, armour, Stun resistance, hit-location adjudication, or AP loop.
"""
from age_runtime.core import dxd_injury


def initial(capacity):
    if type(capacity) is not int or capacity < 1:
        raise ValueError("positive Hitpoint capacity required")
    return {"capacity": capacity, "current": capacity, "rest_seconds": 0,
            "unconscious": False}


def incapacitated(pc):
    return (dxd_injury.incapacitated(pc.get("injury"))
            or pc.get("hitpoints", {}).get("unconscious", False))


def lose(pool, amount):
    """Resolved HP-only loss; no implicit Bodypoint conversion or KO."""
    if type(amount) is not int or not 0 <= amount <= pool["current"]:
        raise ValueError("resolved Hitpoint loss exceeds available pool")
    pool["current"] -= amount
    pool["rest_seconds"] = 0


def subdue(pc, damage):
    """Resolved Subdue Damage; overflow divided by five as native Injury."""
    if type(damage) is not int or damage < 1 or incapacitated(pc):
        raise ValueError("invalid Subdue consequence")
    pool = pc["hitpoints"]
    loss = min(pool["current"], damage)
    overflow = damage - loss
    lose(pool, loss)
    if pool["current"] == 0:
        pool["unconscious"] = True
        if overflow // 5:
            dxd_injury.apply(pc["injury"], overflow // 5)


def recover(pool, amount):
    if type(amount) is not int or amount < 0:
        raise ValueError("invalid Hitpoint recovery")
    old = pool["current"]
    pool["current"] = min(pool["capacity"], old + amount)
    return pool["current"] - old


def advance(pc, seconds, *, restful):
    """Native RR per completed ten seconds of non-strenuous activity.

    No automatic waking from Subdue: exact awakening authority is separate.
    Unconsciousness is not ordinary sleep and never grants sleep recovery.
    """
    if type(seconds) is not int or seconds < 0 or type(restful) is not bool:
        raise ValueError("invalid Hitpoint interval")
    pool = pc["hitpoints"]
    if not restful or incapacitated(pc):
        pool["rest_seconds"] = 0
        return 0
    count, pool["rest_seconds"] = divmod(pool["rest_seconds"] + seconds, 10)
    return recover(pool, count * pc["concerns"]["capacity"]["recovery_rate"])


def projection(pool):
    return {k: pool[k] for k in ("capacity", "current", "unconscious")}
