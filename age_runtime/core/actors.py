"""Scenario-owned actor metadata and descriptive objective evaluation."""
import hashlib
import json

def validate_actors(s):
    actors = s.get("actors", {})
    if not isinstance(actors, dict):
        raise ValueError("actors must be an object")
    for aid, actor in actors.items():
        if not isinstance(aid, str) or not aid or not isinstance(actor, dict):
            raise ValueError("invalid actor")
        if not isinstance(actor.get("label"), str):
            raise ValueError("actor label required")
        if "faction_context" in actor:
            context = actor["faction_context"]
            if not isinstance(context, dict) or set(context) != {"version", "spec_digest", "profile_digest", "profile"} or context["version"] != 1:
                raise ValueError("invalid faction context")
            profile = context["profile"]
            if not isinstance(profile, dict) or profile.get("kind") != "organization" or profile.get("id") != aid or profile.get("label") != actor["label"]:
                raise ValueError("invalid faction identity")
            if hashlib.sha256(json.dumps(profile, sort_keys=True, allow_nan=False).encode()).hexdigest() != context["profile_digest"]:
                raise ValueError("faction profile digest mismatch")
        objectives = actor.get("objectives", {})
        if not isinstance(objectives, dict):
            raise ValueError("objectives must be an object")
        strategy = actor.get("strategy")
        if "strategy" in actor:
            if not isinstance(strategy, dict) or set(strategy) != {"motivation", "priorities"}:
                raise ValueError("invalid faction strategy")
            if not isinstance(strategy["motivation"], str) or not strategy["motivation"].strip():
                raise ValueError("faction motivation required")
            priorities = strategy["priorities"]
            if (not isinstance(priorities, list) or not priorities or
                    any(not isinstance(p, str) or p not in objectives for p in priorities) or
                    len(set(priorities)) != len(priorities) or set(priorities) != set(objectives)):
                raise ValueError("faction priorities must order all own objectives")
            if any(obj.get("key") not in actor.get("visible_keys", []) for obj in objectives.values() if isinstance(obj, dict)):
                raise ValueError("strategic objectives require observable properties")
        for oid, obj in objectives.items():
            if not oid or not isinstance(obj, dict):
                raise ValueError("invalid objective")
            if obj.get("key") not in s["initial"]:
                raise ValueError("unknown objective variable")
            if type(obj.get("threshold")) is not int:
                raise ValueError("objective threshold must be integer")
            if obj.get("comparison") not in ("at_least", "at_most", "equal"):
                raise ValueError("invalid comparison")
            if not isinstance(obj.get("description"), str):
                raise ValueError("objective description required")

def evaluate(s, values):
    results = {}
    for aid, actor in s.get("actors", {}).items():
        objectives = {}
        for oid, obj in actor.get("objectives", {}).items():
            actual, threshold = values[obj["key"]], obj["threshold"]
            passed = {"at_least": actual >= threshold,
                      "at_most": actual <= threshold,
                      "equal": actual == threshold}[obj["comparison"]]
            objectives[oid] = {"description": obj["description"],
                               "actual": actual, "threshold": threshold,
                               "met": passed}
        results[aid] = {"label": actor["label"], "objectives": objectives}
    return results
