"""Bounded DXD modifier gathering; scenario supplies independently relevant sources.

Book II Gathering DMs, pinned vault-sarnalen a6e0058e340a63c9cf4f9c6fd26a75c340569782.
Only explicit linear per-level effects are supported here. Do not infer
applicability or mechanical effects from names or descriptive prose.
"""
from age_runtime.core import dxd

def effective_level(level, position):
    dxd._int(level, "level", 1)
    if position not in (1, 2, 3):
        raise ValueError("invalid contribution position")
    return max(1 if level >= 2 else 0, level // position)

def _unique(names, limit):
    if not isinstance(names, list) or len(names) > limit or len(set(names)) != len(names):
        raise ValueError("duplicate or excessive modifier sources")
    return names

def gather(attributes, skills, traits, spec, *, player=True):
    """Return auditable fixed DMs and modifier dice, before flattening.

    Skills with integer values use the ordinary +level rule. Structured
    sources define per-level signed fixed DM and dice. Explicit effects are
    named, action-selected contributions of owned traits/skills, with full
    level and no duplicate source contribution. A supported interdisciplinary
    effect is selected once, not treated as another divided skill.
    """
    result = {"attribute": [], "skill": [], "trait": [], "explicit": [], "interdisciplinary": []}
    driving = spec["attribute"]
    additional = _unique(spec.get("additional_attributes", []), 2)
    if driving in additional or additional and not player:
        raise ValueError("invalid secondary Attribute")
    for position, name in enumerate([driving] + additional, 1):
        dm = dxd.attribute_dm(attributes[name])
        if position > 1:
            if dm < 2:
                raise ValueError("secondary Attribute DM must be at least +2")
            dm //= position
        result["attribute"].append({"name": name, "dm": dm, "bonus": 0, "penalty": 0})

    used = set()
    def contribute(kind, name, position, category):
        key = (kind, name)
        if key in used:
            raise ValueError("duplicate modifier source")
        used.add(key)
        source = (skills if kind == "skill" else traits)[name]
        if type(source) is int:
            source = {"level": source, "dm_per_level": 1}
        level = effective_level(source["level"], position)
        if category == "interdisciplinary" and not source.get("interdisciplinary", False):
            raise ValueError("not an interdisciplinary Skill")
        if category != "interdisciplinary" and source.get("interdisciplinary", False):
            raise ValueError("interdisciplinary Skill requires explicit supporting slot")
        if source.get("explicit_only", False) and category != "explicit":
            raise ValueError("explicit-only source requires trigger")
        dm = dxd._int(source.get("dm_per_level", 0), "DM per level") * level
        bonus = dxd._int(source.get("bonus_per_level", 0), "bonus per level", 0) * level
        penalty = dxd._int(source.get("penalty_per_level", 0), "penalty per level", 0) * level
        result[category].append({"name": name, "kind": kind, "level": source["level"],
                                 "effective_level": level, "dm": dm, "bonus": bonus, "penalty": penalty})

    names = ([spec["skill"]] if "skill" in spec else []) + spec.get("additional_skills", [])
    if "additional_skills" in spec and "skill" not in spec:
        raise ValueError("secondary Skills require primary Skill")
    for pos, name in enumerate(_unique(names, 3), 1):
        contribute("skill", name, pos, "skill")
    for pos, name in enumerate(_unique(spec.get("traits", []), 3), 1):
        contribute("trait", name, pos, "trait")
    for effect in spec.get("explicit_effects", []):
        if effect["kind"] not in ("skill", "trait"):
            raise ValueError("unknown explicit source kind")
        contribute(effect["kind"], effect["name"], 1, "explicit")
    if "interdisciplinary" in spec:
        contribute("skill", spec["interdisciplinary"], 1, "interdisciplinary")
    return result

def totals(gathered):
    entries = [entry for group in gathered.values() for entry in group]
    return {key: sum(entry[key] for entry in entries) for key in ("dm", "bonus", "penalty")}
