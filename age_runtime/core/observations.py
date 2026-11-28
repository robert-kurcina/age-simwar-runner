"""Read-only actor projections. Full checkpoints are referee-only."""
from copy import deepcopy
from age_runtime.core.communications import view as communication_view, observed_report
from age_runtime.core.negotiation import view as negotiation_view
from age_runtime.core.actions import available_requests
from age_runtime.core.actors import evaluate
from age_runtime.core.economy import bottleneck, dependency_status
from age_runtime.core.diplomacy import history as diplomatic_history
from age_runtime.core.establishment import view as established_context
from age_runtime.core.event_generator import view as development_view
from age_runtime.core.phase_memory import view as historical_view

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
    remaining = (max(0, s["end_minute"] - state["minute"]) + s["turn_minutes"] - 1) // s["turn_minutes"]
    assessments = []
    for p in projects:
        ratings = [(a["axis"], values[a["key"]]) for a in p["axes"]]
        current = bottleneck(p["need"], ratings)
        dependencies = dependency_status(s, p["id"], values)
        blocked = any(not row["met"] for row in dependencies)
        stages_left = p["stages"] - values[p["progress"]]
        assessments.append({"id": p["id"],
                            "horizon": {"stages_remaining": stages_left,
                                        "maximum_future_stages": remaining,
                                        "slack_turns": remaining - stages_left,
                                        "possible_at_maximum_rate": stages_left <= remaining,
                                        "progress_if_capacity_unchanged": min(stages_left, remaining) if current["outcome"] == "clear" and not blocked else 0}, "progress": values[p["progress"]],
                            "stages": p["stages"], "delay": values[p["delay"]],
                            "complications": values[p["complications"]],
                            "complete": values[p["progress"]] >= p["stages"],
                            "capacities": dict(ratings), "bottleneck": current,
                            **({"dependencies": dependencies, "dependency_blocked": blocked} if dependencies else {})})
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
        if reason is None:
            before = bottleneck(p["need"], [(x["axis"], values[x["key"]]) for x in p["axes"]])
            after = choice["if_fulfilled"]["bottleneck"]
            choice["project_effect"] = ("already_clear" if before["outcome"] == "clear" else
                                        "clears_bottleneck" if after["outcome"] == "clear" else
                                        "reduces_shortfall" if after["shortfall"] < before["shortfall"] else
                                        "no_immediate_shortfall_reduction")
        dependencies = dependency_status(s, p["id"], values)
        if dependencies:
            choice["dependencies"] = dependencies
            choice["dependency_blocked"] = any(not row["met"] for row in dependencies)
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
    transfers = {}
    for name in requests:
        t = s.get("resource_transfers", {}).get(name)
        if t is not None:
            balance = values[t["source"]]
            transfers[name] = {"source": t["source"], "destination": t["destination"],
                               "amount": t["amount"], "reported_balance": balance,
                               "currently_feasible": balance >= t["amount"]}
    agreements = {}
    for aid, a in s.get("agreements", {}).items():
        if actor_id not in a["consent"]:
            continue
        signed = sorted(actor for actor, action in a["consent"].items()
                        if any(r["actor"] == actor and r["action"] == action
                               and r["status"] == "reviewed" for r in state["requests"]))
        result = next((r["status"] for r in state.get("agreement_results", []) if r["id"] == aid), None)
        agreements[aid] = {"description": a["description"], "due_minute": a["due_minute"],
                           "consent_action": a["consent"][actor_id], "consenting": signed,
                           **({"participants": sorted(a["consent"])} if s.get("diplomatic_history") else {}),
                           **({"outcome": a["outcome"], "requires": a["requires"]} if "outcome" in a else
                              {"terms": [deepcopy(s["resource_transfers"][t]) for t in a["transfers"]]}),
                           "status": result or ("committed" if len(signed) == len(a["consent"]) else "awaiting_consent")}
    return {**({"agreements": agreements} if "agreements" in s else {}),
            **({"transfer_options": transfers} if "resource_transfers" in s else {}),
            "project_assessments": assessments, "capacity_options": choices,
            "report_changes": changes,
            "pending_orders": [{k: deepcopy(v) for k, v in r.items() if k != "sequence"}
                               for r in state["requests"] if r["actor"] == actor_id
                               and r["status"] == "validated_request"],
            "latest_project_results": [deepcopy(r) for r in state.get("project_results", [])
                                       if r["participant"] == actor_id and r["minute"] == state["minute"]],
            "remaining_turns": remaining,
            "horizon_basis": "At most one project stage per resolution; constant-capacity illustration excludes pending orders and future changes, including future prerequisite completion.",
            "option_basis": "Current reported values; pending orders, competing spending and future events may change fulfillment."}


