"""Bounded native DXD contextual effects, selected from committed facts.

No sentiment inference, arbitrary numerical GM inputs, or universal skill
bonuses. The one-session Emotional disability limit is per owned trait.
"""
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
            # Native morale bonus only in established Addicted status.
            # Mission-start Discipline and other addiction effects are separate.
            if pc.get("addicted") and spec.get("morale_event"):
                dm += level
                entries.append({"name": name, "dm": level, "penalty": 0})
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
