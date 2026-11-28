"""Delegated, mundane narrative establishment, not mechanical adjudication."""
import copy
import re
from age_runtime.mythos import agreements, locks, timed_details, emotions, npc_time, object_actions, action_observations, behavior, expectations, npc_travel, npc_agency, npc_agenda, incidental_people

def text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid establishment text")
    return value.strip()

def normalize(value):
    return " ".join(value.casefold().split())

def record(state, rules, request, npc_available=None):
    if not rules.get("narrative_establishment") or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("establishment unavailable")
    if not isinstance(request, dict) or len(request) != 1:
        raise ValueError("invalid establishment request")
    operation, payload = next(iter(request.items()))
    if operation == "details":
        return _record_details(state, rules, payload, npc_available)
    if operation == "npc_testimony":
        from age_runtime.mythos import epistemic
        epistemic.record_testimony(state, rules, payload, npc_available)
        for actor in ("speaker", "listener"):
            npc_time.interrupt(state, payload[actor])
        return
    from age_runtime.mythos import epistemic
    # Explicit allowlist. Each native handler retains its own validation.
    # Argument groups reflect existing signatures, not a new effect DSL.
    actor_handlers = {
        "hypothesis": epistemic.establish_hypothesis,
        "belief_revision": epistemic.revise_belief,
        "agreement": agreements.record,
        "transfers": transfer,
        "changes": modify,
    }
    text_handlers = {
        "npc_objective": npc_agency.objective,
        "npc_social_test": npc_agency.social_test,
        "npc_lifecycle": npc_time.lifecycle,
        "routine_observation": behavior.record_routine,
        "npc_travel": npc_travel.record,
        "npc_agenda_depart": npc_agenda.depart,
        "npc_presence": npc_agenda.materialize,
        "incidental_person": incidental_people.record,
        "expectation": expectations.record,
        "behavior": behavior.record,
        "npc_activity": npc_time.record,
        "emotion": emotions.record,
    }
    entity_handlers = {
        "npc_task": timed_details.task_control,
        "npc_native_test": timed_details.native_test,
        "npc_initiative": timed_details.initiative,
        "action_observation": action_observations.record,
        "event": timed_details.record,
        "lock": locks.record,
    }
    if operation in actor_handlers:
        return actor_handlers[operation](state, rules, payload, npc_available)
    if operation in text_handlers:
        return text_handlers[operation](state, rules, payload, npc_available, text)
    if operation in entity_handlers:
        return entity_handlers[operation](state, rules, payload, npc_available, local_entities, text)
    if operation == "object_action":
        return object_actions.record(state, rules, payload, local_entities, text)
    raise ValueError("invalid establishment request")


def _record_details(state, rules, details, npc_available):
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
        if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"properties", "custodian", "function"}:
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
        if "function" in item and (not rules.get("object_function") or item["kind"] != "object"
                                   or item["function"] not in ("operational", "impaired", "nonfunctional")):
            raise ValueError("invalid initial object function")
        holder = item.get("custodian")
        if "custodian" in item:
            if not rules.get("narrative_custody") or item["kind"] != "object":
                raise ValueError("initial custody unavailable")
            if holder is not None and not present_npc(state, rules, holder, npc_available):
                raise ValueError("initial custodian must be present NPC")
            if holder is not None and "placement" in properties:
                raise ValueError("held object has no local placement")
        pending.append({"id": eid, "kind": item["kind"], "label": label,
                        "description": description, "basis": basis,
                        "location": state["location"], "turn": state["turn"],
                        "at": state["time"], "source": "gm_narration",
                        **({"properties": properties} if rules.get("narrative_properties") else {}),
                        **({"function": item["function"]} if "function" in item else {}),
                        **({"custodian": holder} if rules.get("narrative_custody") and item["kind"] == "object" else {})})
    ledger.extend(pending)

# Qualitative presentation only: no numerical stats, possession, access,
# location, evidence, hazard, supernatural effect or mechanical condition.
FIELDS = {"appearance", "condition", "placement"}

def present_npc(state, rules, actor, npc_available):
    return (isinstance(actor, str) and actor in state["npcs"]
            and state["npcs"][actor]["location"] == state["location"]
            and npc_available is not None
            and npc_available(state, rules, {"npc": actor, "location": state["location"]}))

