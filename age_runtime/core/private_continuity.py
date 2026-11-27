"""Explicit, referee-approved private civilian continuity; no implicit transfers."""
from copy import deepcopy
from datetime import timedelta
from age_runtime.core.continuity import transfer_values
from age_runtime.core.runner import digest
from age_runtime.core.source_compiler import checked_date



def economy_signature(s):
    """Conservative continuation: same projects, owners, units and accounting."""
    projects = {p["id"]: p for p in s["economy_projects"]}
    from age_runtime.core.actions import stock_owners
    stocks = stock_owners(s)
    keys = set(stocks)
    for p in projects.values():
        keys.update(p[k] for k in ("progress", "delay", "complications"))
        keys.update(a["key"] for a in p["axes"])
    return keys, projects, stocks, s["capacity_actions"], s.get("resource_transfers", {}), s.get("funding_reserves", {})


def continuity_keys(source, target):
    if "economy_projects" in source or "economy_projects" in target:
        if "economy_projects" not in source or "economy_projects" not in target:
            raise ValueError("continuity mechanics mismatch")
        a, b = economy_signature(source), economy_signature(target)
        if a != b or set(source["actors"]) != set(target["actors"]):
            raise ValueError("continuity requires identical project accounting and stock owners")
        if any(source["actors"][k]["label"] != target["actors"][k]["label"] for k in source["actors"]):
            raise ValueError("continuity requires stable faction identities")
        if a[0] != set(source["initial"]) or a[0] != set(target["initial"]):
            raise ValueError("continuity requires complete project accounting only")
        return a[0]
    keys = set(source["initial"])
    eligible = ({"households_assisted", "aid_packages"},
                {"open_service_centers", "restoration_credits"})
    if keys not in eligible or keys != set(target["initial"]):
        raise ValueError("continuity requires a complete same-unit civilian accounting pair")
    return keys


def derive(catalog, entry, spec, compiled, previous):
    from age_runtime.core.private_play import verify
    verify(previous)
    h = previous["header"]
    source = h["compiled"]["scenario"]
    target = compiled["scenario"]
    if h["campaign"] != catalog["id"] or h["catalog_digest"] != digest(catalog):
        raise ValueError("campaign revision mismatch")
    rule = entry.get("carry_from")
    if (not isinstance(rule, dict) or set(rule) != {"scenario", "variables", "reason", "source_spec_digest", "target_spec_digest"}
            or rule["scenario"] != source["id"] or source["id"] == target["id"]
            or not isinstance(rule["reason"], str) or not rule["reason"].strip()):
        raise ValueError("no approved private continuity mapping")
    if (rule["source_spec_digest"] != h["compiled"]["spec_digest"]
            or rule["target_spec_digest"] != compiled["spec_digest"]):
        raise ValueError("continuity specification revision mismatch")
    # Carry complete accounting sets, never orders, consent or arbitrary keys.
    keys = continuity_keys(source, target)
    if rule["variables"] != {k: k for k in keys} or keys & set(compiled["dependencies"]):
        raise ValueError("continuity requires complete literal same-unit accounting")
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
