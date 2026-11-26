"""DXD Character Hooks, automatically enforced in the lightweight runner.

A deterministic authored scope identifies a material Test effect. The GM
narrates it without choosing the PC's voluntary behavior. Full-stack player
enactment can later replace the automatic selection policy.
"""
import copy

def scene_key(state):
    return state.get("pacing", {}).get("scene", state["location"])

def offers(state, rules, action):
    spec = action.get("test")
    if not spec:
        return []
    result = []
    for key, cfg in sorted(rules.get("character_hooks", {}).items()):
        if action["id"] not in cfg["actions"]:
            continue
        if not all(f in state["flags"] for f in cfg.get("requires_flags", [])):
            continue
        if not set(cfg.get("context_tags", [])) <= set(spec.get("context_tags", [])):
            continue
        used = [spec.get("skill"), *spec.get("additional_skills", []), *spec.get("traits", [])]
        if set(cfg.get("exclusive_skills", [])) & set(used):
            continue
        if spec.get("inspiration", {}).get("tag") in cfg.get("exclusive_inspiration", []):
            continue
        if cfg.get("exclusive_commitment") and action.get("commitment"):
            continue
        # No duplicate penalty for an already controlling native disability.
        if cfg.get("exclusive_trait") in state["dxd"].get("traits", {}):
            continue
        dm = cfg["dm"]
        if type(dm) is not int or dm not in (-3, -2, -1, 1):
            raise ValueError("unsupported Character Hook DM")
        result.append({"id": key, "fact": cfg["fact"], "dm": dm,
                       "emphasis": cfg.get("emphasis", False)})
    return result

def apply(state, rules, action):
    choices = offers(state, rules, action)
    persistent = circumstances(state, rules, action)
    if persistent:
        # Same fact is promoted, not stacked. One controlling narrative modifier.
        choices = [x for x in choices if x["id"] not in {p.get("replaces") for p in persistent}]
        choices.extend(persistent)
    if not choices:
        return action
    # Adverse circumstances take precedence over beneficial cues. Stable tie
    # order; only one Hook per Test. Repeat effects remain, repeat XP does not.
    match = min(choices, key=lambda x: (x["dm"] > 0, -abs(x["dm"]), x["id"]))
    result = copy.deepcopy(action)
    result["character_hook"] = match
    return result

def split(request):
    if isinstance(request, dict) and "hook" in request:
        raise ValueError("Character Hooks are automatically resolved in this runner")
    return request, None

def award(state, key, penalty, *, source):
    if penalty < 1:
        return 0
    pc = state["dxd"]
    scene = scene_key(state)
    awards = pc.setdefault("emphasis_awards", [])
    if any(e["id"] == key and e["scene"] == scene for e in awards):
        return 0
    xp = 5 if penalty == 1 else 10 if penalty == 2 else 20
    awards.append({"id": key, "scene": scene, "turn": state["turn"],
                   "xp": xp, "source": source, "adjtn": penalty})
    pc["xp"] = pc.get("xp", 0) + xp
    return xp

def record(state, action, test):
    """One award for an executed Test, never for a declaration or retry.

    Native contextual penalty dice use the Narrative equivalent +3 TN per
    die. No XP for mission checks, passive recovery, or ordinary Conditions.
    """
    candidates = []
    hook = action.get("character_hook", {})
    if hook.get("emphasis") and hook["dm"] < 0:
        candidates.append((-hook["dm"], hook.get("replaces") or hook["id"], hook.get("source", "character_hook")))
    for entry in test.get("contextual", []):
        if entry["penalty"] > 0 and entry["name"].startswith(("[Emotional > ", "[Addict > ")):
            candidates.append((3 * entry["penalty"], entry["name"], "native_disability"))
    if candidates:
        penalty, key, source = max(candidates, key=lambda x: (x[0], x[1]))
        return award(state, key, penalty, source=source)
    return 0

def circumstances(state, rules, action):
    """Derive persistent modifiers from committed flags/clock evidence.

    No new mutable state and no model-created numerical adjustments.
    A circumstance must explicitly establish its scope and termination.
    """
    if not action.get("test"):
        return []
    result = []
    for key, cfg in sorted(rules.get("persistent_circumstances", {}).items()):
        if action["id"] not in cfg["actions"]:
            continue
        if not all(f in state["flags"] for f in cfg["requires_flags"]):
            continue
        if any(f in state["flags"] for f in cfg.get("excludes_flags", [])):
            continue
        dm = cfg["dm"]
        if type(dm) is not int or dm not in (-3, 3):
            raise ValueError("persistent circumstance must be +/-3")
        clock = cfg.get("clock")
        if clock and not state.get("narrative_events", {}).get("clocks", {}).get(clock, {}).get("resolved"):
            continue
        result.append({"id": key, "fact": cfg["fact"], "dm": dm,
                       "source": "persistent_circumstance",
                       "replaces": cfg.get("replaces"),
                       "emphasis": cfg.get("emphasis", False)})
    return result
