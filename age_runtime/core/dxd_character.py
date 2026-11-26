"""DXD Book III bounded humanoid character derivation.

Height & Weight table: vault-sarnalen a6e0058e340a63c9cf4f9c6fd26a75c340569782.
Rows are (height inches, weight pounds, SIZ); table takes precedence over approximation.
"""
from age_runtime.core import dxd

ROLLED = ("CCA", "RCA", "REF", "INT", "KNO", "PRE", "POW", "STR", "FOR")
HEIGHT_WEIGHT = (
    (18, 3, -6),  # 0
    (19, 3, -5),  # 1
    (20, 4, -4),  # 2
    (22, 5, -3),  # 3
    (23, 6, -3),  # 4
    (24, 7, -2),  # 5
    (25, 8, -1),  # 6
    (26, 8, -1),  # 7
    (27, 9, 0),  # 8
    (27, 10, 0),  # 9
    (28, 10, 0),  # 10
    (29, 11, 0),  # 11
    (29, 12, 1),  # 12
    (30, 13, 1),  # 13
    (31, 14, 1),  # 14
    (31, 15, 2),  # 15
    (32, 16, 2),  # 16
    (33, 17, 2),  # 17
    (34, 18, 3),  # 18
    (34, 19, 3),  # 19
    (35, 21, 3),  # 20
    (36, 22, 3),  # 21
    (37, 24, 4),  # 22
    (38, 26, 4),  # 23
    (39, 27, 4),  # 24
    (40, 29, 5),  # 25
    (41, 32, 5),  # 26
    (42, 34, 5),  # 27
    (43, 36, 6),  # 28
    (44, 39, 6),  # 29
    (45, 42, 6),  # 30
    (46, 45, 6),  # 31
    (47, 48, 7),  # 32
    (48, 51, 7),  # 33
    (49, 55, 7),  # 34
    (50, 59, 8),  # 35
    (51, 63, 8),  # 36
    (52, 68, 8),  # 37
    (54, 72, 9),  # 38
    (55, 78, 9),  # 39
    (56, 83, 9),  # 40
    (58, 89, 9),  # 41
    (59, 96, 10),  # 42
    (60, 102, 10),  # 43
    (62, 110, 10),  # 44
    (63, 118, 11),  # 45
    (65, 126, 11),  # 46
    (66, 135, 11),  # 47
    (68, 145, 12),  # 48
    (69, 155, 12),  # 49
    (71, 166, 12),  # 50
    (73, 178, 12),  # 51
    (74, 191, 13),  # 52
    (76, 205, 13),  # 53
    (78, 220, 13),  # 54
    (80, 235, 14),  # 55
    (82, 252, 14),  # 56
    (84, 270, 14),  # 57
    (85, 290, 15),  # 58
    (87, 311, 15),  # 59
    (90, 333, 15),  # 60
    (92, 357, 15),  # 61
    (94, 382, 16),  # 62
    (96, 410, 16),  # 63
    (98, 439, 16),  # 64
    (101, 471, 17),  # 65
    (103, 505, 17),  # 66
    (105, 541, 17),  # 67
    (108, 580, 18),  # 68
    (110, 621, 18),  # 69
    (113, 666, 18),  # 70
    (115, 714, 18),  # 71
    (118, 765, 19),  # 72
    (121, 820, 19),  # 73
    (123, 879, 19),  # 74
    (126, 942, 20),  # 75
    (129, 1009, 20),  # 76
    (133, 1082, 20),  # 77
    (137, 1159, 21),  # 78
    (140, 1242, 21),  # 79
    (143, 1332, 21),  # 80
    (147, 1427, 21),  # 81
    (150, 1530, 22),  # 82
    (154, 1639, 22),  # 83
    (157, 1757, 22),  # 84
    (161, 1883, 23),  # 85
    (165, 2018, 23),  # 86
    (169, 2163, 23),  # 87
    (173, 2318, 24),  # 88
    (177, 2485, 24),  # 89
    (181, 2663, 24),  # 90
    (185, 2854, 24),  # 91
    (190, 3059, 25),  # 92
    (194, 3279, 25),  # 93
    (199, 3514, 25),  # 94
    (203, 3766, 26),  # 95
    (208, 4037, 26),  # 96
    (213, 4326, 26),  # 97
    (218, 4637, 27),  # 98
    (223, 4970, 27),  # 99
)
CRITICAL = {
    "Academic": ("INT", "KNO", "POW"),
    "Cleric": ("INT", "KNO", "PRE", "POW"),
    "Entertainer": ("REF", "INT", "PRE"),
    "Knight": ("PRE", "POW", "STR", "FOR"),
    "Mariner": ("PRE", "POW", "STR", "FOR"),
    "Merchant": ("INT", "KNO", "PRE", "POW"),
    "Rabble": ("REF", "STR", "FOR"),
    "Ranger": ("PRE", "POW", "STR", "FOR"),
    "Rogue": ("CCA", "RCA", "REF", "INT"),
    "Service": ("INT", "KNO", "POW"),
    "Warrior": ("PRE", "POW", "STR", "FOR"),
    "Wizard": ("INT", "KNO", "PRE", "POW"),
    "Default": ("REF", "STR", "FOR"),
}

