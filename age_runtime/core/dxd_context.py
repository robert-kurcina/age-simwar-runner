"""Bounded native DXD contextual effects, selected from committed facts.

No sentiment inference, arbitrary numerical GM inputs, or universal skill
bonuses. The one-session Emotional disability limit is per owned trait.
"""
from age_runtime.core import dxd

def initialize(state):
    """One independent mission-start Discipline Test; no Favor or forced action."""
    pc = state["dxd"]
    trait = pc["traits"].get("[Addict > Drunkard]")
    if not trait:
        return
    level = trait["level"]
    dm = dxd.attribute_dm(pc["attributes"]["POW"]) + pc["skills"].get("Discipline", 0)
    result = dxd.test(f"{state['seed']}:mission:drunkard", tn=7, dm=dm, penalty=level)
    pc["addicted"] = not result["passed"]
    pc["addiction_check"] = {"trait": "[Addict > Drunkard]", "level": level, "result": result}
    refresh_recovery(pc)

def refresh_recovery(pc):
    # Only the native 1D/hour restorative reduction, not RR recovery.
    pc["concerns"]["restorative_stress_penalty"] = sum(
        t["level"] for n, t in pc["traits"].items() if n.startswith("[Emotional > "))

def effects(state, action, spec):
    pc = state["dxd"]
    if "character_profiles" not in state:
        return [], 0, []
    entries = []
    dm = 0
    emotional = []
    for name, trait in pc["traits"].items():
        level = trait["level"] if isinstance(trait, dict) else trait
        if name == "[Addict > Drunkard]":
            if pc.get("addicted") and spec.get("morale_event"):
                dm += level
                entries.append({"name": name, "dm": level, "penalty": 0})
            elif pc.get("addicted") and spec.get("test_kind") in ("combat_hit", "initiative"):
                entries.append({"name": name, "dm": 0, "penalty": level})
            # Emotional triggers require explicit authored/approved context,
            # never inferred mood. Access is actual carried supply.
            if (spec["attribute"] in ("KNO", "PRE") and
                    set(spec.get("context_tags", [])) & {"sad", "lonely", "angry", "bored"}
                    and state["resources"].get("flask_servings", 0) == 0):
                entries.append({"name": name, "dm": 0, "penalty": level})
        elif name.startswith("[Emotional > "):
            topic = trait.get("context")
            if not spec.get("interaction") or not topic:
                continue
            applicable = (topic == "npc:" + str(action.get("npc")) or
                          topic in spec.get("context_tags", []))
            if applicable and name not in pc.get("emotional_triggered", []):
                entries.append({"name": name, "dm": 0, "penalty": level})
                emotional.append(name)
    return entries, dm, emotional

def record(state, names, result):
    if not names:
        return
    from age_runtime.core import dxd_conditions
    pc = state["dxd"]
    pc.setdefault("emotional_triggered", []).extend(names)
    if not result["passed"]:
        # Misses are not cascades. No cascade resolver exists in this runner.
        # Only the explicitly supported Degree-of-Failure Weariness is applied.
        dxd_conditions.add(pc["concerns"], weariness=result["dof"])

def acquire_commitment_disability(pc, entry):
    if entry["emotional_disability"]:
        name = "[Emotional > Commitment: " + entry["context"] + "]"
        pc["traits"][name] = {"level": 1, "explicit_only": True,
                              "penalty_per_level": 1, "context": "npc:" + entry["context"]}
        refresh_recovery(pc)
