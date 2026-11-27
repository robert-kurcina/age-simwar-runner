"""Material faction statements. Speech is not evidence of objective truth."""
from copy import deepcopy


def text_field(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid communication text")
    return value.strip()


def validate(s):
    if "material_communications" in s and (s["material_communications"] is not True or len(s.get("actors", {})) < 2):
        raise ValueError("material communications require multiple actors")


def append(s, state, actor, command):
    if not s.get("material_communications") or actor not in s["actors"] or state["minute"] >= s["end_minute"]:
        raise ValueError("communication unavailable")
    if not isinstance(command, dict) or set(command) - {"id", "recipients", "claim", "corrects"} or not {"id", "recipients", "claim"} <= set(command):
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
    result = deepcopy(state)
    result["requests"].append({"actor": actor, "action": None, "status": "communicated",
        "origin": "communication", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "communication": payload})
    return result


def view(s, state, actor):
    if not s.get("material_communications"):
        return {}
    return {"communications": [
        {"speaker": r["actor"], "turn": r["turn"], "minute": r["minute"], **deepcopy(r["communication"])}
        for r in state["requests"] if r.get("origin") == "communication"
        and (r["actor"] == actor or actor in r["communication"]["recipients"])]}
