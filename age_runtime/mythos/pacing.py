"""Bounded narrative pacing, separate from time and adjudication."""
import re

INTERVALS = (10, 60, 600, 3600)
BUDGETS = (6, 12, 24)

def duration(record):
    if "seconds" in record and "minutes" in record:
        raise ValueError("ambiguous duration")
    value = record.get("seconds") if "seconds" in record else record.get("minutes")
    if type(value) is not int or value <= 0:
        raise ValueError("duration must be a positive integer")
    return value if "seconds" in record else value * 60

def initial(config):
    if config["target_decisions"] not in BUDGETS:
        raise ValueError("unsupported decision budget")
    return {"target": config["target_decisions"], "decisions": [],
            "current": None, "interval_seconds": 600, "narrative_beats": 0}

def record(state, action, proposal=None):
    """An authored default or a GM-classified commitment, not an extra action.

    Stable keys are idempotent even if cited again. A genuinely new
    commitment needs a new key. No budget-driven mechanical effects.
    """
    pacing = state.get("pacing")
    if pacing is None:
        if proposal is not None:
            raise ValueError("decision classification unavailable")
        return
    interval = action.get("interval_seconds", 600)
    if interval not in INTERVALS:
        raise ValueError("unsupported narrative interval")
    pacing["interval_seconds"] = interval
    if action.get("narrative_beat"):
        pacing["narrative_beats"] += 1
    authored = action.get("critical_decision")
    if proposal is not None:
        if not isinstance(proposal, dict) or set(proposal) != {"id", "label"}:
            raise ValueError("invalid decision proposal")
        key, label = proposal["id"], proposal["label"]
        if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key)
                or not isinstance(label, str) or not label.strip() or len(label) > 160
                or any(ord(c) < 32 for c in label)):
            raise ValueError("invalid decision identity or label")
        if authored and key != authored:
            raise ValueError("use authored decision identity")
    elif authored:
        key, label = authored, action["label"]
    else:
        return
    previous = next((d for d in pacing["decisions"] if d["id"] == key), None)
    if previous is not None:
        if proposal is not None and label != previous["label"]:
            raise ValueError("decision identity already established")
        pacing["current"] = key
        return
    pacing["decisions"].append({"id": key, "label": label, "turn": state["turn"],
                                "action": action["id"], "at": state["time"]})
    pacing["current"] = key

def projection(state):
    p = state["pacing"]
    used = len(p["decisions"])
    return {"target_decisions": p["target"], "committed_decisions": used,
            "remaining_decisions": max(0, p["target"] - used),
            "current_decision": next((d for d in p["decisions"] if d["id"] == p["current"]), None),
            "interval_seconds": p["interval_seconds"], "narrative_beats": p["narrative_beats"],
            "game_turns": state["turn"]}
