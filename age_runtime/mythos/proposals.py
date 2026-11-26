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

def local_capabilities(state, rules, npc_available):
    """Derive proposal targets from current world state, not from invented entities."""
    if not rules.get("local_proposals") or state["ending"] or state["dxd"].get("activity", {}).get("status") != "awake":
        return []
    result = []
    for key, npc in sorted(state["npcs"].items()):
        if npc["encounters"] and npc_available(state, rules, {"npc": key, "location": state["location"]}):
            for kind in ("build_rapport",):
                action = "local:" + kind + ":" + key
                if action not in state["used"]:
                    result.append({"action": action, "approach": kind, "target": key})
    for kind in ("survey", "compose_notes"):
        action = "local:" + kind + ":" + state["location"]
        if action not in state["used"]:
            result.append({"action": action, "approach": kind, "target": state["location"]})
    return result

def compile_local(state, rules, request, npc_available):
    if not isinstance(request, dict) or set(request) != {"action", "approach", "intent"} or any(not isinstance(v, str) for v in request.values()):
        raise ValueError("invalid local proposal")
    if not request["intent"].strip() or len(request["intent"]) > 240 or any(ord(c) < 32 for c in request["intent"]):
        raise ValueError("invalid intent")
    cap = next((c for c in local_capabilities(state, rules, npc_available)
                if c["action"] == request["action"] and c["approach"] == request["approach"]), None)
    if cap is None:
        raise ValueError("local capability unavailable")
    kind, target = cap["approach"], cap["target"]
    loc = state["location"]
    action = {"id": cap["action"], "label": kind, "location": loc,
              "duration_seconds": 600, "local_seconds": 600, "interval_seconds": 600,
              "activity": "active", "route": {"nodes": [loc], "seconds": 0, "minutes": 0, "terrain": []},
              "local_capability": kind}
    if kind in ("build_rapport",):
        action.update(npc=target, test={"attribute": "PRE", "skill": "Persuade" if "Persuade" in state["dxd"]["skills"] else "Interview",
                    "interaction": "ordinary", "tn": 7, "significance": "minor", "decision": True},
                    concern_failure={"stress": 1})
    else:
        action["test"] = {"attribute": "INT", "skill": "Investigate" if "Investigate" in state["dxd"]["skills"] else "Investigation", "tn": 7,
                          "significance": "minor", "decision": False}
        action["concern_failure"] = {"fatigue": 1}
    return action

def record_local(state, action, success, result):
    """Bounded semantic record: no invented observations, evidence, or promises."""
    kind = action["local_capability"]
    record = {"kind": kind, "target": action.get("npc", state["location"]),
              "at": state["time"], "turn": state["turn"], "passed": success,
              "effect": result["margin"]}
    if kind == "compose_notes":
        record["evidence_count"] = len(state["discoveries"])
    state["local_records"].append(record)
    # A successful local survey or note preparation can support later
    # ordinary GM interpretation, but grants no canonical clue or score.
    if success and kind in ("survey", "compose_notes"):
        record["established"] = "survey_completed" if kind == "survey" else "notes_organized"

def prepared_duration(state, action, seconds):
    """Apply one authored local preparation benefit, before travel is added.

    Derive it from completed records; no consumable bonus or parallel state.
    Only fixed-duration, nonrepeatable activities can be configured.
    """
    cfg = action.get("preparation")
    if cfg is None:
        return seconds, 0
    kind, saving = cfg["kind"], cfg["seconds"]
    if (kind not in ("survey", "compose_notes") or type(saving) is not int
            or not 0 < saving < seconds or action.get("repeatable")
            or "until" in action or not action.get("location")):
        raise ValueError("invalid preparation duration")
    eligible = any(r["kind"] == kind and r["target"] == action["location"]
                   and r["passed"] and r.get("evidence_count", 0) >= cfg.get("min_evidence", 0)
                   for r in state.get("local_records", []))
    return (seconds - saving, saving) if eligible else (seconds, 0)
