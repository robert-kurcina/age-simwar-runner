"""Certain mundane PC object outcomes, not a general free-form resolver."""
import re

def record(state, rules, request, local_entities, text):
    required = {"id", "object", "before", "outcome", "authorization", "basis", "remnants"}
    if (not rules.get("consequential_objects") or not isinstance(request, dict)
            or set(request) not in (required, required | {"function_before", "function_after"})):
        raise ValueError("invalid consequential object action")
    eid, oid = request["id"], request["object"]
    if not isinstance(eid, str) or not re.fullmatch(r"act:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid action identity")
    ledger = state["object_actions"]
    if len(ledger) >= 256 or any(e["id"] == eid for e in ledger):
        raise ValueError("duplicate action or record limit")
    obj = local_entities(state).get(oid) if isinstance(oid, str) else None
    if not obj or obj["kind"] != "object" or obj.get("custodian") != "pc":
        raise ValueError("action requires incidental object in PC custody")
    before = obj.get("lifecycle", "intact")
    outcome = request["outcome"]
    physical_change = (before, outcome) in (("intact", "damaged"), ("intact", "destroyed"), ("damaged", "destroyed"))
    function = {}
    if "function_after" in request:
        if not rules.get("object_function"):
            raise ValueError("object function unavailable")
        old = obj.get("function")
        new = request["function_after"]
        if (request["function_before"] != old or new not in ("impaired", "nonfunctional")
                or old == new or old == "nonfunctional" or before == "destroyed"
                or (outcome == "destroyed" and new != "nonfunctional")):
            raise ValueError("invalid object functional transition")
        function = {"function_before": old, "function_after": new}
    if request["before"] != before or not (physical_change or (function and before == outcome and before != "destroyed")):
        raise ValueError("invalid object lifecycle transition")
    authorization = text(request["authorization"], 240)
    basis = text(request["basis"], 240)
    remnants = text(request["remnants"], 160)
    # Destruction releases remnants at the action location; damaged objects
    # remain held. Neither transition changes ownership or grants evidence.
    ledger.append({**({"protagonist_id": state["protagonist"]["id"]} if state.get("protagonist") else {}), "id": eid, "object": oid, "before": before, "outcome": outcome,
                   "authorization": authorization, "basis": basis, "remnants": remnants, **function,
                   "location": state["location"], "at": state["time"], "turn": state["turn"],
                   "sequence": len(state["history"])})

def apply(entity, action):
    entity["lifecycle"] = action["outcome"]
    if "function_after" in action:
        entity["function"] = action["function_after"]
    elif "function" in entity and action["outcome"] == "destroyed":
        entity["function"] = "nonfunctional"
    props = entity.setdefault("properties", {})
    props["condition"] = action["remnants"]
    if action["outcome"] == "destroyed":
        entity["custodian"] = None
        entity["location"] = action["location"]
        props.pop("placement", None)

def usable(entity):
    return entity.get("lifecycle", "intact") != "destroyed"
