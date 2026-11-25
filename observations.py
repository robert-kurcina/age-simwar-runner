"""Read-only actor projections. Full checkpoints are referee-only."""
from copy import deepcopy
from actions import available_requests

def validate_views(s):
    for actor in s.get("actors", {}).values():
        keys = actor.get("visible_keys", [])
        if not isinstance(keys, list) or any(not isinstance(k, str) or k not in s["initial"] for k in keys):
            raise ValueError("invalid visible_keys")
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate visible key")

def observe(s, state, actor_id):
    actor = s.get("actors", {}).get(actor_id)
    if actor is None:
        raise ValueError("unknown actor")
    keys = set(actor.get("visible_keys", []))
    return {
        "actor": actor_id,
        "minute": state["minute"],
        "turn": state["turn"],
        "values": {k: v for k, v in state["values"].items() if k in keys},
        "own_requests": [{k: deepcopy(v) for k, v in r.items() if k != "sequence"}
                         for r in state["requests"] if r["actor"] == actor_id],
        "available_requests": available_requests(s, actor_id) if state["minute"] < s["end_minute"] else {},
        "objectives": {
            oid: deepcopy(result)
            for oid, result in state["actors"][actor_id]["objectives"].items()
            if actor["objectives"][oid]["key"] in keys
        }
    }
