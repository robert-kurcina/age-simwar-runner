"""Scenario-reviewed event templates; referee selects, scripts resolve."""
from copy import deepcopy


def validate(s):
    if "event_templates" not in s:
        return
    templates = s["event_templates"]
    if not isinstance(templates, dict) or not templates or not s.get("economy_projects"):
        raise ValueError("event templates require reviewed economy projects")
    protected = {p[k] for p in s["economy_projects"] for k in ("progress", "delay", "complications")}
    protected |= {a["key"] for p in s["economy_projects"] for a in p["axes"]}
    protected |= {a["resource"] for a in s.get("capacity_actions", {}).values()}
    for tid, t in templates.items():
        if (not isinstance(tid, str) or not tid.strip() or not isinstance(t, dict)
                or set(t) != {"description", "audience", "requires", "updates"}):
            raise ValueError("invalid event template")
        if not isinstance(t["description"], str) or not t["description"].strip():
            raise ValueError("event description required")
        audience = t["audience"]
        if (not isinstance(audience, list) or not audience
                or any(not isinstance(a, str) or a not in s["actors"] for a in audience)
                or len(set(audience)) != len(audience)):
            raise ValueError("invalid event audience")
        req = t["requires"]
        if not isinstance(req, dict) or not req or any(k not in s["initial"] or type(n) is not int for k, n in req.items()):
            raise ValueError("event requires explicit property thresholds")
        updates = t["updates"]
        if (not isinstance(updates, dict) or not updates
                or any(k not in s["initial"] or k in protected or type(d) is not int or not d
                       for k, d in updates.items())):
            raise ValueError("event updates must use unprotected scenario properties")
        for key, delta in updates.items():
            if s["initial"][key] < 0 or (delta < 0 and req.get(key, -1) < -delta):
                raise ValueError("event update lacks nonnegative guard")
            if any(key not in s["actors"][a].get("visible_keys", [])
                   or s["actors"][a].get("report_delay_minutes", {}).get(key, 0) for a in audience):
                raise ValueError("event effect must be observable by audience")


def schedule(s, state, proposal):
    if not isinstance(proposal, dict) or set(proposal) != {"template", "due_minute", "rationale"}:
        raise ValueError("invalid event proposal")
    tid, due, why = (proposal[k] for k in ("template", "due_minute", "rationale"))
    if (not isinstance(tid, str) or tid not in s.get("event_templates", {})
            or tid in state.get("generated_events", {})
            or type(due) is not int or not state["minute"] < due <= s["end_minute"]
            or due % s["turn_minutes"]
            or not isinstance(why, str) or not why.strip() or len(why) > 2000):
        raise ValueError("invalid event selection, timing or rationale")
    state["generated_events"][tid] = {**deepcopy(proposal), "status": "scheduled"}


def resolve(s, state, minute):
    for tid, record in sorted(state.get("generated_events", {}).items()):
        if record["due_minute"] != minute or record["status"] != "scheduled":
            continue
        t = s["event_templates"][tid]
        v = state["values"]
        if not all(v[k] >= n for k, n in t["requires"].items()) or any(v[k] + d < 0 for k, d in t["updates"].items()):
            record["status"] = "prerequisite_unmet"
            continue
        for key, delta in sorted(t["updates"].items()):
            v[key] += delta
            state["ledger"].append({"id": "generated:" + tid + ":" + key,
                "minute": minute, "key": key, "delta": delta, "value": v[key]})
        record["status"] = "completed"


def view(s, state, actor):
    if "event_templates" not in s:
        return {}
    return {"developments": [{"id": tid, "description": s["event_templates"][tid]["description"],
                              "minute": record["due_minute"]}
            for tid, record in sorted(state["generated_events"].items())
            if record["status"] == "completed" and actor in s["event_templates"][tid]["audience"]]}


def packet(s, state):
    return {"minute": state["minute"], "turn": state["turn"], "values": deepcopy(state["values"]),
            "templates": {tid: deepcopy(t) for tid, t in s.get("event_templates", {}).items()
                          if tid not in state.get("generated_events", {})}}
