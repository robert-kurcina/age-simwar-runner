"""Bounded DXD Test arithmetic; no setting or session-state ownership."""
from random import Random

STANDARD_TNS = (4, 7, 10, 13, 16, 19, 22, 25, 28, 37, 46)
ATTRIBUTES = ("CCA", "RCA", "REF", "INT", "KNO", "PRE", "POW", "STR", "FOR", "MOV", "SIZ", "ZED")

def _int(value, name, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("invalid " + name)
    return value

def validate_attributes(record):
    """Full major-character record for the supported ordinary index range."""
    if not isinstance(record, dict) or set(record) != set(ATTRIBUTES):
        raise ValueError("complete twelve-Attribute DXD record required")
    for key in ATTRIBUTES:
        _int(record[key], key, 1)

def attribute_dm(raw):
    """Ordinary attribute indices; neutral 7, symmetric steps away from 7."""
    delta = _int(raw, "attribute", 1) - 7
    return (1 if delta >= 0 else -1) * ((abs(delta) + 1) // 2)

def _pool(base, bonus, penalty, favor):
    for name, value, minimum in (("base", base, 2), ("bonus", bonus, 0),
                                 ("penalty", penalty, 0), ("favor", favor, 0)):
        _int(value, name, minimum)
    net = bonus - penalty
    if base + favor + abs(net) > 100:
        raise ValueError("dice pool exceeds runner limit")
    return base + favor, net

def _roll(rng, base, net, dm):
    # Stable ties preserve base dice for bonuses, modifier dice for penalties.
    dice = [rng.randint(1, 6) for _ in range(base + abs(net))]
    indices = list(range(len(dice)))
    if net > 0:
        indices.sort(key=lambda i: (-dice[i], i))
    elif net < 0:
        indices.sort(key=lambda i: (dice[i], -i))
    kept = indices[:base]
    return {"dice": dice, "kept": kept, "dm": dm,
            "score": sum(dice[i] for i in kept) + dm}

def _result(active, tn, passed, opponent=None):
    margin = active["score"] - tn
    return {"active": active, "tn": tn, "opponent": opponent,
            "passed": passed, "margin": margin,
            "dos": max(0, margin) // 5 if passed else 0,
            "dof": max(0, -margin) // 5 if not passed else 0}

def test(seed, *, tn=7, dm=0, base=2, bonus=0, penalty=0, favor=0,
         narrative=False, adversity=0, adversity_dice=0, npc_dm=0):
    """Resolve unopposed or narrative Test from explicitly gathered inputs.

    Narrative adversity is separated from favorable DM and dice to avoid
    double charging. The caller must supply only applicable, validated DMs.
    """
    _int(tn, "target")
    _int(dm, "modifier")
    _int(adversity, "adversity", 0)
    _int(adversity_dice, "adversity dice", 0)
    _int(npc_dm, "npc modifier")
    if not narrative and (adversity or adversity_dice or npc_dm):
        raise ValueError("narrative adjustments require narrative Test")
    if narrative and (dm < 0 or penalty or tn != 7 and npc_dm):
        raise ValueError("use explicit narrative adversity; NPC base TN is 7")
    # Narrative penalty dice convert to +3 TN rather than being rolled.
    if narrative:
        tn += adversity + 3 * adversity_dice + npc_dm
    count, net = _pool(base, bonus, penalty, favor)
    active = _roll(Random(seed), count, net, dm)
    return _result(active, tn, active["score"] >= tn)

def opposed(seed, *, active_raw, target_raw, active_dm=0, target_dm=0,
            active_bonus=0, active_penalty=0, target_bonus=0, target_penalty=0,
            active_favor=0, target_favor=0):
    """Use the specific opposed tie rule: raw attribute, then active actor."""
    ac, an = _pool(2, active_bonus, active_penalty, active_favor)
    tc, tn = _pool(2, target_bonus, target_penalty, target_favor)
    if an * tn > 0:
        cancel = min(abs(an), abs(tn))
        sign = 1 if an > 0 else -1
        an -= sign * cancel
        tn -= sign * cancel
    rng = Random(seed)
    a = _roll(rng, ac, an, attribute_dm(active_raw) + _int(active_dm, "active modifier"))
    b = _roll(rng, tc, tn, attribute_dm(target_raw) + _int(target_dm, "target modifier"))
    passed = (a["score"], active_raw) >= (b["score"], target_raw)
    return _result(a, b["score"], passed, b)

def automatic_favor(*, available, maximum, significance, desired):
    """AGE policy, not DXD canon. Select before rolling; caller debits pool.

    Scenario policy supplies desired allocation for each significance class.
    No rerolls, no automatic resource creation.
    """
    _int(available, "available favor", 0)
    _int(maximum, "maximum advantage", 0)
    if significance not in ("routine", "minor", "important", "critical"):
        raise ValueError("unknown significance")
    amount = _int(desired.get(significance, 0), "desired favor", 0)
    return min(available, maximum, amount)

def emicted_favor(*, available, maximum, enabled):
    """Book II: exhausted pool grants fixed Max Advantage DM, not dice."""
    _int(available, "available favor", 0)
    _int(maximum, "maximum advantage", 0)
    if type(enabled) is not bool:
        raise ValueError("invalid emicted favor policy")
    return maximum if enabled and available == 0 else 0