def observe(s, state, actor_id):
    actor = s.get("actors", {}).get(actor_id)
    if actor is None:
        raise ValueError("unknown actor")
    keys = set(actor.get("visible_keys", []))
    reports = {}
    values = {}
    for key in sorted(keys):
        report = observed_report(s, state, actor_id, key)
        reports[key] = report
        if "value" in report:
            values[key] = report["value"]
    # Evaluate only objectives supported by the actor's observed values.
    observed_actor = {**actor, "objectives": {
        oid: obj for oid, obj in actor.get("objectives", {}).items()
        if obj["key"] in values}}
    observed_objectives = evaluate({"actors": {actor_id: observed_actor}}, values)[actor_id]["objectives"]
    projects = [{"id": p["id"], "need": p["need"], "stages": p["stages"],
                 "axes": deepcopy(p["axes"]), "progress": p["progress"],
                 "delay": p["delay"], "complications": p["complications"]}
                for p in s.get("economy_projects", []) if p["participant"] == actor_id]
    requests = available_requests(s, actor_id, state) if state["minute"] < s["end_minute"] else {}
    pacing = {}
    if "game_length" in s and actor_id not in s.get("model_factions", []):
        from age_runtime.core.runner import GAME_LENGTHS
        committed = [r for r in state["requests"] if r["actor"] == actor_id
                     and r.get("origin") == "critical_decision"]
        pacing = {"decision_pacing": {"game_length": s["game_length"],
                   "target": GAME_LENGTHS[s["game_length"]], "count": len(committed),
                   "advisory": True}}
    strategy = {}
    if "strategy" in actor:
        # Own goals are known even when the supporting report has not arrived.
        # Never infer another faction's intentions from the referee configuration.
        strategy = {"faction_strategy": {
            "motivation": actor["strategy"]["motivation"],
            "goals": [{"id": oid, **deepcopy(actor["objectives"][oid]),
                       "observed_result": deepcopy(observed_objectives.get(oid))}
                      for oid in actor["strategy"]["priorities"]]}}
    from age_runtime.core.opportunity_latitude import objective_outcomes
    institutional = {aid: {"outcome": a["outcome"], "requires": a["requires"],
                           "due_minute": a["due_minute"]}
                     for aid, a in s.get("agreements", {}).items()
                     if "outcome" in a and actor_id in a["consent"]}
    outcomes = objective_outcomes(actor.get("objectives", {}), observed_objectives, reports,
                                  projects, state["minute"], s["end_minute"], s["turn_minutes"],
                                  institutional)
    observation = {
        "objective_outcomes": outcomes,
        **negotiation_view(s, state, actor_id),
        **communication_view(s, state, actor_id),
        **development_view(s, state, actor_id),
        **({"phase_memory": historical_view(s, actor_id)} if "phase_memory" in s else {}),
        **strategy,
        **pacing,
        **({"strategic_support": strategic_support(s, state, actor_id, values, reports, projects, requests)} if "economy_projects" in s or "agreements" in s else {}),
        **({"projects": projects} if "economy_projects" in s else {}),
        **({"faction_context": deepcopy(actor["faction_context"]["profile"])} if "faction_context" in actor else {}),
        **({"project_results": [deepcopy(r) for r in state["project_results"] if r["participant"] == actor_id]} if "project_results" in state else {}),
        "actor": actor_id,
        "minute": state["minute"],
        "turn": state["turn"],
        "values": values,
        "reports": reports,
        "own_requests": [{k: deepcopy(v) for k, v in r.items() if k != "sequence"}
                         for r in state["requests"] if r["actor"] == actor_id and r.get("origin") not in ("communication", "assessment", "diplomatic_record")],
        "available_requests": requests,
        "objectives": observed_objectives
    }
    if s.get("strategic_establishment"):
        observation["established_context"] = established_context(s, state, actor_id)
    if s.get("diplomatic_history"):
        observation["diplomatic_history"] = diplomatic_history(observation, state)
    return observation
