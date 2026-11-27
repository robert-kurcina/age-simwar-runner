"""Read-only institutional recall from an already actor-scoped observation.

No raw referee checkpoint, new truth store, or semantic inference.
"""
from copy import deepcopy


def recall(observation, counterpart=None):
    """Return durable, scoped records; counterpart filtering is exact identity."""
    actor = observation["actor"]
    if counterpart is not None and (not isinstance(counterpart, str) or not counterpart or counterpart == actor):
        raise ValueError("invalid counterpart")
    communications = observation.get("communications", [])
    proposals = observation.get("negotiation", {}).get("proposals", [])
    support = observation.get("strategic_support", {})
    own_requests = observation.get("own_requests", [])
    if counterpart is not None:
        communications = [c for c in communications
                          if counterpart == c["speaker"] or counterpart in c["recipients"]]
        proposals = [p for p in proposals
                     if counterpart in (p["proposer"], p["recipient"])]
        # Authored agreement projection contains consenting actors but does
        # not identify every unsigned party; do not guess counterpart scope.
        claim_ids = {c["id"] for c in communications}
        propositions = {pid: p for pid, p in observation.get("propositions", {}).items()
                        if any(source.get("id") in claim_ids for source in p["sources"])}
        return deepcopy({"actor": actor, "counterpart": counterpart, "turn": observation["turn"],
                         "minute": observation["minute"], "communications": communications,
                         "proposals": proposals, "propositions": propositions,
                         "scope_note": "Counterpart-linked records only; consult full recall for own decisions, authored agreements and other matters."})
    agreements = support.get("agreements", {})
    active = {"proposed", "committed", "awaiting_consent"}
    due = [{"kind": "negotiation", "id": p["id"], "status": p["status"],
            "due_minute": p["due_minute"]}
           for p in proposals if p["status"] in active]
    due.extend({"kind": "agreement", "id": aid, "status": a["status"],
                "due_minute": a["due_minute"]}
               for aid, a in agreements.items() if a["status"] in active)
    due.sort(key=lambda d: (d["due_minute"], d["kind"], d["id"]))
    return deepcopy({
        "actor": actor, "turn": observation["turn"], "minute": observation["minute"],
        "objectives": observation["objectives"],
        "reports": observation["reports"],
        "communications": communications,
        "propositions": observation.get("propositions", {}),
        "proposals": proposals,
        "agreements": agreements,
        "outstanding_deadlines": due,
        "decisions": [r for r in own_requests if r.get("origin") == "critical_decision"],
        "own_requests": own_requests,
        "project_results": observation.get("project_results", []),
        "project_assessments": support.get("project_assessments", []),
        "available_requests": observation["available_requests"],
        "scope_note": "Recorded actor-visible information, not a complete transcript. Claims are not proof; reports may be stale; available requests are not guaranteed feasible."
    })


def reminder_index(observation):
    """Compact references, not a second copy of history or a relevance score."""
    history = recall(observation)
    communications = history["communications"]
    propositions = history["propositions"]
    decisions = history["decisions"]
    return {
        "outstanding_deadlines": history["outstanding_deadlines"],
        "recent_claim_ids": [c["id"] for c in communications[-5:]],
        "unsettled_proposition_ids": [pid for pid, p in propositions.items()
                                     if p["latest_stance"] in ("unstated", "unknown", "doubts")],
        "recent_decision_ids": [d["decision_id"] for d in decisions[-3:]],
        "stale_or_unknown_report_keys": [key for key, report in history["reports"].items()
                                         if report["status"] in ("stale", "unknown")],
        "recall_instruction": "Before consequential decisions, retrieve relevant earlier claims, conditions, decisions and evidence even when old. This index is not exhaustive."
    }