def local_entities(state):
    """Fold descriptive changes over immutable establishment records."""
    entities = {e["id"]: copy.deepcopy(e) for e in state.get("established_details", [])}
    updates = [(c.get("sequence", 0), "property", c) for c in state.get("detail_changes", [])]
    updates += [(c["sequence"], "transfer", c) for c in state.get("custody_transfers", [])]
    updates += [(c["sequence"], "action", c) for c in state.get("object_actions", [])]
    for _, kind, change in sorted(updates, key=lambda entry: entry[0]):
        if kind == "action":
            object_actions.apply(entities[change["object"]], change)
            continue
        entity = entities[change["id"]]
        if kind == "transfer":
            entity["custodian"] = (change.get("protagonist_id", "pc")
                                   if change["to"] == "pc" else change["to"])
            entity["location"] = change["location"]
            entity.setdefault("properties", {}).pop("placement", None)
        else:
            entity.setdefault("properties", {})[change["property"]] = change["after"]
    for entity in entities.values():
        holder = entity.get("custodian")
        if holder == "pc" or (state.get("protagonist") and holder == state["protagonist"]["id"]):
            entity["custodian"] = "pc"
            entity["location"] = state["location"]
        elif isinstance(holder, str) and holder.startswith("pc:"):
            # A predecessor\'s possessions are not available to the active PC.
            # Replacement must establish their final location and transfer authority.
            entity["location"] = None
        elif holder is not None:
            entity["location"] = None if npc_travel.pending(state, holder) else state["npcs"][holder]["location"]
    return {eid: e for eid, e in entities.items() if e["location"] == state["location"]}

def transfer(state, rules, transfers, npc_available):
    if not rules.get("narrative_custody"):
        raise ValueError("narrative custody unavailable")
    if not isinstance(transfers, list) or not 1 <= len(transfers) <= 12:
        raise ValueError("transfer 1 to 12 objects per batch")
    ledger = state["custody_transfers"]
    if len(ledger) + len(transfers) > 256:
        raise ValueError("custody transfer record limit")
    entities = local_entities(state)
    seen = set()
    pending = []
    for item in transfers:
        required = {"id", "from", "to", "pc_authorization", "npc_consent", "basis"}
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("invalid custody transfer fields")
        eid, old, new = item["id"], item["from"], item["to"]
        if not isinstance(eid, str) or eid not in entities or entities[eid]["kind"] != "object":
            raise ValueError("transfer requires local incidental object")
        if eid in seen or old == new or entities[eid].get("custodian") != old:
            raise ValueError("custody precondition mismatch")
        seen.add(eid)
        if "pc" not in (old, new):
            raise ValueError("transfer requires PC participation")
        npcs = []
        for actor in (old, new):
            if actor is None or actor == "pc":
                continue
            if not present_npc(state, rules, actor, npc_available):
                raise ValueError("custodian unavailable")
            npcs.append(actor)
        authorization = text(item["pc_authorization"], 240)
        consent = item["npc_consent"]
        if npcs:
            consent = text(consent, 240)
        elif consent is not None:
            raise ValueError("unexpected NPC consent")
        basis = text(item["basis"], 240)
        pending.append({"transfer_id": len(ledger) + len(pending) + 1,
                        "id": eid, "from": old, "to": new, "sequence": len(state["history"]),
                        **({"protagonist_id": state["protagonist"]["id"]} if state.get("protagonist") else {}),
                        "pc_authorization": authorization, "npc_consent": consent,
                        "basis": basis, "location": state["location"],
                        "turn": state["turn"], "at": state["time"]})
    ledger.extend(pending)

def modify(state, rules, changes, npc_available=None):
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
        if field == "condition" and entities[eid].get("lifecycle", "intact") != "intact":
            raise ValueError("damaged object condition requires lifecycle adjudication")
        if field == "placement" and entities[eid].get("custodian") is not None:
            raise ValueError("held object has no local placement")
        holder = entities[eid].get("custodian")
        if holder not in (None, "pc") and not present_npc(state, rules, holder, npc_available):
            raise ValueError("custodian unavailable")
        old = entities[eid].get("properties", {}).get(field)
        if item["before"] != old:
            raise ValueError("property precondition mismatch")
        new = text(item["after"], 160)
        if old == new:
            raise ValueError("property unchanged")
        basis = text(item["basis"], 240)
        pending.append({"change_id": len(ledger) + len(pending) + 1,
                        "id": eid, "property": field, "before": old, "after": new, "sequence": len(state["history"]),
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
        actions = [copy.deepcopy(c) for c in state.get("object_actions", []) if c["object"] == e["id"]]
        if actions:
            e["action_history"] = actions
        transfers = [copy.deepcopy(c) for c in state.get("custody_transfers", []) if c["id"] == e["id"]]
        if transfers:
            e["custody_history"] = transfers
    return list(entities.values())
