"""Scenario-local causal clocks and DXD Encounter Tension.

No generic expression evaluator or model-authored mutations. Effects are
limited to declared flags and observations; hidden clocks stay private.
"""
from datetime import datetime
from random import Random

def eligible(state, spec):
    return (all(f in state["flags"] for f in spec.get("requires_flags", []))
            and not any(f in state["flags"] for f in spec.get("excludes_flags", []))
            and (not spec.get("locations") or state["location"] in spec["locations"]))

def validate(rules):
    locations = set(rules["locations"])
    actions = {a["id"] for a in rules["actions"]}
    for key, cfg in rules.get("event_clocks", {}).items():
        if type(cfg["segments"]) is not int or cfg["segments"] <= 0 or not cfg.get("source") or not cfg.get("name"):
            raise ValueError("invalid Event Clock")
        if not cfg.get("triggers") and not cfg.get("interval_seconds"):
            raise ValueError("Event Clock needs a trigger")
        if "interval_seconds" in cfg and (type(cfg["interval_seconds"]) is not int or cfg["interval_seconds"] <= 0):
            raise ValueError("invalid Event Clock interval")
        for trigger in cfg.get("triggers", []):
            if trigger["action"] not in actions or trigger.get("outcome", "any") not in ("any", "success", "failure") or type(trigger["marks"]) is not int or trigger["marks"] <= 0:
                raise ValueError("invalid Event Clock trigger")
        if not cfg.get("grant"):
            raise ValueError("Event Clock needs consequence")
    ids = set()
    for entry in rules.get("encounter_table", []):
        if entry["id"] in ids or type(entry["weight"]) is not int or entry["weight"] <= 0 or not entry.get("locations") or not set(entry["locations"]) <= locations or not entry.get("observation"):
            raise ValueError("invalid encounter entry")
        ids.add(entry["id"])
    if rules.get("encounter_table") and not rules.get("encounter_exposure_locations"):
        raise ValueError("encounter table needs exposure scope")
    if not set(rules.get("encounter_exposure_locations", [])) <= locations:
        raise ValueError("invalid encounter exposure location")

def initial(rules):
    validate(rules)
    return {"clocks": {key: {"marks": 0, "resolved": False, "seconds": 0}
                       for key in rules.get("event_clocks", {})},
            "encounter": {"dice": 0, "seconds": 0, "checks": [], "seen": []},
            "ledger": []}

def mark(state, key, cfg, amount):
    data = state["narrative_events"]
    clock = data["clocks"][key]
    if clock["resolved"] or not amount:
        return
    clock["marks"] = min(cfg["segments"], clock["marks"] + amount)
    data["ledger"].append({"clock": key, "at": state["time"], "marks": clock["marks"]})
    if clock["marks"] == cfg["segments"]:
        clock["resolved"] = True
        for f in cfg["grant"]:
            if f not in state["flags"]:
                state["flags"].append(f)
        if cfg.get("observation") and eligible(state, cfg.get("visibility", {})):
            state["observations"].append(cfg["observation"])

def advance_time(state, rules, seconds):
    """Only time elapsed while eligible counts; no retroactive marks."""
    if "narrative_events" not in state:
        return
    # Snapshot eligibility before applying any same-boundary consequence.
    due = [(key, cfg) for key, cfg in rules.get("event_clocks", {}).items()
           if not state["narrative_events"]["clocks"][key]["resolved"]
           and cfg.get("interval_seconds") and eligible(state, cfg)]
    for key, cfg in due:
        clock = state["narrative_events"]["clocks"][key]
        marks, clock["seconds"] = divmod(clock["seconds"] + seconds, cfg["interval_seconds"])
        mark(state, key, cfg, marks)

def next_boundary(state, rules):
    """Seconds to next eligible timed mark, or None."""
    values = []
    for key, cfg in rules.get("event_clocks", {}).items():
        clock = state["narrative_events"]["clocks"][key]
        if not clock["resolved"] and cfg.get("interval_seconds") and eligible(state, cfg):
            values.append(cfg["interval_seconds"] - clock["seconds"])
    return min(values) if values else None

def encounter_check(state, rules, kind):
    e = state["narrative_events"]["encounter"]
    rng = Random(f"{state['seed']}:encounter:{len(e['checks'])}")
    rolls = [rng.randint(1, 6) for _ in range(e["dice"])]
    severity = max(0, rolls.count(1) - rolls.count(6))
    candidates = [x for x in rules["encounter_table"] if x["id"] not in e["seen"] and eligible(state, x)]
    selected = None
    if severity and candidates:
        selected = rng.choices(candidates, weights=[x["weight"] for x in candidates], k=1)[0]
        e["seen"].append(selected["id"])
        for flag in selected.get("grant", []):
            if flag not in state["flags"]:
                state["flags"].append(flag)
        state["observations"].append(selected["observation"])
    e["checks"].append({"at": state["time"], "kind": kind, "rolls": rolls,
                        "severity": severity, "event": selected["id"] if selected else None})
    # Native Overflow leaves half; Trigger consumes the rolled pool.
    e["dice"] = e["dice"] // 2 if kind == "overflow" else 0

def complete_action(state, rules, action, success, local_seconds):
    if "narrative_events" not in state:
        return
    # Like timed clocks, evaluate eligibility against one pre-mark snapshot.
    due = [(key, cfg) for key, cfg in rules.get("event_clocks", {}).items()
           if eligible(state, cfg)]
    for key, cfg in due:
        amount = sum(t["marks"] for t in cfg.get("triggers", [])
                     if t["action"] == action["id"] and t.get("outcome", "any") in
                     ("any", "success" if success else "failure"))
        mark(state, key, cfg, amount)
    if not rules.get("encounter_table") or state["location"] not in rules.get("encounter_exposure_locations", []):
        return
    e = state["narrative_events"]["encounter"]
    if action.get("activity") not in ("rest", "sleep") and local_seconds:
        # Local narrative interval 10 min; normal exposed activity adds
        # one die per three intervals. No travel or opposition double count.
        count, e["seconds"] = divmod(e["seconds"] + local_seconds, 1800)
        for _ in range(count):
            e["dice"] += 1
            if e["dice"] >= 6:
                encounter_check(state, rules, "overflow")
    if action.get("encounter_trigger"):
        encounter_check(state, rules, "trigger")

def projection(state, rules):
    data = state["narrative_events"]
    return {"clocks": [{"id": key, "name": cfg["name"], "segments": cfg["segments"],
                        "marks": data["clocks"][key]["marks"], "resolved": data["clocks"][key]["resolved"]}
                       for key, cfg in rules.get("event_clocks", {}).items()
                       if cfg.get("visible") and eligible(state, cfg.get("visibility", {}))],
            "encounter_dice": data["encounter"]["dice"]}
