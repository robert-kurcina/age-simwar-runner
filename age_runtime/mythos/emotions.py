"""Scenario-bounded emotional episodes and native Concern consequences."""
import copy
import re
from age_runtime.core import dxd_conditions

def record(state, rules, request, npc_available, text):
    cfg = rules.get("interpersonal_duress")
    required = {"id", "npc", "claim_ids", "emotion", "intensity", "expression", "cause", "stress"}
    if not cfg or not isinstance(request, dict) or not required <= set(request) or set(request) - required - {"observation"}:
        raise ValueError("invalid emotional episode")
    eid, npc = request["id"], request["npc"]
    if not isinstance(eid, str) or not re.fullmatch(r"emo:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid emotional episode identity")
    if (not isinstance(npc, str) or npc not in state["npcs"]
            or state["npcs"][npc]["location"] != state["location"]
            or not npc_available(state, rules, {"npc": npc, "location": state["location"]})):
        raise ValueError("emotional participant unavailable")
    if rules.get("dialogue_requires_encounter"):
        from age_runtime.mythos.epistemic import conversation_available
        if not conversation_available(state, rules, npc, npc_available):
            raise ValueError("emotional episode requires current authored encounter")
    ledger = state["emotional_episodes"]
    if len(ledger) >= 256 or any(e["id"] == eid for e in ledger):
        raise ValueError("duplicate emotional episode or record limit")
    ids = request["claim_ids"]
    observation = None
    if "observation" in request:
        observation = next((o for o in state.get("action_observations", [])
                            if o["id"] == request["observation"] and o["npc"] == npc), None)
        if not rules.get("action_observations") or not observation:
            raise ValueError("episode requires NPC observation provenance")
    if not isinstance(ids, list) or not (0 if observation else 1) <= len(ids) <= 4 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid emotional episode references")
    claims = {c["id"]: c for c in state["dialogue"]}
    for i in ids:
        c = claims.get(i)
        if (not c or {c["speaker"], c["listener"]} != {"pc", npc}
                or c["location"] != state["location"] or c["turn"] != state["turn"]):
            raise ValueError("episode requires current actual exchange")
    intensity = request["intensity"]
    if intensity not in ("restrained", "elevated", "acute", "subsiding"):
        raise ValueError("invalid expression intensity")
    emotion = text(request["emotion"], 120)
    expression = text(request["expression"], 240)
    cause = text(request["cause"], 240)
    stress = request["stress"]
    if not isinstance(stress, dict) or set(stress) - {"pc", npc}:
        raise ValueError("invalid exposed actors")
    for actor, tier in stress.items():
        if not isinstance(tier, str) or tier not in cfg["stress_awards"]:
            raise ValueError("unsupported duress severity")
        if observation:
            if actor == "pc" and not ids and observation["kind"] != "witnessed":
                raise ValueError("PC duress requires current exposure")
            if observation["turn"] != state["turn"] or observation["location"] != state["location"]:
                raise ValueError("new duress requires current observation exposure")
            if any(actor in e["awards"] and e.get("action") == observation["action"] for e in ledger):
                raise ValueError("action duress already charged")
        # A claim may support a later description, but not a second award.
        if any(actor in e["awards"] and (set(ids) & set(e["claim_ids"])
                    or (e["npc"] == npc and e["turn"] == state["turn"]
                        and e["location"] == state["location"])) for e in ledger):
            raise ValueError("duress already charged for this exchange")
    # Values are bounded scenario policy, not an inferred emotional scale.
    awards = {actor: cfg["stress_awards"][tier] for actor, tier in stress.items()}
    for actor, amount in awards.items():
        concerns = state["dxd"]["concerns"] if actor == "pc" else state["npcs"][actor]["concerns"]
        dxd_conditions.add(concerns, stress=amount)
        if actor != "pc" and rules.get("npc_abstract_recovery"):
            state["npcs"][actor]["activity_plan"] = None
        if actor != "pc" and "activity" in state["npcs"][actor]:
            dxd_conditions.refresh_sleep_limit(concerns, state["npcs"][actor]["activity"], state["npcs"][actor]["dxd_attributes"])
    if "pc" in awards and "activity" in state["dxd"]:
        dxd_conditions.refresh_sleep_limit(state["dxd"]["concerns"], state["dxd"]["activity"], state["dxd"]["attributes"])
    ledger.append({"id": eid, "npc": npc, "claim_ids": list(ids), "emotion": emotion,
                   "intensity": intensity, "expression": expression, "cause": cause,
                   "severity": copy.deepcopy(stress), "awards": awards, "turn": state["turn"],
                   "at": state["time"], "location": state["location"],
                   **({"observation": observation["id"], "action": observation["action"]} if observation else {})})

def projection(state, participants):
    result = {}
    for npc in sorted(participants):
        if "concerns" not in state["npcs"][npc]:
            continue
        episodes = [e for e in state.get("emotional_episodes", []) if e["npc"] == npc]
        # Historical salience is not current Stress or a fresh award.
        older = [e for e in episodes[:-6] if e["intensity"] == "acute"
                 or e.get("observation") or any(v in ("significant", "severe")
                                               for v in e.get("severity", {}).values())][-4:]
        concerns = state["npcs"][npc]["concerns"]
        result[npc] = {"last_episode": copy.deepcopy(episodes[-1]) if episodes else None,
                       "recent_episodes": copy.deepcopy(episodes[-6:]),
                       "salient_history": copy.deepcopy(older),
                       "concerns": copy.deepcopy(concerns),
                       "degrees": dxd_conditions.degrees(concerns),
                       "condition": dxd_conditions.describe(concerns)}
    return result
