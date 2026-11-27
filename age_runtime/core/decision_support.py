"""Actor-local strategic decision support; no adjudication or inferred intent."""
from copy import deepcopy

from age_runtime.core.institutional_memory import recall


def diplomatic_options(observation, remaining):
    """Surface existing reviewed terms, not predictions of counterpart consent."""
    if remaining == 0:
        return []
    negotiation = observation.get("negotiation", {})
    actor = observation["actor"]
    result = []
    for counterpart, terms in negotiation.get("counterpart_terms", {}).items():
        for ident, term in terms.items():
            result.append({"kind": "transfer_proposal", "counterpart": counterpart,
                           "term": ident, "terms": term,
                           "last_due_minute": negotiation["last_due_minute"],
                           "requires_consent": True})
    for ident, term in negotiation.get("permission_terms", {}).items():
        if term["max_due_minute"] <= observation["minute"]:
            continue
        if any(p.get("permission") == ident and p["status"] in ("proposed", "active")
               for p in negotiation.get("proposals", [])):
            continue
        counterpart = term["grantee"] if actor == term["issuer"] else term["issuer"]
        result.append({"kind": "permission_proposal", "counterpart": counterpart,
                       "term": ident, "terms": term,
                       "last_due_minute": term["max_due_minute"], "requires_consent": True})
    for proposal in negotiation.get("proposals", []):
        if (proposal["recipient"] == actor and proposal["status"] == "proposed"
                and proposal["due_minute"] > observation["minute"]):
            result.append({"kind": "proposal_response", "id": proposal["id"],
                           "counterpart": proposal["proposer"],
                           "due_minute": proposal["due_minute"],
                           "choices": ["accept", "reject", "counter"]})
    return result


def decision_brief(observation):
    """Derive a concise decision packet from the existing observation."""
    history = recall(observation)
    support = observation.get("strategic_support", {})
    options = []
    for ident, description in observation["available_requests"].items():
        option = {"id": ident, "description": description}
        if ident in support.get("capacity_options", {}):
            option.update(kind="capacity", assessment=support["capacity_options"][ident])
        elif ident in support.get("transfer_options", {}):
            option.update(kind="transfer", assessment=support["transfer_options"][ident])
        else:
            agreement = next((aid for aid, record in support.get("agreements", {}).items()
                              if record["consent_action"] == ident), None)
            option.update(kind="consent", agreement=agreement) if agreement else option.update(kind="request")
        options.append(option)
    # Group spending alternatives by their shared observed resource.
    # The sum is an opportunity-cost warning, not a reservation or prediction.
    spending = {}
    for option in options:
        a = option.get("assessment", {})
        if option["kind"] == "capacity":
            key, cost = a["resource"], a["cost"]
        elif option["kind"] == "transfer":
            key, cost = a["source"], a["amount"]
        else:
            continue
        if a["currently_feasible"]:
            group = spending.setdefault(key, {"reported_balance": a["reported_balance"], "alternatives": []})
            group["alternatives"].append({"id": option["id"], "cost": cost})
    conflicts = [{"resource": key, **group}
                 for key, group in spending.items()
                 if sum(a["cost"] for a in group["alternatives"]) > group["reported_balance"]]
    goals = observation.get("faction_strategy", {}).get("goals")
    if goals is None:
        goals = [{"id": oid, "observed_result": result}
                 for oid, result in observation["objectives"].items()]
    return deepcopy({
        "actor": observation["actor"], "turn": observation["turn"], "minute": observation["minute"],
        "goals": goals, "remaining_turns": support.get("remaining_turns"),
        "objective_outcomes": observation.get("objective_outcomes", {}),
        "decision_pacing": observation.get("decision_pacing"),
        "changed_reports": support.get("report_changes", {}),
        "uncertain_reports": {key: report for key, report in observation["reports"].items()
                              if report["status"] in ("stale", "unknown")},
        "deadlines": history["outstanding_deadlines"],
        "pending_orders": support.get("pending_orders", []),
        "projects": history["project_assessments"],
        "recent_decisions": history["decisions"][-3:],
        "recent_claims": history["communications"][-5:],
        "unsettled_propositions": {pid: record for pid, record in history["propositions"].items()
                                   if record["latest_stance"] in ("unstated", "unknown", "doubts")},
        "options": options, "shared_budget_warnings": conflicts,
        "diplomatic_options": diplomatic_options(observation, support.get("remaining_turns")),
        "horizon_basis": support.get("horizon_basis"),
        "negotiation": observation.get("negotiation", {}),
        "guidance": "Retrieve older relevant records before presenting a consequential choice. "
                    "Explain the current stakes, feasible alternatives, uncertainties and prior commitments. "
                    "Do not infer consent, treat claims as facts, or guarantee fulfillment. "
                    "Explain deadline bounds and distinguish immediate marginal benefit from feasibility. "
                    "Include relevant diplomatic alternatives without implying consent or funding. "
                    "Decision targets are advisory; routine orders, reading and ordinary waiting do not require a Critical Decision. "
                    "Count deliberate inaction only when it is a confirmed consequential commitment.",
    })
