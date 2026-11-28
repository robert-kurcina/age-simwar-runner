"""GM-proposed approaches, not model-owned outcomes or world mutations."""
import copy
import re
from datetime import datetime
from age_runtime.core import dxd
from age_runtime.mythos import pacing, establishment, object_actions


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
        required = {"target", "resolution"}
        allowed = required | {"seconds", "variable_interval_seconds", "test", "concern_failure", "established", "count_evidence", "requires_evidence", "object_effect", "resumable", "access"}
        if not required <= set(spec) or set(spec) - allowed:
            raise ValueError("invalid capability fields")
        if spec["target"] not in ("location", "npc", "object"):
            raise ValueError("invalid capability scope")
        if spec["target"] == "object":
            if not rules.get("narrative_custody") or not rules.get("consequential_objects"):
                raise ValueError("object capabilities require custody and lifecycle authority")
            if spec.get("object_effect") != "inspect":
                raise ValueError("local object capabilities support inspection only")
        elif "object_effect" in spec:
            raise ValueError("object effect requires object target")
        if "access" in spec and (spec["target"] != "object" or spec["access"] not in ("held", "held_or_unheld")):
            raise ValueError("invalid object access policy")
        duration_range(spec)
        if "resumable" in spec and (type(spec["resumable"]) is not bool or
                spec["target"] != "location" or "variable_interval_seconds" not in spec):
            raise ValueError("resumption requires reviewed variable location task")
        if type(spec.get("requires_evidence", 0)) is not int or spec.get("requires_evidence", 0) < 0:
            raise ValueError("invalid capability evidence prerequisite")
        if type(spec.get("count_evidence", False)) is not bool:
            raise ValueError("invalid evidence count policy")
        marker = spec.get("established")
        if marker is not None and (not isinstance(marker, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", marker)):
            raise ValueError("invalid capability completion marker")
        if spec["resolution"] == "certain":
            if spec["target"] == "npc" or "test" in spec or "concern_failure" in spec:
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


def duration_range(spec):
    """A capability has exactly one reviewed duration model."""
    if ("seconds" in spec) == ("variable_interval_seconds" in spec):
        raise ValueError("specify exactly one capability duration model")
    if "seconds" in spec:
        seconds = spec["seconds"]
        if type(seconds) is not int or not 10 <= seconds <= 3600:
            raise ValueError("invalid fixed capability duration")
        return seconds, seconds
    interval = spec["variable_interval_seconds"]
    if type(interval) is not int or interval not in pacing.INTERVALS:
        raise ValueError("unsupported variable Time Interval")
    return 3 * interval, 18 * interval


def pending_work(state, action_id):
    return state.get("pending_work", {}).get(action_id)


def pause_work(state, action, started, reason):
    """Credit only elapsed work for explicitly reviewed resumable tasks."""
    if not action.get("local_spec", {}).get("resumable") or reason not in ("event", "involuntary_sleep", "unconsciousness"):
        return
    elapsed = int((datetime.fromisoformat(state["time"]) - started).total_seconds())
    prior = pending_work(state, action["id"])
    total = action["task_duration"]["seconds"]
    worked = (prior["worked_seconds"] if prior else 0) + elapsed
    if 0 < worked < total:
        state.setdefault("pending_work", {})[action["id"]] = {
            "task_duration": copy.deepcopy(action["task_duration"]),
            "worked_seconds": worked, "location": state["location"],
            "evidence": copy.deepcopy(state["discoveries"])}


def resolve_duration(state, action):
    """Resolve only after accepted proposal validation; previews never roll."""
    spec = action.get("local_spec", {})
    if "variable_interval_seconds" not in spec:
        return action
    prior = pending_work(state, action["id"])
    if prior and spec.get("resumable"):
        roll = copy.deepcopy(prior["task_duration"])
        remaining = roll["seconds"] - prior["worked_seconds"]
        return dict(action, duration_seconds=remaining, local_seconds=remaining, task_duration=roll)
    interval = spec["variable_interval_seconds"]
    roll = dxd.task_duration(f"{state['seed']}:task-duration:{state['turn'] + 1}:{action['id']}", interval)
    return dict(action, duration_seconds=roll["seconds"], local_seconds=roll["seconds"],
                task_duration=roll)


def object_available(entity, spec=None):
    """Inspect local held or explicitly permitted unheld objects; NPC property uses Locks."""
    holders = (None, "pc") if (spec or {}).get("access") == "held_or_unheld" else ("pc",)
    return bool(entity and entity["kind"] == "object"
                and entity.get("custodian") in holders and object_actions.usable(entity))


def object_condition(entity):
    """Material examination identity; custody and location alone do not reset it."""
    return {"lifecycle": entity.get("lifecycle", "intact"), "function": entity.get("function")}


def examination_available(state, kind, entity):
    condition = object_condition(entity)
    return not any(r["kind"] == kind and r["target"] == entity["id"]
                   and r.get("object_condition") == condition for r in state.get("local_records", []))


def completion_available(state, rules, action, npc_available):
    spec = action.get("local_spec")
    if spec is None:
        return True
    if spec["target"] == "object":
        entity = establishment.local_entities(state).get(action["object_target"])
        return (object_available(entity, spec)
                and entity.get("custodian") == action["object_custodian_before"]
                and entity.get("lifecycle", "intact") == action["object_before"]
                and entity.get("function") == action.get("object_function_before")
                and examination_available(state, action["local_capability"], entity))
    if spec["target"] == "npc":
        from age_runtime.mythos.epistemic import conversation_available
        return conversation_available(state, rules, action["npc"], npc_available)
    return True


def local_capabilities(state, rules, npc_available):
    """Derive eligible targets, never manufacture an entity or a Test."""
    cfg = rules.get("local_proposals")
    if not cfg or state["ending"] or state["dxd"].get("activity", {}).get("status") != "awake":
        return []
    from age_runtime.mythos.epistemic import conversation_available
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds()
    result = []
    for kind, spec in cfg.items():
        minimum, maximum = duration_range(spec)
        if len(state["discoveries"]) < spec.get("requires_evidence", 0):
            continue
        if spec["target"] == "object":
            entities = establishment.local_entities(state)
            targets = [oid for oid, entity in sorted(entities.items()) if object_available(entity, spec)]
        elif spec["target"] == "npc":
            targets = [nid for nid, npc in sorted(state["npcs"].items())
                       if npc["encounters"] and conversation_available(state, rules, nid, npc_available)]
        else:
            targets = [state["location"]]
        for target in targets:
            action = "local:" + kind + ":" + target
            prior = pending_work(state, action) if spec.get("resumable") else None
            if prior and prior["evidence"] != state["discoveries"]:
                # Changed source material requires a fresh task, not credit.
                prior = None
            needed = prior["task_duration"]["seconds"] - prior["worked_seconds"] if prior else minimum
            unused = (examination_available(state, kind, entities[target])
                      if spec["target"] == "object" else action not in state["used"])
            if unused and needed <= remaining:
                result.append({"action": action, "approach": kind, "target": target,
                               "resolution": spec["resolution"],
                               **({"remaining_seconds": needed, "resuming": True} if prior else
                                  {"duration_range_seconds": [minimum, maximum],
                                   "time_interval_seconds": spec["variable_interval_seconds"],
                                   **({"deadline_risk": True} if maximum > remaining else {})}
                                  if "variable_interval_seconds" in spec else {"seconds": minimum})})
    return result


def compile_local(state, rules, request, npc_available):
    validate_request(request)
    cap = next((c for c in local_capabilities(state, rules, npc_available)
                if c["action"] == request["action"] and c["approach"] == request["approach"]), None)
    if cap is None:
        raise ValueError("local capability unavailable")
    kind, target = cap["approach"], cap["target"]
    spec = rules["local_proposals"][kind]
    loc, seconds = state["location"], duration_range(spec)[1]
    if not cap.get("resuming"):
        state.get("pending_work", {}).pop(cap["action"], None)
    action = {"id": cap["action"], "label": kind, "location": loc,
              "duration_seconds": seconds, "local_seconds": seconds, "interval_seconds": spec.get("variable_interval_seconds", 600),
              "activity": "active", "route": {"nodes": [loc], "seconds": 0, "minutes": 0, "terrain": []},
              "local_capability": kind, "local_spec": copy.deepcopy(spec)}
    if spec["target"] == "npc":
        action["npc"] = target
    elif spec["target"] == "object":
        action["object_target"] = target
        entity = establishment.local_entities(state)[target]
        action["object_custodian_before"] = entity.get("custodian")
        action["object_before"] = entity.get("lifecycle", "intact")
        action["object_function_before"] = entity.get("function")
        action["object_condition"] = object_condition(entity)
    if spec["resolution"] == "test":
        action["test"] = copy.deepcopy(spec["test"])
        action["concern_failure"] = copy.deepcopy(spec.get("concern_failure", {}))
    return action


def record_local(state, action, success, result):
    """Record only source-authorized completion; no manufactured Test margin."""
    kind, spec = action["local_capability"], action["local_spec"]
    record = {"kind": kind, "target": action.get("object_target", action.get("npc", state["location"])),
              "at": state["time"], "turn": state["turn"], "passed": success,
              "effect": result["margin"] if result is not None else None}
    if "object_target" in action:
        record["location"] = state["location"]
        record["object_condition"] = copy.deepcopy(action["object_condition"])
    if "task_duration" in action:
        record["task_duration"] = copy.deepcopy(action["task_duration"])
    if spec.get("count_evidence"):
        record["evidence_count"] = len(state["discoveries"])
    if success and spec.get("established"):
        record["established"] = spec["established"]
    state["local_records"].append(record)
    state.get("pending_work", {}).pop(action["id"], None)


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
