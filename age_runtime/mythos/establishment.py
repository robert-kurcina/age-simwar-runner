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
        if not isinstance(item, dict) or set(item) != {"id", "kind", "label", "description", "basis"}:
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
        pending.append({"id": eid, "kind": item["kind"], "label": label,
                        "description": description, "basis": basis,
                        "location": state["location"], "turn": state["turn"],
                        "at": state["time"], "source": "gm_narration"})
    ledger.extend(pending)

def projection(state):
    """Visible local details are remembered descriptions, not new observations."""
    return [{k: copy.deepcopy(v) for k, v in e.items() if k != "basis"}
            for e in state.get("established_details", []) if e["location"] == state["location"]]

def referee_projection(state):
    return copy.deepcopy([e for e in state.get("established_details", []) if e["location"] == state["location"]])
