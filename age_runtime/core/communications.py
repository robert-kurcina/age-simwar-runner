"""Material faction statements. Speech is not evidence of objective truth."""
from copy import deepcopy


def text_field(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid communication text")
    return value.strip()


def validate(s):
    if "material_communications" in s and (s["material_communications"] is not True or len(s.get("actors", {})) < 2):
        raise ValueError("material communications require multiple actors")
    if "communication_propositions" in s:
        registry = s["communication_propositions"]
        if not s.get("material_communications") or not isinstance(registry, dict) or not registry or len(registry) > 128:
            raise ValueError("invalid proposition registry")
        for pid, item in registry.items():
            if text_field(pid, 80) != pid or not isinstance(item, dict) or set(item) != {"text", "initial_access"}:
                raise ValueError("invalid proposition definition")
            text_field(item["text"], 400)
            access = item["initial_access"]
            if not isinstance(access, list) or any(not isinstance(a, str) or a not in s["actors"] for a in access) or len(set(access)) != len(access):
                raise ValueError("invalid initial proposition access")


def append(s, state, actor, command):
    if not s.get("material_communications") or actor not in s["actors"] or state["minute"] >= s["end_minute"]:
        raise ValueError("communication unavailable")
    if not isinstance(command, dict) or set(command) - {"id", "recipients", "claim", "corrects", "proposition", "asserts"} or not {"id", "recipients", "claim"} <= set(command):
        raise ValueError("invalid communication fields")
    cid = text_field(command["id"], 80)
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
    if "proposition" in command or "asserts" in command:
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


def access_sources(s, state, actor, pid):
    item = s.get("communication_propositions", {}).get(pid)
    if item is None:
        return []
    result = [{"kind": "authored_access"}] if actor in item["initial_access"] else []
    for r in state["requests"]:
        if r.get("origin") != "communication":
            continue
        msg = r["communication"]
        if msg.get("proposition") == pid and actor in msg["recipients"]:
            result.append({"kind": "received_claim", "id": msg["id"], "asserts": msg["asserts"]})
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
    result["requests"].append({"actor": actor, "action": None, "status": "assessed",
        "origin": "assessment", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "assessment": {"proposition": pid, "stance": stance, "basis": sorted(basis)}})
    return result


def propositions_view(s, state, actor):
    result = {}
    for pid, item in s.get("communication_propositions", {}).items():
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
    return {**({"propositions": propositions_view(s, state, actor)} if "communication_propositions" in s else {}), "communications": [
        {"speaker": r["actor"], "turn": r["turn"], "minute": r["minute"], **deepcopy(r["communication"])}
        for r in state["requests"] if r.get("origin") == "communication"
        and (r["actor"] == actor or actor in r["communication"]["recipients"])]}
