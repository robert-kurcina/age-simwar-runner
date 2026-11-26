"""Read-only actor projections. Full checkpoints are referee-only."""
from copy import deepcopy
from age_runtime.core.actions import available_requests
from age_runtime.core.actors import evaluate
from age_runtime.core.economy import bottleneck

def validate_views(s):
    for actor in s.get("actors", {}).values():
        keys = actor.get("visible_keys", [])
        if not isinstance(keys, list) or any(not isinstance(k, str) or k not in s["initial"] for k in keys):
            raise ValueError("invalid visible_keys")
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate visible key")
        delays = actor.get("report_delay_minutes", {})
        if not isinstance(delays, dict) or any(k not in keys or type(v) is not int or v < 0 for k, v in delays.items()):
            raise ValueError("invalid report delay")

def strategic_support(s, state, actor_id, values, reports, projects, requests):
    """Derived actor-local assessments; no predicted adjudication or new state."""
    assessments = []
    for p in projects:
        ratings = [(a["axis"], values[a["key"]]) for a in p["axes"]]
        current = bottleneck(p["need"], ratings)
        assessments.append({"id": p["id"], "progress": values[p["progress"]],
                            "stages": p["stages"], "delay": values[p["delay"]],
                            "complications": values[p["complications"]],
                            "complete": values[p["progress"]] >= p["stages"],
                            "capacities": dict(ratings), "bottleneck": current})
    choices = {}
    own_projects = {p["id"]: p for p in projects}
    for action in requests:
        a = s.get("capacity_actions", {}).get(action)
        if a is None or a["project"] not in own_projects:
            continue
        p = own_projects[a["project"]]
        rating = values[a["capacity"]]
        balance = values[a["resource"]]
        reason = ("project_complete" if values[p["progress"]] >= p["stages"] else
                  "capacity_at_limit" if rating >= 5 else
                  "insufficient_resources" if balance < a["cost"] else None)
        choice = {"project": p["id"], "resource": a["resource"], "cost": a["cost"],
                  "reported_balance": balance, "capacity": a["capacity"],
                  "current_rating": rating, "currently_feasible": reason is None,
                  "reason": reason}
        if reason is None:
            choice["if_fulfilled"] = {
                "balance": balance - a["cost"], "rating": rating + 1,
                "bottleneck": bottleneck(p["need"], [
                    (x["axis"], values[x["key"]] + (x["key"] == a["capacity"]))
                    for x in p["axes"]])}
        choices[action] = choice
    # Compare report cutoffs, not hidden current values. A delayed report may
    # first become available this turn; never infer the unknown prior value.
    changes = {}
    if state["turn"]:
        previous = max(0, (state["turn"] - 1) * s["turn_minutes"])
        for key, report in reports.items():
            if "value" not in report:
                continue
            cutoff = previous - report["age_minutes"]
            if cutoff < 0:
                changes[key] = {"status": "newly_reported", "value": report["value"]}
                continue
            before = s["initial"][key]
            for entry in state["ledger"]:
                if entry["key"] == key and entry["minute"] <= cutoff:
                    before = entry["value"]
            if before != report["value"]:
                changes[key] = {"status": "changed", "before": before,
                                "value": report["value"], "delta": report["value"] - before}
    return {"project_assessments": assessments, "capacity_options": choices,
            "report_changes": changes,
            "pending_orders": [{k: deepcopy(v) for k, v in r.items() if k != "sequence"}
                               for r in state["requests"] if r["actor"] == actor_id
                               and r["status"] == "validated_request"],
            "latest_project_results": [deepcopy(r) for r in state.get("project_results", [])
                                       if r["participant"] == actor_id and r["minute"] == state["minute"]],
            "remaining_turns": (max(0, s["end_minute"] - state["minute"]) + s["turn_minutes"] - 1) // s["turn_minutes"],
            "option_basis": "Current reported values; pending orders, competing spending and future events may change fulfillment."}


def observe(s, state, actor_id):
    actor = s.get("actors", {}).get(actor_id)
    if actor is None:
        raise ValueError("unknown actor")
    keys = set(actor.get("visible_keys", []))
    reports = {}
    values = {}
    for key in sorted(keys):
        delay = actor.get("report_delay_minutes", {}).get(key, 0)
        cutoff = state["minute"] - delay
        if cutoff < 0:
            reports[key] = {"status": "unknown"}
            continue
        value = s["initial"][key]
        for entry in state["ledger"]:
            if entry["key"] == key and entry["minute"] <= cutoff:
                value = entry["value"]
        values[key] = value
        reports[key] = {"status": "current" if delay == 0 else "stale",
                        "as_of_minute": cutoff, "age_minutes": delay,
                        "value": value}
    # Evaluate only objectives supported by the actor's observed values.
    observed_actor = {**actor, "objectives": {
        oid: obj for oid, obj in actor.get("objectives", {}).items()
        if obj["key"] in values}}
    observed_objectives = evaluate({"actors": {actor_id: observed_actor}}, values)[actor_id]["objectives"]
    projects = [{"id": p["id"], "need": p["need"], "stages": p["stages"],
                 "axes": deepcopy(p["axes"]), "progress": p["progress"],
                 "delay": p["delay"], "complications": p["complications"]}
                for p in s.get("economy_projects", []) if p["participant"] == actor_id]
    requests = available_requests(s, actor_id) if state["minute"] < s["end_minute"] else {}
    return {
        **({"strategic_support": strategic_support(s, state, actor_id, values, reports, projects, requests)} if "economy_projects" in s else {}),
        **({"projects": projects} if "economy_projects" in s else {}),
        **({"faction_context": deepcopy(actor["faction_context"]["profile"])} if "faction_context" in actor else {}),
        **({"project_results": [deepcopy(r) for r in state["project_results"] if r["participant"] == actor_id]} if "project_results" in state else {}),
        "actor": actor_id,
        "minute": state["minute"],
        "turn": state["turn"],
        "values": values,
        "reports": reports,
        "own_requests": [{k: deepcopy(v) for k, v in r.items() if k != "sequence"}
                         for r in state["requests"] if r["actor"] == actor_id],
        "available_requests": requests,
        "objectives": observed_objectives
    }
