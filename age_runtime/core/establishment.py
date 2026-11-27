"""Referee-established descriptive context, never mechanical evidence or authority."""
from copy import deepcopy
import re
from age_runtime.core.communications import text_field

KINDS = ("setting_detail", "facility_detail", "administrative_detail")
SOURCE = "referee_session_establishment"


def validate(s):
    if "strategic_establishment" in s and (
            s["strategic_establishment"] is not True or not s.get("actors")):
        raise ValueError("strategic establishment requires an actor-scoped scenario")


def entities(state):
    """Fold immutable, ordered referee records; not a second state store."""
    result = {}
    for record in state["requests"]:
        if record.get("origin") != "strategic_establishment":
            continue
        command = record["establishment"]
        for item in command.get("details", []):
            result[item["id"]] = {**deepcopy(item), "established_minute": record["minute"],
                                  "updated_minute": record["minute"], "source": SOURCE,
                                  "history": []}
        for item in command.get("changes", []):
            entity = result[item["id"]]
            entity["description"] = item["after"]
            entity["updated_minute"] = record["minute"]
            entity["history"].append({**deepcopy(item), "minute": record["minute"]})
    return result


def view(s, state, actor):
    if not s.get("strategic_establishment"):
        return {}
    # Scope and referee rationale are not player knowledge. A viewer sees
    # only the descriptions and history disclosed to that actor.
    return {eid: {**{k: deepcopy(v) for k, v in entity.items()
                     if k not in ("audience", "basis", "history")},
                  "history": [{k: deepcopy(v) for k, v in change.items() if k != "basis"}
                              for change in entity["history"]]}
            for eid, entity in entities(state).items() if actor in entity["audience"]}


def append(s, state, command):
    if not s.get("strategic_establishment") or state["minute"] >= s["end_minute"]:
        raise ValueError("strategic establishment unavailable")
    if not isinstance(command, dict) or set(command) not in ({"details"}, {"changes"}):
        raise ValueError("invalid establishment batch")
    kind = next(iter(command))
    items = command[kind]
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("establish or change 1 to 12 details per batch")
    prior = [r for r in state["requests"] if r.get("origin") == "strategic_establishment"]
    if sum(len(next(iter(r["establishment"].values()))) for r in prior) + len(items) > 256:
        raise ValueError("strategic establishment record limit")
    current = entities(state)
    pending = []
    seen = set()
    # Labels may repeat for independent entities; stable IDs identify facts.
    for item in items:
        required = ({"id", "kind", "label", "description", "audience", "basis"}
                    if kind == "details" else {"id", "before", "after", "basis"})
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("invalid descriptive establishment fields")
        eid = item["id"]
        if not isinstance(eid, str) or not re.fullmatch(r"inc:[a-z][a-z0-9_]{0,63}", eid):
            raise ValueError("invalid incidental identity")
        if eid in seen:
            raise ValueError("duplicate detail in batch")
        seen.add(eid)
        basis = text_field(item["basis"], 240)
        if kind == "details":
            if eid in current or item["kind"] not in KINDS:
                raise ValueError("existing entity or unsupported descriptive kind")
            audience = item["audience"]
            if (not isinstance(audience, list) or not audience
                    or any(not isinstance(a, str) or a not in s["actors"] for a in audience)
                    or len(set(audience)) != len(audience)):
                raise ValueError("invalid descriptive audience")
            pending.append({"id": eid, "kind": item["kind"],
                            "label": text_field(item["label"], 80),
                            "description": text_field(item["description"], 400),
                            "audience": sorted(audience), "basis": basis})
        else:
            if eid not in current or item["before"] != current[eid]["description"]:
                raise ValueError("descriptive prior-value mismatch")
            after = text_field(item["after"], 400)
            if after == item["before"]:
                raise ValueError("description unchanged")
            pending.append({"id": eid, "before": item["before"], "after": after, "basis": basis})
    result = deepcopy(state)
    result["requests"].append({"actor": None, "action": None, "status": "established",
        "origin": "strategic_establishment", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "establishment": {kind: pending}})
    return result
