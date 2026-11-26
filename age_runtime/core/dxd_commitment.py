"""Player-declared, GM-approved DXD Emotional Commitment, NPC scope only."""
from random import Random
from age_runtime.core import dxd_conditions

def eligible(state, rules, action):
    pc = state["dxd"]
    npc = action.get("npc")
    return bool(rules.get("emotional_commitment") and not state["ending"]
                and pc.get("activity", {}).get("status") == "awake"
                and not pc.get("commitments") and npc in state["npcs"]
                and state["npcs"][npc]["encounters"] > 0
                and action.get("location") == state["location"]
                and action.get("test", {}).get("interaction"))

def validate(state, rules, action, request):
    if not isinstance(request, dict) or set(request) != {"context", "level", "vignette"}:
        raise ValueError("invalid Emotional Commitment request")
    if not eligible(state, rules, action) or request["context"] != action.get("npc"):
        raise ValueError("Emotional Commitment unavailable for this context")
    # First use only; no approved background Hook grants a higher level here.
    if type(request["level"]) is not int or request["level"] != 1:
        raise ValueError("initial Commitment must be 1")
    text = request["vignette"]
    if not isinstance(text, str) or not text.strip() or len(text) > 400 or any(ord(c) < 32 for c in text):
        raise ValueError("invalid Commitment vignette")

def modifier(pc, action):
    context = action.get("npc")
    if action.get("commitment"):
        return action["commitment"]["level"]
    return -sum(c["level"] for c in pc.get("commitments", []) if c["context"] == context)

def record(state, action, outcome):
    request = action["commitment"]
    level = request["level"]
    pc = state["dxd"]
    concerns = pc["concerns"]
    rng = Random(f"{state['seed']}:commitment:{state['turn']}:{request['context']}")
    stress = sum(rng.randint(1, 6) for _ in range(level))
    dxd_conditions.add(concerns, fatigue=level, stress=stress, weariness=level)
    concerns["min_stress"] = concerns.get("min_stress", 0) + 1
    dxd_conditions.add(concerns, stress=max(0, concerns["min_stress"] - concerns["stress"]))
    entry = dict(request, turn=state["turn"], at=state["time"], action=action["id"],
                 stress_cost=stress, emotional_disability=bool(outcome["dof"]))
    pc["commitments"].append(entry)
    return entry
