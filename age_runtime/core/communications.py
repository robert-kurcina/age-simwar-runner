"""Material faction statements. Speech is not evidence of objective truth."""
from copy import deepcopy


def text_field(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid communication text")
    return value.strip()


def validate(s):
    if "diplomatic_history" in s and (s["diplomatic_history"] is not True or not s.get("material_communications")):
        raise ValueError("diplomatic history requires material communications")
    if "communication_delay_minutes" in s:
        routes = s["communication_delay_minutes"]
        if not s.get("material_communications") or not isinstance(routes, dict):
            raise ValueError("communication delays require material communications")
        for sender, destinations in routes.items():
            if sender not in s["actors"] or not isinstance(destinations, dict):
                raise ValueError("invalid communication sender")
            for recipient, delay in destinations.items():
                if recipient not in s["actors"] or recipient == sender or type(delay) is not int or delay < 0:
                    raise ValueError("invalid communication route delay")
    if "runtime_propositions" in s and (s["runtime_propositions"] is not True or not s.get("material_communications")):
        raise ValueError("runtime propositions require material communications")
    if "material_communications" in s and (s["material_communications"] is not True or len(s.get("actors", {})) < 2):
        raise ValueError("material communications require multiple actors")
    if "communication_propositions" in s:
        registry = s["communication_propositions"]
        if not s.get("material_communications") or not isinstance(registry, dict) or not registry or len(registry) > 128:
            raise ValueError("invalid proposition registry")
        for pid, item in registry.items():
            if text_field(pid, 80) != pid or not isinstance(item, dict) or not {"text", "initial_access"} <= set(item) or set(item) - {"text", "initial_access", "report_binding"}:
                raise ValueError("invalid proposition definition")
            text_field(item["text"], 400)
            if "report_binding" in item:
                binding = item["report_binding"]
                if (not isinstance(binding, dict) or set(binding) != {"key", "comparison", "threshold"}
                        or not isinstance(binding["key"], str) or binding["key"] not in s["initial"]
                        or binding["comparison"] not in ("equal", "at_least", "at_most")
                        or type(binding["threshold"]) is not int):
                    raise ValueError("invalid proposition report binding")
            access = item["initial_access"]
            if not isinstance(access, list) or any(not isinstance(a, str) or a not in s["actors"] for a in access) or len(set(access)) != len(access):
                raise ValueError("invalid initial proposition access")


def append(s, state, actor, command):
    if not s.get("material_communications") or actor not in s["actors"] or state["minute"] >= s["end_minute"]:
        raise ValueError("communication unavailable")
    if not isinstance(command, dict) or set(command) - {"id", "recipients", "claim", "corrects", "proposition", "asserts", "speaker_intent", "introduce_proposition", "private_intention"} or not {"id", "recipients", "claim"} <= set(command):
        raise ValueError("invalid communication fields")
    cid = text_field(command["id"], 80)
    if cid == "authored_access" or (cid.startswith("report:") and any(
            "report_binding" in item for item in s.get("communication_propositions", {}).values())):
        raise ValueError("reserved communication ID")
    claim = text_field(command["claim"], 400)
    recipients = command["recipients"]
    if not isinstance(recipients, list) or not recipients or any(not isinstance(x, str) or x == actor or x not in s["actors"] for x in recipients) or len(set(recipients)) != len(recipients):
        raise ValueError("invalid recipients")
    prior = [r for r in state["requests"] if r.get("origin") == "communication"]
    if len(prior) >= 256 or any(r["communication"]["id"] == cid for r in prior):
        raise ValueError("duplicate ID or communication limit")
    correction = command.get("corrects")
    if "corrects" in command:
        if not isinstance(correction, str) or not any(r["communication"]["id"] == correction and r["actor"] == actor and set(recipients) <= set(r["communication"]["recipients"]) for r in prior):
            raise ValueError("correction requires own prior claim and original recipients")
    payload = {"id": cid, "recipients": sorted(recipients), "claim": claim}
    if correction is not None:
        payload["corrects"] = correction
    if "speaker_intent" in command:
        intent = command["speaker_intent"]
        if intent not in ("unstated", "sincere", "deceive", "fabricate"):
            raise ValueError("invalid speaker intent")
        payload["speaker_intent"] = intent
    if "private_intention" in command:
        intention = command["private_intention"]
        if not s.get("diplomatic_history") or not isinstance(intention, dict) or set(intention) != {"counterpart", "topic", "status", "text", "revises"}:
            raise ValueError("invalid private intention")
        counterpart = intention["counterpart"]
        if not isinstance(counterpart, str) or counterpart not in recipients:
            raise ValueError("intention counterpart must be an actual recipient")
        topic = text_field(intention["topic"], 80)
        statement = text_field(intention["text"], 400)
        status = intention["status"]
        if status not in ("active", "withdrawn"):
            raise ValueError("invalid intention status")
        history = [r["communication"] for r in prior if r["actor"] == actor
                   and r["communication"].get("private_intention", {}).get("counterpart") == counterpart
                   and r["communication"].get("private_intention", {}).get("topic") == topic]
        previous = history[-1]["id"] if history else None
        if intention["revises"] != previous or (status == "withdrawn" and
                (not history or history[-1]["private_intention"]["status"] != "active")):
            raise ValueError("intention revision must reference latest own intention")
        if history and history[-1]["private_intention"]["status"] == status and history[-1]["private_intention"]["text"] == statement:
            raise ValueError("duplicate private intention")
        payload["private_intention"] = {"counterpart": counterpart, "topic": topic,
                                       "status": status, "text": statement, "revises": previous}
    # Introduction is inseparable from the actual originating utterance.
    # It establishes a subject of discourse, never a new world fact.
    if "introduce_proposition" in command:
        introduction = command["introduce_proposition"]
        if not s.get("runtime_propositions") or not isinstance(introduction, dict) or set(introduction) != {"id", "text"}:
            raise ValueError("invalid runtime proposition introduction")
        pid = text_field(introduction["id"], 80)
        statement = text_field(introduction["text"], 400)
        registry = proposition_registry(s, state)
        if (not pid.startswith("inc:") or len(pid) <= 4 or pid in registry
                or len(registry) >= 256 or command.get("proposition") != pid
                or type(command.get("asserts")) is not bool or correction is not None
                or any(item["text"].strip().casefold() == statement.casefold() for item in registry.values())):
            raise ValueError("invalid or duplicate runtime proposition")
        payload.update(introduce_proposition={"id": pid, "text": statement},
                       proposition=pid, asserts=command["asserts"])
    elif "proposition" in command or "asserts" in command:
        pid = command.get("proposition")
        if not isinstance(pid, str) or type(command.get("asserts")) is not bool or not access_sources(s, state, actor, pid):
            raise ValueError("linked claim requires accessible proposition and assertion polarity")
        payload.update(proposition=pid, asserts=command["asserts"])
        if correction is not None:
            earlier = next(r["communication"] for r in prior if r["communication"]["id"] == correction)
            if earlier.get("proposition") != pid:
                raise ValueError("linked correction must address same proposition")
    elif correction is not None and any(r["communication"]["id"] == correction and "proposition" in r["communication"] for r in prior):
        raise ValueError("linked correction requires proposition")
    result = deepcopy(state)
    result["requests"].append({"actor": actor, "action": None, "status": "communicated",
        "origin": "communication", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "communication": payload})
    return result


def observed_report(s, state, actor, key):
    """Single delayed-report projection for observations and evidence."""
    profile = s["actors"][actor]
    if key not in profile.get("visible_keys", []):
        return None
    delay = profile.get("report_delay_minutes", {}).get(key, 0)
    cutoff = state["minute"] - delay
    if cutoff < 0:
        return {"status": "unknown"}
    value = s["initial"][key]
    for entry in state["ledger"]:
        if entry["key"] == key and entry["minute"] <= cutoff:
            value = entry["value"]
    return {"status": "current" if delay == 0 else "stale",
            "as_of_minute": cutoff, "age_minutes": delay, "value": value}


def report_source(s, state, actor, item):
    """Actor-visible snapshot only; no disclosure of unreported current values."""
    binding = item.get("report_binding")
    if binding is None:
        return None
    key = binding["key"]
    report = observed_report(s, state, actor, key)
    if report is None or "value" not in report:
        return None
    cutoff, value = report["as_of_minute"], report["value"]
    threshold = binding["threshold"]
    satisfies = {"equal": value == threshold, "at_least": value >= threshold,
                 "at_most": value <= threshold}[binding["comparison"]]
    return {"kind": "observed_report", "id": "report:" + str(cutoff), "key": key,
            "as_of_minute": cutoff, "value": value, "asserts": satisfies}


def proposition_registry(s, state):
    registry = dict(s.get("communication_propositions", {}))
    for record in state["requests"]:
        if record.get("origin") != "communication":
            continue
        message = record["communication"]
        introduction = message.get("introduce_proposition")
        if introduction is not None:
            registry[introduction["id"]] = {"text": introduction["text"],
                "initial_access": [], "origin_claim": message["id"], "origin_actor": record["actor"]}
    return registry


def delivery_minute(s, record, recipient):
    delay = s.get("communication_delay_minutes", {}).get(record["actor"], {}).get(recipient, 0)
    return record["minute"] + delay


def received(s, state, record, actor):
    return (actor in record["communication"]["recipients"]
            and delivery_minute(s, record, actor) <= state["minute"])


def access_sources(s, state, actor, pid):
    item = proposition_registry(s, state).get(pid)
    if item is None:
        return []
    result = [{"kind": "authored_access"}] if actor in item["initial_access"] else []
    if item.get("origin_actor") == actor:
        result.append({"kind": "originated_claim", "id": item["origin_claim"]})
    # Only actors already granted proposition access may see its registry text.
    # A report binding is not itself permission to discover a private proposition.
    for r in state["requests"]:
        if r.get("origin") != "communication":
            continue
        msg = r["communication"]
        if msg.get("proposition") == pid and received(s, state, r, actor):
            result.append({"kind": "received_claim", "id": msg["id"], "asserts": msg["asserts"]})
    if result:
        report = report_source(s, state, actor, item)
        if report is not None:
            result.append(report)
    return result


def assess(s, state, actor, command):
    """Explicit actor assessment, never a change to world truth."""
    if not s.get("material_communications") or actor not in s["actors"] or state["minute"] >= s["end_minute"]:
        raise ValueError("assessment unavailable")
    if not isinstance(command, dict) or set(command) != {"proposition", "stance", "basis"}:
        raise ValueError("invalid assessment fields")
    pid, stance, basis = command["proposition"], command["stance"], command["basis"]
    if not isinstance(pid, str) or stance not in ("believes", "doubts", "disbelieves", "unknown"):
        raise ValueError("invalid assessment")
    sources = access_sources(s, state, actor, pid)
    allowed = {x.get("id", "authored_access") for x in sources}
    if not isinstance(basis, list) or not basis or any(not isinstance(x, str) or x not in allowed for x in basis) or len(set(basis)) != len(basis):
        raise ValueError("assessment requires accessible basis")
    prior = [r for r in state["requests"] if r.get("origin") == "assessment"]
    if len(prior) >= 256:
        raise ValueError("assessment limit")
    result = deepcopy(state)
    evidence = [deepcopy(x) for x in sources if x.get("id", "authored_access") in basis]
    record = {"proposition": pid, "stance": stance, "basis": sorted(basis)}
    if any(x["kind"] == "observed_report" for x in evidence):
        record["report_evidence"] = [x for x in evidence if x["kind"] == "observed_report"]
    result["requests"].append({"actor": actor, "action": None, "status": "assessed",
        "origin": "assessment", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "assessment": record})
    return result


def propositions_view(s, state, actor):
    result = {}
    for pid, item in proposition_registry(s, state).items():
        sources = access_sources(s, state, actor, pid)
        if not sources:
            continue
        history = [{"turn": r["turn"], "minute": r["minute"], **deepcopy(r["assessment"])}
                   for r in state["requests"] if r.get("origin") == "assessment" and r["actor"] == actor
                   and r["assessment"]["proposition"] == pid]
        result[pid] = {"text": item["text"], "sources": sources, "assessments": history,
                       "latest_stance": history[-1]["stance"] if history else "unstated"}
    return result


def view(s, state, actor):
    if not s.get("material_communications"):
        return {}
    messages = []
    for r in state["requests"]:
        if r.get("origin") != "communication":
            continue
        sender = r["actor"] == actor
        if not sender and not received(s, state, r, actor):
            continue
        message = {"speaker": r["actor"], "turn": r["turn"], "minute": r["minute"],
                   **{k: deepcopy(v) for k, v in r["communication"].items()
                      if k not in ("speaker_intent", "private_intention") or sender}}
        if "communication_delay_minutes" in s:
            if sender:
                message["scheduled_delivery"] = {
                    a: delivery_minute(s, r, a) for a in r["communication"]["recipients"]}
                # This is a schedule, not an acknowledgement by the recipient.
            else:
                message["delivery_minute"] = delivery_minute(s, r, actor)
        messages.append(message)
    return {**({"propositions": propositions_view(s, state, actor)}
               if "communication_propositions" in s or s.get("runtime_propositions") else {}),
            "communications": messages}
