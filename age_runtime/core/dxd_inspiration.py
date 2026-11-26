"""AGE automatic Inspiration policy for bounded DXD Tests."""
from fractions import Fraction
from math import comb
from age_runtime.core import dxd

def probability(*, tn=7, dm=0, base=2, bonus=0, penalty=0, favor=0,
                narrative=False, adversity=0, adversity_dice=0, npc_dm=0):
    """Exact distribution via face-count DP, not exponential roll enumeration."""
    count, net = dxd._pool(base, bonus, penalty, favor)
    if narrative:
        tn += adversity + 3 * adversity_dice + npc_dm
    n = count + abs(net)
    target = tn - dm
    if target <= count:
        return Fraction(1)
    if target > 6 * count:
        return Fraction(0)
    faces = range(6, 0, -1) if net > 0 else range(1, 7)
    states = {(0, 0): 1}
    for face in faces:
        next_states = {}
        for (used, score), ways in states.items():
            for k in range(n - used + 1):
                key = (used + k, score + face * min(k, max(0, count - used)))
                next_states[key] = next_states.get(key, 0) + ways * comb(n - used, k)
        states = next_states
    return Fraction(sum(ways for (used, score), ways in states.items()
                        if used == n and score >= target), 6 ** n)

def eligible(chance, *, turn, last_turn, consequence, maximum, extra_base):
    if consequence not in ("routine", "meaningful", "irreversible"):
        raise ValueError("unknown consequence class")
    return (consequence != "routine"
            and (last_turn is None or turn - last_turn >= 3)
            and extra_base < maximum
            and (chance <= Fraction(33, 100)
                 or consequence == "irreversible" and chance <= Fraction(67, 100)))

def applicable_dm(entries, tags):
    return min(3, sum(1 for entry in entries if entry["tag"] in tags))
