"""Delegated, mundane narrative establishment, not mechanical adjudication."""
import copy
import re

def text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid establishment text")
    return value.strip()

def normalize(value):
    return " ".join(value.casefold().split())

def record(state, rules, request):
    if not rules.get("narrative_establishment") or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("establishment unavailable")
    if isinstance(request, dict) and set(request) == {"changes"}:
        return modify(state, rules, request["changes"])
    if not isinstance(request, dict) or set(request) != {"details"}:
        raise ValueError("invalid establishment request")
    details = request["details"]
    if not isinstance(details, list) or not 1 <= len(details) <= 12:
        raise ValueError("establish 1 to 12 details per batch")
    ledger = state["established_details"]
    if len(ledger) + len(details) > 256:
        raise ValueError("establishment record limit")
    # Scope IDs globally; names locally. No alteration, relocation or
    # ownership transfer by re-establishing an existing entity.
    ids = {entry["id"] for entry in ledger}
    labels = {(entry["location"], normalize(entry["label"])) for entry in ledger}
    pending = []
    for item in details:
        required = {"id", "kind", "label", "description", "basis"}
        if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"properties"}:
            raise ValueError("invalid establishment detail fields")
        eid = item["id"]
        if not isinstance(eid, str) or not re.fullmatch(r"inc:[a-z][a-z0-9_]{0,63}", eid):
            raise ValueError("invalid incidental identity")
        if item["kind"] not in ("fixture", "object", "setting_detail"):
            raise ValueError("invalid incidental kind")
        label = text(item["label"], 80)
        description = text(item["description"], 400)
        basis = text(item["basis"], 240)
        key = (state["location"], normalize(label))
        if eid in ids or key in labels:
            raise ValueError("detail identity already established; reuse it")
        # No inventory insertion, flags, mechanical attributes, NPC state,
        # hidden properties or new access rights are accepted here.
        ids.add(eid)
        labels.add(key)
        properties = item.get("properties", {})
        if "properties" in item and not rules.get("narrative_properties"):
            raise ValueError("narrative properties unavailable")
        if not isinstance(properties, dict) or set(properties) - FIELDS:
            raise ValueError("unsupported descriptive property")
        properties = {key: text(value, 160) for key, value in properties.items()}
        pending.append({"id": eid, "kind": item["kind"], "label": label,
                        "description": description, "basis": basis,
                        "location": state["location"], "turn": state["turn"],
                        "at": state["time"], "source": "gm_narration",
                        **({"properties": properties} if rules.get("narrative_properties") else {})})
    ledger.extend(pending)

# Qualitative presentation only: no numerical stats, possession, access,
# location, evidence, hazard, supernatural effect or mechanical condition.
FIELDS = {"appearance", "condition", "placement"}

def local_entities(state):
    """Fold descriptive changes over immutable establishment records."""
    entities = {e["id"]: copy.deepcopy(e) for e in state.get("established_details", [])
                if e["location"] == state["location"]}
    for change in state.get("detail_changes", []):
        entity = entities.get(change["id"])
        if entity is not None:
            entity.setdefault("properties", {})[change["property"]] = change["after"]
    return entities

def modify(state, rules, changes):
    if not rules.get("narrative_properties"):
        raise ValueError("narrative properties unavailable")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 12:
        raise ValueError("modify 1 to 12 properties per batch")
    ledger = state["detail_changes"]
    if len(ledger) + len(changes) > 512:
        raise ValueError("property change record limit")
    entities = local_entities(state)
    pending = []
    seen = set()
    for item in changes:
        if not isinstance(item, dict) or set(item) != {"id", "property", "before", "after", "basis"}:
            raise ValueError("invalid property change fields")
        eid, field = item["id"], item["property"]
        if not isinstance(eid, str) or eid not in entities:
            raise ValueError("entity not present")
        if not isinstance(field, str) or field not in FIELDS:
            raise ValueError("unsupported descriptive property")
        if (eid, field) in seen:
            raise ValueError("duplicate property change in batch")
        seen.add((eid, field))
        old = entities[eid].get("properties", {}).get(field)
        if item["before"] != old:
            raise ValueError("property precondition mismatch")
        new = text(item["after"], 160)
        if old == new:
            raise ValueError("property unchanged")
        basis = text(item["basis"], 240)
        pending.append({"change_id": len(ledger) + len(pending) + 1,
                        "id": eid, "property": field, "before": old, "after": new,
                        "basis": basis, "turn": state["turn"], "at": state["time"],
                        "location": state["location"], "source": "gm_narration"})
    ledger.extend(pending)

def projection(state):
    """Visible local entities with current properties and original description."""
    return [{k: v for k, v in e.items() if k != "basis"}
            for e in local_entities(state).values()]

def referee_projection(state):
    entities = local_entities(state)
    for e in entities.values():
        changes = [copy.deepcopy(c) for c in state.get("detail_changes", []) if c["id"] == e["id"]]
        if changes:
            e["property_history"] = changes
    return list(entities.values())
