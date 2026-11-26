"""Contextual nomination of owned DXD sources, with authored scope guards.

The GM interprets relevance. The runtime validates the permissible source
set and prerequisites and derives all numerical effects from owned records.
"""
import copy
from age_runtime.core import dxd_modifiers

def offer(state, rules, action):
    if not rules.get("modifier_nominations") or not action.get("test"):
        return None
    cfg = rules["modifier_nominations"].get(action["id"])
    if cfg is None and action.get("local_capability"):
        cfg = rules["modifier_nominations"].get("local:" + action["local_capability"])
    if cfg is None:
        return None
    if not all(f in state["flags"] for f in cfg.get("requires_flags", [])):
        return None
    pc = state["dxd"]
    spec = action["test"]
    skills = [n for n in cfg.get("skills", []) if n in pc["skills"]
              and n != spec.get("skill") and n not in spec.get("additional_skills", [])]
    traits = [n for n in cfg.get("traits", []) if n in pc["traits"]
              and not (isinstance(pc["traits"][n], dict) and pc["traits"][n].get("explicit_only", False))
              and n not in spec.get("traits", [])]
    return {"skills": skills, "traits": traits}

def apply(state, rules, action, nomination):
    if nomination is None:
        return action
    if not isinstance(nomination, dict) or set(nomination) != {"skills", "traits", "basis"}:
        raise ValueError("invalid modifier nomination")
    basis = nomination["basis"]
    if not isinstance(basis, str) or not basis.strip() or len(basis) > 240 or any(ord(c) < 32 for c in basis):
        raise ValueError("invalid nomination basis")
    permitted = offer(state, rules, action)
    if permitted is None:
        raise ValueError("modifier nominations unavailable")
    result = copy.deepcopy(action)
    spec = result["test"]
    for kind in ("skills", "traits"):
        names = nomination[kind]
        if not isinstance(names, list) or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names) or not set(names) <= set(permitted[kind]):
            raise ValueError("unowned or inapplicable nominated " + kind)
        if kind == "skills" and names:
            if "skill" not in spec:
                spec["skill"], names = names[0], names[1:]
            spec["additional_skills"] = spec.get("additional_skills", []) + names
        elif kind == "traits" and names:
            spec["traits"] = spec.get("traits", []) + names
    pc = state["dxd"]
    # Validate slot limits, duplicates and native diminishing effects before
    # any time, resource or RNG operation.
    dxd_modifiers.gather(pc["attributes"], pc["skills"], pc["traits"], spec)
    return result

def split(request):
    if not isinstance(request, dict) or "nomination" not in request:
        return request, None
    if request["nomination"] is None:
        raise ValueError("empty modifier nomination")
    return {k: v for k, v in request.items() if k != "nomination"}, request["nomination"]

def projection(state, rules, legal, npc_available):
    """Offer scopes for compiled methods, not just default action Tests."""
    from age_runtime.mythos import proposals, beats
    result = []
    if not rules.get("modifier_nominations"):
        return result
    def add(request, action):
        scope = offer(state, rules, action)
        if scope and any(scope.values()):
            result.append({"action": request["action"], "approach": request["approach"], **scope})
    for action in legal:
        for approach in rules.get("gm_proposals", {}).get(action["id"], {}):
            request = {"action": action["id"], "approach": approach, "intent": "scope preview"}
            try:
                compiled = proposals.compile_action(state, rules, request, [action])
            except ValueError:
                continue
            add(request, compiled)
    for cap in proposals.local_capabilities(state, rules, npc_available):
        request = {"action": cap["action"], "approach": cap["approach"], "intent": "scope preview"}
        add(request, proposals.compile_local(state, rules, request, npc_available))
    for cap in beats.available(state, rules):
        request = {"action": cap["action"], "approach": cap["approach"], "intent": "scope preview"}
        add(request, beats.compile_beat(state, rules, request))
    return result
