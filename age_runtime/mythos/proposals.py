"""GM-proposed approaches, not model-owned outcomes or world mutations."""
import copy

def compile_action(state, rules, request, choices):
    if not rules.get("gm_proposals") or state["ending"]:
        raise ValueError("GM proposals unavailable")
    if state["dxd"].get("activity", {}).get("status") != "awake":
        raise ValueError("character unavailable")
    if not isinstance(request, dict) or set(request) != {"action", "approach", "intent"}:
        raise ValueError("invalid proposal fields")
    if any(not isinstance(v, str) for v in request.values()):
        raise ValueError("invalid proposal values")
    intent = request["intent"]
    if not intent.strip() or len(intent) > 240 or any(ord(c) < 32 for c in intent):
        raise ValueError("invalid intent")
    target = next((a for a in choices if a["id"] == request["action"]), None)
    if target is None:
        raise ValueError("objective unavailable")
    cfg = rules["gm_proposals"].get(request["action"], {})
    approach = cfg.get(request["approach"])
    if approach is None:
        raise ValueError("approach unavailable for objective")
    if target.get("terminal") or target.get("cost") or target.get("until") or not target.get("test"):
        raise ValueError("unsupported objective")
    # Every authored alternate uses the same stakes, prerequisites, location,
    # consequences and action identity as the original; only Test changes.
    action = copy.deepcopy(target)
    action["test"].update(copy.deepcopy(approach))
    return action
