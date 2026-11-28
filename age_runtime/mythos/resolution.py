"""Native player-character DXD Test resolution, separate from action orchestration.

The caller supplies the existing canonical seed digest. This module retains
the established modifier order, Favor policy, Inspiration and Test ledger.
"""
import copy
from age_runtime.core import (
    dxd, dxd_conditions, dxd_inspiration, dxd_modifiers,
    dxd_psychology, dxd_commitment, dxd_context, dxd_injury, dxd_physical_disability,
)

def resolve(state, rules, action, digest):
    """Gather only authored applicable modifiers and allocate Favor before rolling."""
    spec = copy.deepcopy(action["test"])
    interaction = spec.get("interaction")
    if interaction:
        if spec["attribute"] != "PRE" or interaction not in ("ordinary", "pivotal") or action.get("npc") not in state["npcs"]:
            raise ValueError("invalid Interaction Test")
        if dxd.attribute_dm(state["dxd"]["attributes"]["INT"]) >= 2:
            spec["additional_attributes"] = ["INT"]
    cfg = rules["dxd"]
    pc = state["dxd"]
    if "character_profiles" in state and spec.get("morale_event") and "Grit" in pc["skills"]:
        spec["skill"] = "Grit"
    gathered = dxd_modifiers.gather(pc["attributes"], pc["skills"], pc["traits"], spec)
    attr = sum(x["dm"] for x in gathered["attribute"])
    skill = sum(x["dm"] for x in gathered["skill"])
    other = [x["dm"] for key in ("trait", "explicit", "interdisciplinary") for x in gathered[key]]
    contextual, context_dm, emotional_triggers = dxd_context.effects(state, action, spec)
    mods = dxd_modifiers.totals(gathered)
    condition = dxd_conditions.penalty_dice(pc["concerns"], decision=spec.get("decision", False))
    if "injury" in pc:
        condition += dxd_injury.penalty_dice(pc["injury"])
    physical = dxd_physical_disability.penalties(pc.get("injury", {}), spec)
    condition += sum(x["penalty"] for x in physical)
    hook = (dxd_commitment.effective_demeanor(state, action.get("npc"), action) if rules.get("demeanor") and spec["attribute"] == "PRE"
            else 1 if spec.get("relationship_bonus") and state["relationships"][spec["relationship_bonus"]] >= 1 else 0)
    cue = spec.get("inspiration") if not state.get("retired_protagonists") else None
    inspiration_dm = dxd_inspiration.applicable_dm(pc["inspirations"], [cue["tag"]] if cue else [])
    policy = cfg["favor"]
    emicted = dxd.emicted_favor(available=pc["favor"], maximum=policy["maximum"],
                                 enabled=policy.get("emicted", False))
    psychology = dxd_psychology.effects(pc["morale"], spec.get("psychology_context"))
    progression_dm = -(state["progression"]["stage"] - 1) if "progression" in state and spec["attribute"] == "POW" else 0
    emotional_dm = dxd_commitment.modifier(pc, action)
    leverage_dm = dxd_commitment.leverage(state, action)
    character_hook_dm = action.get("character_hook", {}).get("dm", 0)
    components = [character_hook_dm, context_dm, emotional_dm, -leverage_dm if interaction != "pivotal" else 0, attr, skill, hook, inspiration_dm, emicted, spec.get("fixed_dm", 0), psychology["dm"], progression_dm] + other
    favor = dxd.automatic_favor(available=pc["favor"], maximum=policy["maximum"],
                                significance=spec["significance"], desired=policy["desired"])
    net = mods["bonus"] - mods["penalty"] - condition - psychology["penalty"] - sum(x["penalty"] for x in contextual)
    bonus = min(policy["maximum"], max(0, net))
    penalty = max(0, -net)
    args = {"favor": favor, "bonus": bonus}
    npc_gathered = None
    if interaction == "pivotal":
        npc = state["npcs"][action["npc"]]
        npc_attrs = npc["dxd_attributes"]
        target_spec = {"attribute": "INT", **spec.get("opposition", {})}
        npc_gathered = dxd_modifiers.gather(npc_attrs, npc.get("skills", {}), npc.get("dxd_traits", {}), target_spec, player=False)
        target_mods = dxd_modifiers.totals(npc_gathered)
        if "concerns" in npc:
            target_mods["penalty"] += dxd_conditions.penalty_dice(npc["concerns"], decision=spec.get("decision", False))
        # NPCs do not receive the PC-only additional Attribute bonus.
        args = {"active_raw": pc["attributes"]["PRE"], "target_raw": npc_attrs["INT"],
                "active_dm": sum(components) - dxd.attribute_dm(pc["attributes"]["PRE"]),
                "active_bonus": bonus, "active_penalty": penalty, "active_favor": favor,
                "target_dm": target_mods["dm"] - dxd.attribute_dm(npc_attrs["INT"]) + leverage_dm,
                "target_bonus": target_mods["bonus"], "target_penalty": target_mods["penalty"]}
    elif spec.get("narrative"):
        args.update(narrative=True, tn=spec["tn"], dm=sum(max(0, x) for x in components),
                    adversity=sum(max(0, -x) for x in components), adversity_dice=penalty)
    elif "npc_attribute" in spec:
        npc = state["npcs"][action["npc"]]
        args.update(narrative=True, dm=sum(max(0, x) for x in components),
                    adversity=sum(max(0, -x) for x in components), adversity_dice=penalty,
                    npc_dm=dxd.attribute_dm(npc["dxd_attributes"][spec["npc_attribute"]])
                           + spec.get("npc_adversity", 0))
    else:
        args.update(tn=spec["tn"], dm=sum(components), penalty=penalty)
    pc["favor"] -= favor
    chance = dxd_inspiration.opposed_probability(**args) if interaction == "pivotal" else dxd_inspiration.probability(**args)
    seed_parts = [state["seed"], state["turn"]]
    if spec.get("morale_event"):
        seed_parts.append(spec["morale_event"])
    first = (dxd.opposed if interaction == "pivotal" else dxd.test)(digest(seed_parts), **args)
    result = first
    inspired = None
    if (interaction != "pivotal" and not first["passed"] and cue and cfg.get("inspiration", {}).get("enabled")
            and dxd_inspiration.eligible(chance, turn=state["turn"],
                last_turn=pc["inspirations"][-1]["turn"] if pc["inspirations"] else None,
                consequence=cue["consequence"], maximum=policy["maximum"],
                extra_base=favor)):
        inspired = {**({"protagonist_id": state["protagonist"]["id"]} if state.get("protagonist") else {}), "turn": state["turn"], "action": action["id"],
                    "tag": cue["tag"], "memory": cue["memory"],
                    "basis": cue["memory"], "source": "authored"}
        pc["inspirations"].append(inspired)
        retry = dict(args, base=3)
        result = dxd.test(digest(seed_parts + ["inspiration"]), **retry)
        dxd_conditions.add(pc["concerns"], weariness=1)
    dxd_context.record(state, emotional_triggers, result)
    pc["tests"].append({**({"protagonist_id": state["protagonist"]["id"]} if state.get("protagonist") else {}), "turn": state["turn"], "action": action["id"],
                        "inputs": args, "components": {"attribute": attr, "skill": skill,
                        "condition_penalty_dice": condition, **({"physical_location_penalties": physical} if physical else {}), "relationship": hook,
                        **({"emotional_commitment": emotional_dm, "commitment_leverage": leverage_dm} if "commitments" in pc else {}),
                        "inspiration": inspiration_dm, "emicted": emicted, "psychology": psychology, "progression": progression_dm},
                        "gathered": gathered, **({"character_hook": copy.deepcopy(action["character_hook"])} if "character_hook" in action else {}), **({"contextual": contextual, "npc_gathered": npc_gathered} if "character_profiles" in state else {}), "net_bonus": bonus, "net_penalty": penalty,
                        "probability": [chance.numerator, chance.denominator],
                        "initial_result": first, "inspired": inspired is not None,
                        "result": result})
    return result["passed"]
