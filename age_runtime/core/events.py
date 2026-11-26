"""Bounded, one-shot civilian institutional events.

A fixed due time, explicit conditions and finite updates. No arbitrary
expressions, retries, implicit authority or unrecorded model decisions.
"""
def validate_dependent_events(s):
    events = s.get("dependent_events", [])
    if not isinstance(events, list):
        raise ValueError("dependent_events must be a list")
    ids = {e["id"] for e in s["events"]}
    for e in events:
        if not isinstance(e, dict) or set(e) != {"id", "minute", "participant", "requires", "updates"}:
            raise ValueError("invalid dependent event fields")
        if not isinstance(e["id"], str) or not e["id"].strip() or e["id"] in ids:
            raise ValueError("invalid or duplicate dependent event ID")
        ids.add(e["id"])
        if type(e["minute"]) is not int or not 0 < e["minute"] <= s["end_minute"]:
            raise ValueError("dependent event outside horizon")
        if not isinstance(e["participant"], str) or e["participant"] not in s.get("actors", {}):
            raise ValueError("unknown dependent event participant")
        actor = s["actors"][e["participant"]]
        req = e["requires"]
        if not isinstance(req, list) or not req:
            raise ValueError("dependent event requires explicit conditions")
        seen = set()
        for c in req:
            if not isinstance(c, dict) or set(c) != {"key", "at_least"}:
                raise ValueError("invalid dependent event condition")
            key = c["key"]
            if not isinstance(key, str) or key not in s["initial"] or key in seen or type(c["at_least"]) is not int:
                raise ValueError("invalid dependent event threshold")
            if key not in actor.get("visible_keys", []) or actor.get("report_delay_minutes", {}).get(key, 0):
                raise ValueError("condition not currently observable by participant")
            seen.add(key)
        updates = e["updates"]
        if not isinstance(updates, dict) or not updates:
            raise ValueError("dependent event requires updates")
        if any(k not in s["initial"] or type(v) is not int or v == 0 for k, v in updates.items()):
            raise ValueError("invalid dependent event update")
        minima = {c["key"]: c["at_least"] for c in req}
        for key, delta in updates.items():
            if key not in actor.get("visible_keys", []) or actor.get("report_delay_minutes", {}).get(key, 0):
                raise ValueError("event update not currently observable by participant")
            if delta < 0 and minima.get(key, -1) < -delta:
                raise ValueError("dependent event debit lacks resource guard")

def resolve_dependent_events(s, state, minute):
    """Resolve same-minute events in authored order, once, after reviews."""
    if "dependent_events" not in s:
        return
    seen = {e["id"] for e in state["background_events"]}
    for event in s["dependent_events"]:
        if event["minute"] != minute or event["id"] in seen:
            continue
        passed = all(state["values"][c["key"]] >= c["at_least"] for c in event["requires"])
        state["background_events"].append({
            "id": event["id"], "minute": minute, "participant": event["participant"],
            "outcome": "completed" if passed else "prerequisite_unmet"})
        if passed:
            for key, delta in sorted(event["updates"].items()):
                state["values"][key] += delta
                state["ledger"].append({"id": event["id"], "minute": minute, "key": key,
                                        "delta": delta, "value": state["values"][key]})
