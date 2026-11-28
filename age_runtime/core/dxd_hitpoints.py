"""DXD Book III Hitpoints and Book VII recovery/Subdue.

Only resolved superficial loss or reviewed Subdue exchanges. No raw Damage
rolls, armour, Stun resistance, hit-location adjudication, or AP loop.
"""
from age_runtime.core import dxd_injury, dxd


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
        pool["unconscious_seconds"] = 0
        pool["minimum_seconds"] = minimum_seconds(pc["injury"]["injury"])
        pool["awakening_checks"] = []


def recover(pool, amount):
    if type(amount) is not int or amount < 0:
        raise ValueError("invalid Hitpoint recovery")
    old = pool["current"]
    pool["current"] = min(pool["capacity"], old + amount)
    return pool["current"] - old


def advance(pc, seconds, *, restful):
    """Native RR per completed ten seconds of non-strenuous activity.

    Unconscious duration and awakening use separate chronological accounting.
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


def minimum_seconds(injury):
    """Scalar(Injury) rounds, ten seconds each; zero injury uses one round.
    
    The zero-injury case is an explicit AGE convention, not a native rule.
    """
    if type(injury) is not int or injury < 0:
        raise ValueError("invalid Injury")
    if injury == 0:
        return 10
    return (12, 15, 20, 25, 30, 40, 50, 60, 80, 100)[(injury - 1) % 10] * 10 ** ((injury - 1) // 10) * 10


def advance_unconscious(pc, seconds):
    pool = pc.get("hitpoints", {})
    if not pool.get("unconscious") or dxd_injury.incapacitated(pc.get("injury")):
        return False
    pool["unconscious_seconds"] = pool.get("unconscious_seconds", 0) + seconds
    if pool["unconscious_seconds"] >= pool.get("minimum_seconds", minimum_seconds(pc["injury"]["injury"])):
        pool["unconscious"] = False
        return True
    return False


def awakening_boundary(pc):
    pool = pc.get("hitpoints", {})
    if pool.get("unconscious") and not dxd_injury.incapacitated(pc.get("injury")):
        return max(1, pool.get("minimum_seconds", minimum_seconds(pc["injury"]["injury"])) - pool.get("unconscious_seconds", 0))
    return None


def assisted_awaken(pc, seed):
    pool = pc["hitpoints"]
    if not pool["unconscious"] or dxd_injury.incapacitated(pc.get("injury")):
        raise ValueError("patient cannot be awakened by this procedure")
    elapsed = pool.get("unconscious_seconds", 0)
    checks = pool.setdefault("awakening_checks", [])
    if checks and elapsed - checks[-1]["elapsed"] < 600:
        raise ValueError("awakening retry requires ten minutes")
    result = dxd.test(f"{seed}:awaken:{len(checks)}", tn=7,
                      dm=dxd.attribute_dm(pc["attributes"]["FOR"]) - pc["injury"]["injury"])
    checks.append({"elapsed": elapsed, "result": result})
    if result["passed"]:
        pool["unconscious"] = False
    return result
