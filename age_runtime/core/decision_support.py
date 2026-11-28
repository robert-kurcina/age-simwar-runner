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


def matrix_choices(observation):
    """Explain cost and goal tension using only actor-visible opening reports.

    Isolated bounded effects are illustrative, never predicted net outcomes.
    No opponent order, hidden balance, or invented probability enters here.
    """
    matrix = observation["matrix"]
    choices = []
    for action, effects in matrix["own_options"].items():
        row = {"id": action, "contributions": effects, "cost": None,
               "opening_feasibility": "unconfirmed", "goal_tradeoffs": []}
        for aid, account in observation.get("reserve_accounts", {}).items():
            spec = account["options"].get(action)
            if spec is None:
                continue
            op, slot = spec["operation"], spec["commitment"]
            active = account["commitments"].get(slot, 0)
            cost = spec["amount"] if op in ("reserve", "spend") else 0
            row["cost"] = {"account": aid, "kind": "reserve", "operation": op,
                           "amount": cost, "available": account["available"],
                           "pending": account["pending_gross_allocations"]}
            eligible = (not active if op == "reserve" else bool(active) if op in ("release", "consume") else True)
            row["opening_feasibility"] = ("commitment_state_conflict" if not eligible else
                "insufficient_unallocated_balance" if cost and cost + account["pending_gross_allocations"] > account["available"]
                else "within_opening_limits")
        for aid, account in observation.get("stock_accounts", {}).items():
            spec = account["options"].get(action)
            if spec is None:
                continue
            row["cost"] = {"account": aid, "kind": "stock", "amount": spec["amount"],
                           "available": account["balance"], "pending": account["pending_gross_debits"]}
            row["opening_feasibility"] = ("within_opening_limits"
                if spec["amount"] + account["pending_gross_debits"] <= account["balance"]
                else "insufficient_unallocated_balance")
        for goal in observation.get("faction_strategy", {}).get("goals", []):
            key = goal["key"]
            prop = matrix["properties"].get(key)
            if key not in effects or not prop or prop["reported_value"] is None:
                continue
            before = prop["reported_value"]
            after = max(prop["minimum"], min(prop["maximum"], before + effects[key]))
            threshold, comparison = goal["threshold"], goal["comparison"]
            def distance(value):
                if comparison == "at_least":
                    return max(0, threshold - value)
                if comparison == "at_most":
                    return max(0, value - threshold)
                return abs(value - threshold)
            old, new = distance(before), distance(after)
            row["goal_tradeoffs"].append({"goal": goal["id"], "property": key,
                "before": before, "isolated_if_fulfilled": after,
                "direction": "advances" if new < old else "setback" if new > old else "unchanged"})
        choices.append(row)
    return {"alternatives": choices,
            "recent_own_resolutions": [r for r in observation["own_requests"]
                if r.get("status") == "reviewed" and r["turn"] == observation["turn"] - 1],
            "remaining_turns": matrix["remaining_turns"],
            "reported_changes": matrix["reported_changes"],
            "basis": "Costs and isolated effects only. Pending commitment collisions, opposition, bounds and later changes can alter results.",
            "presentation": "Frame the choice around what is at risk, why it matters now, and what must be sacrificed. "
                "Explain at least two materially different feasible approaches when present, including deliberate restraint if relevant. "
                "Use recorded consequences and visible reports for the next scene; do not invent crises, guarantees, or hidden opponent intentions."}


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
        "goals": goals, "remaining_turns": support.get("remaining_turns", observation.get("matrix", {}).get("remaining_turns")),
        **({"matrix": observation["matrix"], "consequential_choices": matrix_choices(observation)} if "matrix" in observation else {}),
        **({"reserve_accounts": observation["reserve_accounts"]} if "reserve_accounts" in observation else {}),
        **({"stock_accounts": observation["stock_accounts"]} if "stock_accounts" in observation else {}),
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
