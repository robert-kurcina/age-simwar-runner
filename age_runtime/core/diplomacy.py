"""Qualitative diplomatic history derived from actor-visible records only."""
from copy import deepcopy


def history(observation, state=None):
    actor = observation["actor"]
    result = {}

    def relationship(other):
        return result.setdefault(other, {"communications": [], "proposals": [],
                                         "agreements": [], "private_intentions": {}})

    for msg in observation.get("communications", []):
        others = msg["recipients"] if msg["speaker"] == actor else [msg["speaker"]]
        for other in others:
            rel = relationship(other)
            # A dispatch is not evidence of acknowledgement, and a claim
            # is not a commitment. Keep only the corresponding record ID.
            rel["communications"].append({
                "id": msg["id"], "direction": "outgoing" if msg["speaker"] == actor else "incoming",
                "sent_minute": msg["minute"],
                **({"delivery_minute": msg["delivery_minute"]} if "delivery_minute" in msg else {}),
                **({"scheduled_delivery": msg["scheduled_delivery"][other]}
                   if "scheduled_delivery" in msg and other in msg["scheduled_delivery"] else {})})
            intention = msg.get("private_intention")
            if state is None and msg["speaker"] == actor and intention and intention["counterpart"] == other:
                topic = intention["topic"]
                revisions = rel["private_intentions"].setdefault(topic, {"history": []})
                revisions["history"].append({"claim_id": msg["id"], "minute": msg["minute"],
                                             **deepcopy(intention)})
                revisions["latest"] = deepcopy(revisions["history"][-1])
    for proposal in observation.get("negotiation", {}).get("proposals", []):
        other = proposal["recipient"] if proposal["proposer"] == actor else proposal["proposer"]
        relationship(other)["proposals"].append({
            "id": proposal["id"], "status": proposal["status"],
            "due_minute": proposal["due_minute"],
            **({"parent": proposal["parent"]} if "parent" in proposal else {})})
    for aid, agreement in observation.get("strategic_support", {}).get("agreements", {}).items():
        # Signatory identities are disclosed only within an authorized
        # agreement projection. Do not infer consent from participation.
        for other in agreement.get("participants", []):
            if other != actor:
                relationship(other)["agreements"].append({
                    "id": aid, "status": agreement["status"], "due_minute": agreement["due_minute"],
                    "counterpart_consented": other in agreement["consenting"]})
    if state is not None:
        for entry in private_history(state, actor):
            rel = relationship(entry["counterpart"])
            group = "private_intentions" if entry["kind"] == "intention" else "relationship_assessments"
            revisions = rel.setdefault(group, {}).setdefault(entry["topic"], {"history": []})
            public_entry = {k: deepcopy(v) for k, v in entry.items() if k not in ("kind", "id")}
            revisions["history"].append(public_entry)
            revisions["latest"] = deepcopy(public_entry)
    return result


def private_history(state, actor):
    """Preserve request sequence across speech-linked and independent revisions."""
    for record in state["requests"]:
        if record["actor"] != actor:
            continue
        if record.get("origin") == "communication":
            msg = record["communication"]
            if "private_intention" in msg:
                yield {"kind": "intention", "id": msg["id"], "claim_id": msg["id"],
                       "minute": record["minute"], **deepcopy(msg["private_intention"])}
        elif record.get("origin") == "diplomatic_record":
            entry = deepcopy(record["diplomatic_record"])
            entry["record_id"] = entry["id"]
            entry["minute"] = record["minute"]
            yield entry


def latest(state, actor, counterpart, topic, kind):
    entries = [e for e in private_history(state, actor) if e["kind"] == kind
               and e["counterpart"] == counterpart and e["topic"] == topic]
    return entries[-1] if entries else None


def validate_revision(previous, command):
    if command["revises"] != (previous["id"] if previous else None):
        raise ValueError("diplomatic revision must reference latest own record")
    if command["kind"] == "intention":
        if command["status"] not in ("active", "withdrawn"):
            raise ValueError("invalid intention status")
        if command["status"] == "withdrawn" and (not previous or previous["status"] != "active"):
            raise ValueError("withdrawal requires active intention")
        if previous and all(previous[k] == command[k] for k in ("status", "text")):
            raise ValueError("duplicate private intention")


def append(s, state, actor, command):
    from age_runtime.core.communications import text_field
    from age_runtime.core.observations import observe
    if not s.get("diplomatic_history") or actor not in s["actors"] or state["minute"] >= s["end_minute"]:
        raise ValueError("private diplomatic record unavailable")
    if not isinstance(command, dict):
        raise ValueError("invalid diplomatic record")
    kind = command.get("kind")
    required = {"kind", "id", "counterpart", "topic", "text", "revises"}
    if kind == "intention":
        required.add("status")
    elif kind == "assessment":
        required.add("basis")
    else:
        raise ValueError("invalid diplomatic record kind")
    if set(command) != required:
        raise ValueError("invalid diplomatic record fields")
    rid = text_field(command["id"], 80)
    counterpart = command["counterpart"]
    if not isinstance(counterpart, str) or counterpart == actor or counterpart not in s["actors"]:
        raise ValueError("invalid diplomatic counterpart")
    records = [r for r in state["requests"] if r.get("origin") == "diplomatic_record"]
    if (len(records) >= 256 or any(r["diplomatic_record"]["id"] == rid for r in records)
            or any(r.get("origin") == "communication" and r["communication"]["id"] == rid
                   for r in state["requests"])):
        raise ValueError("duplicate diplomatic ID or record limit")
    payload = {**deepcopy(command), "id": rid, "topic": text_field(command["topic"], 80),
               "text": text_field(command["text"], 400)}
    previous = latest(state, actor, counterpart, payload["topic"], kind)
    validate_revision(previous, payload)
    if kind == "assessment":
        rel = observe(s, state, actor)["diplomatic_history"].get(counterpart, {})
        allowed = {}
        for category in ("communications", "proposals", "agreements"):
            for entry in rel.get(category, []):
                # Outgoing dispatch does not demonstrate counterpart conduct.
                if category == "communications" and entry["direction"] != "incoming":
                    continue
                allowed[(category, entry["id"])] = entry
        basis = command["basis"]
        if not isinstance(basis, list) or not basis or len(basis) > 32:
            raise ValueError("assessment requires accessible conduct evidence")
        keys = []
        for item in basis:
            if (not isinstance(item, dict) or set(item) != {"kind", "id"}
                    or not all(isinstance(item[k], str) for k in ("kind", "id"))):
                raise ValueError("invalid assessment evidence reference")
            key = (item["kind"], item["id"])
            if key not in allowed or key in keys:
                raise ValueError("assessment requires accessible conduct evidence")
            keys.append(key)
        payload["basis"] = [{"kind": k, "id": i} for k, i in sorted(keys)]
        payload["evidence"] = [{"kind": k, **deepcopy(allowed[(k, i)])} for k, i in sorted(keys)]
        if previous and all(previous[k] == payload[k] for k in ("text", "basis", "evidence")):
            raise ValueError("duplicate relationship assessment")
    result = deepcopy(state)
    result["requests"].append({"actor": actor, "action": None, "status": "deliberated",
        "origin": "diplomatic_record", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "diplomatic_record": payload})
    return result
