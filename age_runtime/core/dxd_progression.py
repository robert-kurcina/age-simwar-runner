"""Fear! PML-independent professional qualification and development arithmetic.

No lifetime simulation and no automatic XP awards or promotion. Skill levels
remain authoritative character properties, not a second profession bonus.
"""
from age_runtime.core import dxd

AGE_GROUPS = ("Youth", "Early Teen", "Teenager", "Young Adult", "Adult",
              "Mature", "Middle Age", "Elder", "Aged", "Venerable")
# DXD Book IV Warrior progression, counts and minimum levels by rank.
REQUIREMENTS = (
    ((0, 2), (0, 2), (0, 2), (0, 2)),
    ((1, 2), (0, 2), (0, 2), (0, 2)),
    ((2, 2), (0, 2), (0, 2), (0, 2)),
    ((3, 2), (1, 2), (0, 2), (0, 2)),
    ((4, 2), (2, 2), (0, 2), (0, 2)),
    ((5, 2), (3, 2), (1, 2), (0, 2)),
    ((6, 2), (4, 2), (2, 2), (0, 2)),
    ((6, 3), (5, 2), (3, 2), (0, 2)),
    ((7, 3), (5, 3), (4, 2), (1, 2)),
    ((8, 3), (5, 4), (4, 3), (2, 3)),
    ((9, 3), (5, 5), (4, 4), (3, 4)),
)
ATTRIBUTE_IM = {"CCA": 5, "RCA": 3, "REF": 9, "INT": 7, "KNO": 3,
                "POW": 4, "PRE": 3, "STR": 5, "FOR": 6}

def level(value):
    return dxd._int(value["level"] if isinstance(value, dict) else value, "skill level", 1)

def cumulative_cost(im, desired):
    dxd._int(im, "IM", 1)
    dxd._int(desired, "level", 0)
    return im * desired * (desired + 1) // 2

def fast_track_budget(age_years, rank):
    dxd._int(age_years, "age", 0)
    dxd._int(rank, "professional rank", 0)
    if rank > 10:
        raise ValueError("rank outside progression table")
    return age_years + 3 * rank

def xp_to_skillpoints(xp):
    return divmod(dxd._int(xp, "XP", 0), 100)

def soft_limit(source_base, attributes, rank, relevant):
    if source_base not in (1, 2, 3, 4):
        raise ValueError("invalid Skill source")
    return max(1, source_base + max(dxd.attribute_dm(attributes["KNO"]),
                                   dxd.attribute_dm(attributes["INT"]))
               + (rank // 3 if relevant else 0))

def qualification(skills, career, rank):
    dxd._int(rank, "professional rank", 0)
    if rank > 10:
        raise ValueError("rank outside progression table")
    # Native Ladder uses the entire career list; mandatory lists additionally
    # require their own counts. A specialization is one distinct owned skill.
    all_names = set().union(*(set(career[k]) for k in ("ladder", "A", "B", "C")))
    groups = [all_names, set(career["A"]), set(career["B"]), set(career["C"])]
    result = []
    for name, allowed, (count, minimum) in zip(("ladder", "A", "B", "C"), groups, REQUIREMENTS[rank]):
        found = sorted(k for k, v in skills.items()
                       if k.split(" > ", 1)[0] in allowed and level(v) >= minimum)
        result.append({"group": name, "required": count, "minimum_level": minimum,
                       "qualified_skills": found, "shortfall": max(0, count - len(found))})
    return {"rank": rank, "qualified": not any(r["shortfall"] for r in result), "requirements": result}

def attribute_quote(attribute, increments, target_increments):
    """Fear! provisional +3 purchased growth ceiling; no PML substitute."""
    im = ATTRIBUTE_IM[attribute]
    dxd._int(increments, "purchased increments", 0)
    dxd._int(target_increments, "target increments", 1)
    if not increments < target_increments <= 3:
        raise ValueError("attribute exceeds Fear purchased-growth ceiling")
    return {"skillpoints": cumulative_cost(im, target_increments) - cumulative_cost(im, increments),
            "months": sum(im * n for n in range(increments + 1, target_increments + 1))}

def describe(profile, careers):
    background, intrinsic = profile["background"], profile["intrinsics"]
    prof = profile["proficiencies"]
    age, age_rank = background["age_years"], background["age_rank"]
    if not 0 <= age_rank < len(AGE_GROUPS) or AGE_GROUPS[age_rank] != background["age_group"]:
        raise ValueError("inconsistent age group")
    rank = intrinsic["professional_rank"]
    career = careers[intrinsic["profession"]]
    result = qualification(prof["skills"], career, rank)
    result["bonus_skillpoints"] = fast_track_budget(age, rank)
    result["age_rank"] = age_rank
    result["prior_careers"] = [
        {"profession": c["profession"], **qualification(prof["skills"], careers[c["profession"]], c["attained_rank"])}
        for c in intrinsic.get("prior_careers", [])]
    return result