def derive(attributes, body):
    """Freeze a curated nine-Attribute array and explicit creation inputs.

    Stature and Build are final authored indices, not rolled here. The
    stored original rolls are distinct from adjusted values. Trade is an
    explicit adaptation used for Affinity; no setting magic is granted.
    """
    if set(attributes) != set(ROLLED):
        raise ValueError("nine non-derived DXD attributes required")
    rolls = body["attribute_rolls"]
    if set(rolls) != set(ROLLED):
        raise ValueError("nine original attribute rolls required")
    for v in list(attributes.values()) + list(rolls.values()):
        dxd._int(v, "attribute", 1)
    stature, build = body["stature"], body["build"]
    for value in (stature, build):
        if type(value) is not int or not 0 <= value < len(HEIGHT_WEIGHT):
            raise ValueError("invalid body index")
    height = HEIGHT_WEIGHT[stature][0]
    _, weight, siz = HEIGHT_WEIGHT[build]
    critical = CRITICAL[body["trade"]]
    affinity = body["affinity"]
    if affinity not in critical or rolls[affinity] != max(rolls[k] for k in critical):
        raise ValueError("Affinity must be highest original critical Attribute")
    # Exact signed arithmetic, truncate completed Walk and Run formulas.
    adj = dxd.attribute_dm(attributes["STR"]) + dxd.attribute_dm(attributes["REF"]) - dxd.attribute_dm(siz)
    def trunc_div(n, d):
        return (1 if n >= 0 else -1) * (abs(n) // d)
    walk = trunc_div(stature + 100 + 5 * adj, 20)
    jog = walk + 3
    run = trunc_div(2 * (jog + 3) + adj, 2)
    result = dict(attributes, MOV=run, SIZ=siz, ZED=rolls[affinity])
    dxd.validate_attributes(result)
    physical = physical_properties(result, stature, body)
    return {"physical": physical, "attributes": result, "stature": stature, "build": build,
            "height_inches": height, "weight_pounds": weight,
            "profile": (stature + build) // 2, "walk": walk, "jog": jog,
            "run": run, "affinity": affinity, "trade": body["trade"],
            "attribute_rolls": dict(rolls),
            "physicality": max(result["STR"], siz),
            "resistance": 3 + 4 * siz // 3}

def physical_properties(a, stature, body):
    """Ordinary human baseline; no implicit PML, ancestry or injury modifiers."""
    dxd.validate_attributes(a)
    for_dm = dxd.attribute_dm(a["FOR"])
    # Universal Table scalar values, indices 1 through 19.
    scalars = (12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800)
    if not 1 <= a["FOR"] <= len(scalars):
        raise ValueError("FOR outside supported scalar range")
    scalar = scalars[a["FOR"] - 1]
    lift = a["SIZ"] + a["STR"] // 2 - 9
    shoulder = max(a["STR"], a["SIZ"]) - 9
    carry = min(a["STR"], shoulder) - 3
    basic = {"lift": lift, "shoulder": shoulder, "carry": carry}
    upward = max(a["STR"] - a["SIZ"] - 6, a["MOV"] - 24)
    # PML and Bodypoint adjustments are explicit setting inputs, not guessed.
    hp = max(1, 10 + sum(dxd.attribute_dm(a[k]) for k in ("REF", "POW", "PRE", "MOV")))
    pml = body.get("pml")
    if pml is not None:
        dxd._int(pml, "PML", 1)
        hp += 3 * pml
    bp_adjust = body.get("bodypoint_adjustment")
    if bp_adjust is not None:
        dxd._int(bp_adjust, "Bodypoint adjustment")
    return {"base_hitpoints": hp, "bodypoints": None if bp_adjust is None else max(1, a["SIZ"] + bp_adjust),
            "basic_burden": basic,
            "maximum_burden": {k: v + 5 + for_dm for k, v in basic.items()},
            "jump": {"upward": upward, "broad": upward + stature // 10,
                     "downward": max(a["MOV"] - 12, upward + 3)},
            "gasp_limit_turns": scalar - 10, "sleep_limit_hours": scalar - 5}
