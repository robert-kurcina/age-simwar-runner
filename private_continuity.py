"""Explicit, referee-approved private civilian continuity; no implicit transfers."""
from copy import deepcopy
from datetime import timedelta
from continuity import transfer_values
from runner import digest
from source_compiler import checked_date


def derive(catalog, entry, spec, compiled, previous):
    from private_play import verify
    verify(previous)
    h = previous["header"]
    source = h["compiled"]["scenario"]
    target = compiled["scenario"]
    if h["campaign"] != catalog["id"] or h["catalog_digest"] != digest(catalog):
        raise ValueError("campaign revision mismatch")
    rule = entry.get("carry_from")
    if (not isinstance(rule, dict) or set(rule) != {"scenario", "variables", "reason"}
            or rule["scenario"] != source["id"] or source["id"] == target["id"]
            or not isinstance(rule["reason"], str) or not rule["reason"].strip()):
        raise ValueError("no approved private continuity mapping")
    # Only carry complete, same-unit civilian accounting pairs. Never carry
    # consent, map dissimilar resources, or reset half of a finite ledger.
    keys = set(source["initial"])
    eligible = ({"households_assisted", "aid_packages"},
                {"open_service_centers", "restoration_credits"})
    if (keys not in eligible or keys != set(target["initial"])
            or rule["variables"] != {k: k for k in keys}
            or keys & set(compiled["dependencies"])):
        raise ValueError("continuity requires a complete same-unit civilian accounting pair")
    if source.get("assistance_capacity") != target.get("assistance_capacity"):
        raise ValueError("continuity requires the same assistance catchment assumptions")
    if source.get("community_assistance") != target.get("community_assistance") or source.get("service_restoration") != target.get("service_restoration"):
        raise ValueError("continuity mechanics mismatch")
    end_date = checked_date(h["effective_date"]) + timedelta(days=(source["end_minute"] + 1439) // 1440)
    if checked_date(spec["effective_date"]) < end_date:
        raise ValueError("target begins before source completion")
    result, transferred = transfer_values(source, previous["state"], target, rule["variables"])
    link = {"version": 1, "source_id": source["id"],
            "source_session_digest": digest(previous),
            "source_checkpoint_digest": digest(previous["state"]),
            "target_template_digest": compiled["scenario_digest"],
            "target_scenario_digest": digest(result),
            "mapping_digest": digest(rule), "transferred": transferred,
            "classification": "derived_session_outcome"}
    snapshot = deepcopy(compiled)
    snapshot["scenario"] = result
    snapshot["scenario_digest"] = digest(result)
    return snapshot, link


def verify_record(compiled, link):
    """Local structural check; full source replay requires the source session."""
    if (not isinstance(link, dict) or link.get("version") != 1
            or link.get("classification") != "derived_session_outcome"
            or link.get("target_scenario_digest") != compiled["scenario_digest"]):
        raise ValueError("continuity record mismatch")
    initial = compiled["scenario"]["initial"]
    records = link.get("transferred")
    if not isinstance(records, dict) or set(records) != set(initial):
        raise ValueError("continuity record keys mismatch")
    for k, v in records.items():
        if v != {"source_key": k, "value": initial[k]}:
            raise ValueError("continuity record value mismatch")
