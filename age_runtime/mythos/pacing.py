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

def initial(config, scene, location):
    if config["target_spotlights"] not in BUDGETS:
        raise ValueError("unsupported Spotlight budget")
    definitions = scene["frames"]
    if any(not frame["locations"] or not set(frame["locations"]) <= set(scene["locations"])
           for frame in definitions.values()):
        raise ValueError("invalid Scene locations")
    start = scene["initial_frame"]
    if location not in definitions[start]["locations"]:
        raise ValueError("invalid initial Scene")
    return {"target": config["target_spotlights"], "spotlights": [], "current": None,
            "scene": start, "scene_changes": [], "interval_seconds": 600,
            "narrative_beats": 0}

def eligible_scenes(state, rules):
    return [key for key, frame in rules["scene"]["frames"].items()
            if state["location"] in frame["locations"]
            and all(f in state["flags"] for f in frame.get("requires_flags", []))
            and not any(f in state["flags"] for f in frame.get("excludes_flags", []))]

def change_scene(state, rules, key):
    if key not in eligible_scenes(state, rules):
        raise ValueError("Scene unavailable at current location")
    p = state["pacing"]
    if key != p["scene"]:
        p["scene_changes"].append({"from": p["scene"], "to": key,
                                   "turn": state["turn"], "at": state["time"]})
        p["scene"] = key

def reconcile_scene(state, rules):
    # Movement within a frame does not force a transition; leaving its
    # permitted locations does. A GM may choose another eligible frame.
    if "pacing" not in state:
        return
    eligible = eligible_scenes(state, rules)
    if not eligible:
        raise ValueError("no eligible Scene at destination")
    if state["pacing"]["scene"] not in eligible:
        change_scene(state, rules, eligible[0])

def current(state):
    p = state["pacing"]
    return next((x for x in p["spotlights"] if x["id"] == p["current"]), None)

def control(state, rules, request):
    """Pacing-only transition: no clock, test or mechanical turn effects."""
    if "pacing" not in state or state["ending"]:
        raise ValueError("narrative control unavailable")
    p = state["pacing"]
    kind = request.get("kind")
    if kind == "scene" and set(request) == {"kind", "id"}:
        change_scene(state, rules, request["id"])
    elif kind == "open" and set(request) == {"kind", "id", "label"}:
        key, label = request["id"], request["label"]
        if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key)
                or not isinstance(label, str) or not label.strip() or len(label) > 160
                or any(ord(c) < 32 for c in label)):
            raise ValueError("invalid Spotlight identity or purpose")
        if p["current"] is not None or any(x["id"] == key for x in p["spotlights"]):
            raise ValueError("Spotlight already active or identity used")
        p["spotlights"].append({"id": key, "label": label, "character": "pc",
                                "opened_at": state["time"], "opened_turn": state["turn"],
                                "opened_scene": p["scene"], "activities": [],
                                "closed_at": None, "status": "active"})
        p["current"] = key
    elif kind in ("complete", "abandon") and set(request) == {"kind", "id"}:
        item = current(state)
        if item is None or item["id"] != request["id"]:
            raise ValueError("Spotlight not active")
        # Meaningful dialogue/revelation may occur without a Test or time
        # advance. GM classification remains advisory, not semantic proof.
        item.update(status="completed" if kind == "complete" else "abandoned",
                    closed_at=state["time"], closed_turn=state["turn"],
                    closed_scene=p["scene"])
        p["current"] = None
    else:
        raise ValueError("invalid narrative control")

def record(state, action):
    if "pacing" not in state:
        return
    p = state["pacing"]
    interval = action.get("interval_seconds", 600)
    if interval not in INTERVALS:
        raise ValueError("unsupported narrative interval")
    p["interval_seconds"] = interval
    if action.get("narrative_beat"):
        p["narrative_beats"] += 1
    item = current(state)
    if item is not None:
        item["activities"].append({"turn": state["turn"], "action": action["id"],
                                   "scene": p["scene"], "success": state["last_result"]["success"]})

def projection(state, rules):
    p = state["pacing"]
    used = sum(x["status"] == "completed" for x in p["spotlights"])
    active = current(state)
    frame = rules["scene"]["frames"][p["scene"]]
    return {"target_spotlights": p["target"], "completed_spotlights": used,
            "remaining_spotlights": max(0, p["target"] - used),
            "current_spotlight": active,
            "scene": {"id": p["scene"], "background": frame["background"],
                      "eligible_frames": eligible_scenes(state, rules)},
            "interval_seconds": p["interval_seconds"], "narrative_beats": p["narrative_beats"],
            "game_turns": state["turn"]}
