"""One-shot, reviewed strategic developments. Selection is not fulfillment."""
from copy import deepcopy
from age_runtime.core.actions import stock_owners
from age_runtime.core.communications import text_field


def validate(s):
    if "event_templates" not in s:
        return
    templates = s["event_templates"]
    # First adopter slice is civilian economic/institutional inspection,
    # not a general-purpose writer to governed properties.
    if not isinstance(templates, dict) or not 1 <= len(templates) <= 64 or not s.get("economy_projects"):
        raise ValueError("event templates require reviewed civilian projects")
    protected = set(stock_owners(s))
    protected.update(p[k] for p in s["economy_projects"] for k in ("progress", "delay", "complications"))
    protected.update(a["key"] for p in s["economy_projects"] for a in p["axes"])
    protected.update(a["outcome"] for a in s.get("agreements", {}).values() if "outcome" in a)
    protected.update(e["key"] for e in s["events"])
    protected.update(k for e in s.get("dependent_events", []) for k in e["updates"])
    for flag, keys in (("service_restoration", ("open_service_centers", "restoration_credits")),
                       ("community_assistance", ("households_assisted", "aid_packages")),
                       ("civic_agreement", ("participating_councils", "council_a_joined", "council_b_joined"))):
        if s.get(flag):
            protected.update(keys)
    outputs = set()
    for tid, t in templates.items():
        if (not isinstance(tid, str) or not tid.strip() or len(tid) > 80
                or not isinstance(t, dict)
                or set(t) != {"description", "participant", "audience", "requires", "permission", "outcome"}):
            raise ValueError("invalid event template")
        text_field(t["description"], 400)
        actor, audience = t["participant"], t["audience"]
        if (not isinstance(actor, str) or actor not in s["actors"]
                or not isinstance(audience, list) or actor not in audience
                or any(not isinstance(a, str) or a not in s["actors"] for a in audience)
                or len(set(audience)) != len(audience)):
            raise ValueError("invalid event audience")
        key = t["outcome"]
        if (not isinstance(key, str) or key not in s["initial"] or s["initial"][key] != 0
                or key in protected or key in outputs):
            raise ValueError("event requires dedicated initially unset outcome")
        outputs.add(key)
        for a, profile in s["actors"].items():
            # Outcome reporting must have exactly the same audience as the
            # development itself. Delayed reports delay the description too.
            if (key in profile.get("visible_keys", [])) != (a in audience):
                raise ValueError("event outcome visibility must match audience")
        req = t["requires"]
        if not isinstance(req, dict) or any(
                k not in s["actors"][actor].get("visible_keys", [])
                or s["actors"][actor].get("report_delay_minutes", {}).get(k, 0)
                or type(n) is not int for k, n in req.items()):
            raise ValueError("event conditions require current participant reports")
        permission = t["permission"]
        if permission is not None:
            term = s.get("permission_terms", {}).get(permission) if isinstance(permission, str) else None
            if not term or term["grantee"] != actor or not set(audience) <= {term["issuer"], actor}:
                raise ValueError("event permission must match reviewed participant and audience")
        elif not req:
            raise ValueError("event requires explicit eligibility")


def append(s, state, command):
    if not isinstance(command, dict) or set(command) != {"template", "due_minute", "permission_id", "rationale"}:
        raise ValueError("invalid event selection")
    tid, due, pid = (command[k] for k in ("template", "due_minute", "permission_id"))
    templates = s.get("event_templates", {})
    if (not isinstance(tid, str) or tid not in templates
            or tid in state.get("generated_events", {})
            or type(due) is not int or not state["minute"] < due <= s["end_minute"]
            or due % s["turn_minutes"]):
        raise ValueError("invalid event identity or due boundary")
    t = templates[tid]
    if t["permission"] is None:
        if pid is not None:
            raise ValueError("unexpected permission reference")
    else:
        p = state.get("negotiations", {}).get(pid) if isinstance(pid, str) else None
        if not p or p.get("permission") != t["permission"] or p["status"] != "active" or due >= p["due_minute"]:
            raise ValueError("event requires active permission through due boundary")
    if not all(state["values"][k] >= n for k, n in t["requires"].items()):
        raise ValueError("event prerequisites not met at selection")
    payload = {**deepcopy(command), "rationale": text_field(command["rationale"], 400)}
    result = deepcopy(state)
    result["generated_events"][tid] = {**payload, "scheduled_minute": state["minute"], "status": "scheduled"}
    result["requests"].append({"actor": None, "action": None, "origin": "generated_development",
        "status": "scheduled", "turn": state["turn"], "minute": state["minute"],
        "sequence": len(state["requests"]) + 1, "development": payload})
    return result


def resolve(s, state, minute):
    for tid, record in sorted(state.get("generated_events", {}).items()):
        if record["due_minute"] != minute or record["status"] != "scheduled":
            continue
        t = s["event_templates"][tid]
        key = t["outcome"]
        p = state.get("negotiations", {}).get(record["permission_id"])
        authorized = t["permission"] is None or bool(
            p and p.get("permission") == t["permission"] and p["status"] == "active"
            and minute < p["due_minute"])
        if not authorized or state["values"][key] != 0 or not all(
                state["values"][k] >= n for k, n in t["requires"].items()):
            record["status"] = "prerequisite_unmet"
        else:
            state["values"][key] = 1
            state["ledger"].append({"id": "generated:" + tid, "minute": minute,
                                    "key": key, "delta": 1, "value": 1})
            record["status"] = "completed"


def view(s, state, actor):
    if "event_templates" not in s:
        return {}
    visible = []
    for tid, record in sorted(state["generated_events"].items()):
        t = s["event_templates"][tid]
        if actor not in t["audience"] or record["status"] != "completed":
            continue
        delay = s["actors"][actor].get("report_delay_minutes", {}).get(t["outcome"], 0)
        if record["due_minute"] + delay <= state["minute"]:
            visible.append({"id": tid, "description": t["description"], "minute": record["due_minute"],
                            "outcome_key": t["outcome"], "source": "resolved_development"})
    return {"developments": visible}
