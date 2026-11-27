"""Actor-local strategic decision support; no adjudication or inferred intent."""
from copy import deepcopy

from age_runtime.core.institutional_memory import recall


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
        "negotiation": observation.get("negotiation", {}),
        "guidance": "Retrieve older relevant records before presenting a consequential choice. "
                    "Explain the current stakes, feasible alternatives, uncertainties and prior commitments. "
                    "Do not infer consent, treat claims as facts, or guarantee fulfillment. "
                    "Decision targets are advisory; routine orders and reading do not require a Critical Decision.",
    })
