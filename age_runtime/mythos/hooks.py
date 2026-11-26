"""One recorded, context-scoped DXD Character Hook per Test."""
import copy

def offers(state, rules, action):
    if not action.get("test"):
        return []
    result = []
    for key, cfg in rules.get("character_hooks", {}).items():
        if action["id"] not in cfg["actions"]:
            continue
        if not all(f in state["flags"] for f in cfg.get("requires_flags", [])):
            continue
        # A Hook must be distinct from already applied proficiency or memory.
        spec = action["test"]
        used = [spec.get("skill"), *spec.get("additional_skills", []), *spec.get("traits", [])]
        if set(cfg.get("exclusive_skills", [])) & set(used):
            continue
        if spec.get("inspiration", {}).get("tag") in cfg.get("exclusive_inspiration", []):
            continue
        result.append({"id": key, "fact": cfg["fact"], "dm": cfg["dm"]})
    return result

def apply(state, rules, action, cue):
    if cue is None:
        return action
    if not isinstance(cue, dict) or set(cue) != {"id", "basis"}:
        raise ValueError("invalid Character Hook")
    if not isinstance(cue["basis"], str) or not cue["basis"].strip() or len(cue["basis"]) > 240 or any(ord(c)<32 for c in cue["basis"]):
        raise ValueError("invalid Hook basis")
    match = next((x for x in offers(state, rules, action) if x["id"] == cue["id"]), None)
    if match is None:
        raise ValueError("Character Hook unavailable")
    result = copy.deepcopy(action)
    result["character_hook"] = {**match, "basis": cue["basis"]}
    return result

def split(request):
    if not isinstance(request, dict) or "hook" not in request:
        return request, None
    if request["hook"] is None:
        raise ValueError("empty Hook")
    return {k:v for k,v in request.items() if k != "hook"}, request["hook"]
