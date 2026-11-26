"""Read-only actor projections. Full checkpoints are referee-only."""
from copy import deepcopy
from age_runtime.core.actions import available_requests
from age_runtime.core.actors import evaluate

def validate_views(s):
    for actor in s.get("actors", {}).values():
        keys = actor.get("visible_keys", [])
        if not isinstance(keys, list) or any(not isinstance(k, str) or k not in s["initial"] for k in keys):
            raise ValueError("invalid visible_keys")
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate visible key")
        delays = actor.get("report_delay_minutes", {})
        if not isinstance(delays, dict) or any(k not in keys or type(v) is not int or v < 0 for k, v in delays.items()):
            raise ValueError("invalid report delay")

def observe(s, state, actor_id):
    actor = s.get("actors", {}).get(actor_id)
    if actor is None:
        raise ValueError("unknown actor")
    keys = set(actor.get("visible_keys", []))
    reports = {}
    values = {}
    for key in sorted(keys):
        delay = actor.get("report_delay_minutes", {}).get(key, 0)
        cutoff = state["minute"] - delay
        if cutoff < 0:
            reports[key] = {"status": "unknown"}
            continue
        value = s["initial"][key]
        for entry in state["ledger"]:
            if entry["key"] == key and entry["minute"] <= cutoff:
                value = entry["value"]
        values[key] = value
        reports[key] = {"status": "current" if delay == 0 else "stale",
                        "as_of_minute": cutoff, "age_minutes": delay,
                        "value": value}
    # Evaluate only objectives supported by the actor's observed values.
    observed_actor = {**actor, "objectives": {
        oid: obj for oid, obj in actor.get("objectives", {}).items()
        if obj["key"] in values}}
    observed_objectives = evaluate({"actors": {actor_id: observed_actor}}, values)[actor_id]["objectives"]
    return {
        **({"faction_context": deepcopy(actor["faction_context"]["profile"])} if "faction_context" in actor else {}),
        **({"project_results": [deepcopy(r) for r in state["project_results"] if r["participant"] == actor_id]} if "project_results" in state else {}),
        "actor": actor_id,
        "minute": state["minute"],
        "turn": state["turn"],
        "values": values,
        "reports": reports,
        "own_requests": [{k: deepcopy(v) for k, v in r.items() if k != "sequence"}
                         for r in state["requests"] if r["actor"] == actor_id],
        "available_requests": available_requests(s, actor_id) if state["minute"] < s["end_minute"] else {},
        "objectives": observed_objectives
    }
