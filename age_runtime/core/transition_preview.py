"""Read-only historical transition preparation; no automatic carry or approval."""
from datetime import timedelta
from copy import deepcopy

from age_runtime.core.private_play import verify, inventory, view, eligible_perspectives
from age_runtime.core.draft_rehearsal import select_rehearsal
from age_runtime.core.phase_memory import KINDS, derive
from age_runtime.core.institutional_memory import recall
from age_runtime.core.source_compiler import checked_date
from age_runtime.core.runner import digest


def transition_preview(path, previous, target_id, selectors=None):
    """Preview only the current human faction's accessible historical records.

    Explicit selectors can be mechanically checked against the existing
    historical carry contract, but neither preview nor rehearsal approves
    identities, relevance or a reviewed continuation.
    """
    verify(previous)
    h = previous["header"]
    catalog = inventory(path)
    source = h["compiled"]["scenario"]
    actor = h["actor"]
    if h["campaign"] != catalog["id"] or h["catalog_digest"] != digest(catalog):
        raise ValueError("campaign revision mismatch")
    if previous["state"]["minute"] != source["end_minute"]:
        raise ValueError("source episode must be complete")
    if h.get("shared"):
        raise ValueError("single-perspective transition preview required")
    if h["compiled"].get("qualification") != "unreviewed-rehearsal":
        raise ValueError("preview currently supports draft rehearsal sources only")
    _, _, entry, spec, compiled = select_rehearsal(path, target_id)
    target = compiled["scenario"]
    if target_id == source["id"]:
        raise ValueError("select a different target episode")
    end = checked_date(h["effective_date"]) + timedelta(days=(source["end_minute"] + 1439) // 1440)
    opening = checked_date(spec["effective_date"])
    if opening < end:
        raise ValueError("target starts before source completion")
    if (actor not in eligible_perspectives(entry, target)
            or target["actors"][actor]["label"] != source["actors"][actor]["label"]):
        raise ValueError("same eligible faction identity required")
    history = recall(view(previous)["observation"])
    candidates = []
    for kind in KINDS:
        group = history.get(kind, {})
        ids = [record["id"] for record in group] if isinstance(group, list) else list(group)
        candidates.extend({"kind": kind, "id": ident} for ident in sorted(ids))
    records = []
    rule = None
    if selectors is not None:
        rule = {"scenario": source["id"], "source_spec_digest": h["compiled"]["spec_digest"],
                "target_spec_digest": compiled["spec_digest"],
                "reason": "Unapproved transition preview; review relevance and dated identity.",
                "actors": {actor: deepcopy(selectors)}}
        snapshot, _ = derive(catalog, {**entry, "remember_from": rule}, spec, compiled, previous)
        records = snapshot["scenario"]["phase_memory"][actor]
    return {"status": "unreviewed-preview", "source": source["id"], "target": target_id,
            "actor": actor, "source_session_digest": digest(previous),
            "source_completion_date": end.isoformat(), "target_opening_date": opening.isoformat(),
            "gap_days": (opening - end).days, "candidate_selectors": candidates,
            "selected_history": records, "proposed_mapping": rule,
            "prior_objectives": view(previous)["observation"].get("objective_outcomes", {}),
            "authority": "None; historical records only. No resources, live commitments, or current knowledge carried.",
            "approved": False, "registered": False}
