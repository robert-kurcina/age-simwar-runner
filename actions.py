"""Validate structured proposals without granting mutation authority.

The prototype accepts only scenario-declared administrative requests.
Registration is a pure operation; no action effects are executed here.
"""
def validate_catalog(s):
    catalog = s.get("action_catalog", {})
    if not isinstance(catalog, dict):
        raise ValueError("action catalog must be an object")
    for name, spec in catalog.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ValueError("invalid action definition")
        if set(spec) != {"description", "actors"}:
            raise ValueError("invalid action definition fields")
        if not isinstance(spec["description"], str) or not spec["description"]:
            raise ValueError("missing action description")
        ids = spec["actors"]
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in s.get("actors", {}) for i in ids):
            raise ValueError("unknown action actor")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate action actor")

def available_requests(s, actor_id):
    if actor_id not in s.get("actors", {}):
        raise ValueError("unknown actor")
    return {name: {"description": spec["description"]}
            for name, spec in s.get("action_catalog", {}).items()
            if actor_id in spec["actors"]}

def validate_request(s, actor_id, proposal):
    """Trusted caller supplies actor identity; proposal cannot override it."""
    if not isinstance(proposal, dict) or set(proposal) != {"action"}:
        raise ValueError("proposal must contain only action")
    name = proposal["action"]
    if not isinstance(name, str) or name not in available_requests(s, actor_id):
        raise ValueError("action unavailable")
    return {"actor": actor_id, "action": name, "status": "validated_request"}

def register_request(s, state, actor_id, proposal):
    """Return a detached record; does not mutate state or imply execution."""
    if state["minute"] >= s["end_minute"]:
        raise ValueError("session ended")
    record = validate_request(s, actor_id, proposal)
    return {**record, "turn": state["turn"], "minute": state["minute"]}
