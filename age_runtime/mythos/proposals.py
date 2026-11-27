"""GM-proposed approaches, not model-owned outcomes or world mutations."""
import copy
import re
from datetime import datetime


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {"action", "approach", "intent"}:
        raise ValueError("invalid proposal fields")
    if any(not isinstance(v, str) for v in request.values()):
        raise ValueError("invalid proposal values")
    intent = request["intent"]
    if not intent.strip() or len(intent) > 240 or any(ord(c) < 32 for c in intent):
        raise ValueError("invalid intent")

def compile_action(state, rules, request, choices):
    if not rules.get("gm_proposals") or state["ending"]:
        raise ValueError("GM proposals unavailable")
    if state["dxd"].get("activity", {}).get("status") != "awake":
        raise ValueError("character unavailable")
    validate_request(request)
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

def validate_local(rules):
    """Validate reviewed source definitions, not GM-supplied mechanical effects."""
    cfg = rules.get("local_proposals", False)
    if cfg is False:
        return
    if not isinstance(cfg, dict) or not cfg or len(cfg) > 24:
        raise ValueError("invalid local capability configuration")
    if not rules.get("activity") or not rules.get("gm_proposals"):
        raise ValueError("local capabilities require detailed proposal runtime")
    for kind, spec in cfg.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", kind) or not isinstance(spec, dict):
            raise ValueError("invalid capability identity")
        required = {"target", "seconds", "resolution"}
        allowed = required | {"test", "concern_failure", "established", "count_evidence"}
        if not required <= set(spec) or set(spec) - allowed:
            raise ValueError("invalid capability fields")
        if spec["target"] not in ("location", "npc") or type(spec["seconds"]) is not int or not 10 <= spec["seconds"] <= 3600:
            raise ValueError("invalid capability scope or duration")
        if type(spec.get("count_evidence", False)) is not bool:
            raise ValueError("invalid evidence count policy")
        marker = spec.get("established")
        if marker is not None and (not isinstance(marker, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", marker)):
            raise ValueError("invalid capability completion marker")
        if spec["resolution"] == "certain":
            if spec["target"] != "location" or "test" in spec or "concern_failure" in spec:
                raise ValueError("certain capability cannot adjudicate NPCs or Test effects")
        elif spec["resolution"] == "test":
            test = spec.get("test")
            fields = {"attribute", "skill", "tn", "significance", "decision"}
            if not isinstance(test, dict) or not fields <= set(test) or set(test) - fields - {"interaction"}:
                raise ValueError("invalid capability Test")
            if (test["attribute"] not in rules["dxd"]["attributes"] or test["skill"] not in rules["dxd"]["skills"]
                    or type(test["tn"]) is not int or not 2 <= test["tn"] <= 18
                    or test["significance"] not in ("routine", "minor", "important", "critical")
                    or type(test["decision"]) is not bool):
                raise ValueError("invalid native capability Test")
            if "interaction" in test and (test["interaction"] != "ordinary" or spec["target"] != "npc"
                    or test["attribute"] != "PRE" or not rules.get("demeanor")):
                raise ValueError("invalid capability Interaction Test")
            costs = spec.get("concern_failure", {})
            if not isinstance(costs, dict) or set(costs) - {"fatigue", "stress", "weariness"} or any(type(v) is not int or not 0 <= v <= 6 for v in costs.values()):
                raise ValueError("invalid capability Concern consequence")
        else:
            raise ValueError("unsupported capability resolution")


def local_capabilities(state, rules, npc_available):
    """Derive eligible targets, never manufacture an entity or a Test."""
    cfg = rules.get("local_proposals")
    if not cfg or state["ending"] or state["dxd"].get("activity", {}).get("status") != "awake":
        return []
    from age_runtime.mythos.epistemic import conversation_available
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds()
    result = []
    for kind, spec in cfg.items():
        if spec["seconds"] > remaining:
            continue
        targets = [state["location"]] if spec["target"] == "location" else [
            nid for nid, npc in sorted(state["npcs"].items())
            if npc["encounters"] and conversation_available(state, rules, nid, npc_available)]
        for target in targets:
            action = "local:" + kind + ":" + target
            if action not in state["used"]:
                result.append({"action": action, "approach": kind, "target": target,
                               "resolution": spec["resolution"], "seconds": spec["seconds"]})
    return result


def compile_local(state, rules, request, npc_available):
    validate_request(request)
    cap = next((c for c in local_capabilities(state, rules, npc_available)
                if c["action"] == request["action"] and c["approach"] == request["approach"]), None)
    if cap is None:
        raise ValueError("local capability unavailable")
    kind, target = cap["approach"], cap["target"]
    spec = rules["local_proposals"][kind]
    loc, seconds = state["location"], spec["seconds"]
    action = {"id": cap["action"], "label": kind, "location": loc,
              "duration_seconds": seconds, "local_seconds": seconds, "interval_seconds": 600,
              "activity": "active", "route": {"nodes": [loc], "seconds": 0, "minutes": 0, "terrain": []},
              "local_capability": kind, "local_spec": copy.deepcopy(spec)}
    if spec["target"] == "npc":
        action["npc"] = target
    if spec["resolution"] == "test":
        action["test"] = copy.deepcopy(spec["test"])
        action["concern_failure"] = copy.deepcopy(spec.get("concern_failure", {}))
    return action


def record_local(state, action, success, result):
    """Record only source-authorized completion; no manufactured Test margin."""
    kind, spec = action["local_capability"], action["local_spec"]
    record = {"kind": kind, "target": action.get("npc", state["location"]),
              "at": state["time"], "turn": state["turn"], "passed": success,
              "effect": result["margin"] if result is not None else None}
    if spec.get("count_evidence"):
        record["evidence_count"] = len(state["discoveries"])
    if success and spec.get("established"):
        record["established"] = spec["established"]
    state["local_records"].append(record)


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
