"""Read-only readiness report for strategic scenario preparation."""
import argparse
import json
from pathlib import Path

from age_runtime.core.private_play import inventory, select, start_selected, eligible_perspectives, verify, supported, read
from age_runtime.core.draft_rehearsal import select_rehearsal
from age_runtime.core.resource_acquisition import requirements
from age_runtime.core.source_compiler import compile_scenario, read_pinned_source
from age_runtime.core.runner import digest
from age_runtime.core.participants import compile_profile
from copy import deepcopy

ERRORS = (ValueError, TypeError, KeyError, OSError)


def check_openings(selection, owners):
    entry, scenario = selection[2], selection[4]["scenario"]
    perspectives = eligible_perspectives(entry, scenario)
    if not perspectives:
        raise ValueError("no eligible human perspectives")
    results = []
    for actor in perspectives:
        try:
            verify(start_selected(selection, actor, owners,
                                  shared=bool(scenario.get("civic_agreement"))))
        except ERRORS as exc:
            results.append({"actor": actor, "status": "blocked", "reason": str(exc)})
        else:
            results.append({"actor": actor, "status": "verified-opening"})
    return results


def roster_review(spec, entry, owners=None):
    """Author-facing diagnostics only; profiles remain opening context."""
    scenario = spec["scenario"]
    profiles = spec.get("faction_profiles", {})
    actors = scenario["actors"]
    eligible = eligible_perspectives(entry, scenario)
    rows = []
    for ident, actor in actors.items():
        profile = profiles.get(ident)
        row = {"id": ident, "label": actor["label"],
               "profile_present": ident in profiles,
               "selectable": ident in eligible,
               "default_role": "model" if ident in scenario.get("model_factions", []) else "human",
               "objectives": list(actor.get("objectives", {})),
               "strategy_present": "strategy" in actor,
               "profile_status": "absent", "unresolved_properties": [],
               "referenced_properties": [], "hypothetical_properties": []}
        if ident in profiles:
            try:
                if (not isinstance(profile, dict) or profile.get("id") != ident
                        or profile.get("label") != actor["label"]
                        or profile.get("effective_date") != spec["effective_date"]
                        or profile.get("kind") != "organization"):
                    raise ValueError("faction identity, label, kind or date mismatch")
                candidate = deepcopy(profile)
                for key, record in candidate["properties"].items():
                    if "reference" in record:
                        row["referenced_properties"].append(key)
                    elif record.get("classification") == "unresolved":
                        row["unresolved_properties"].append(key)
                    elif record.get("classification") == "hypothetical":
                        row["hypothetical_properties"].append(key)
                    if owners is None:
                        record.pop("evidence", None)
                if owners is None and row["referenced_properties"]:
                    row["profile_status"] = "requires-source-check"
                else:
                    compile_profile(candidate, owners if owners is not None else {})
                    row["profile_status"] = "compiled" if owners is not None else "literal-checked"
            except ERRORS:
                row["profile_status"] = "blocked"
        rows.append(row)
    return {"actors": rows, "unbound_profiles": sorted(set(profiles) - set(actors)),
            "eligible_perspectives": eligible,
            "review_notes": ["Missing optional profiles are not mechanical failures.",
                             "Unresolved context is not a numeric resource or permission.",
                             "Check motives, authority and dated assumptions before author approval."]}


def prepare(path, owners=None):
    """Report independent preparation gates; never promote or write a catalog."""
    catalog = inventory(path)
    root = Path(path).resolve().parent
    resources = []
    resource_error = None
    try:
        manifest = requirements(path)
        for item in manifest["resources"]:
            result = {**item, "status": "not-checked"}
            if owners is not None:
                try:
                    raw = read_pinned_source(owners, item["owner"], item["revision"], item["path"])
                except ERRORS:
                    # Do not echo source-reader exceptions that may include local paths.
                    result["status"] = "unavailable-or-invalid"
                else:
                    result.update(status="bytes-verified", bytes=len(raw))
            resources.append(result)
    except ERRORS as exc:
        resource_error = str(exc)
    results = []
    for group in catalog["groups"]:
        for entry in group["scenarios"]:
            sid = entry["id"]
            result = {"id": sid, "group": group["id"], "catalog_status": entry["status"],
                      "author_review": "not-assessed", "roster": [], "checks": {}}
            checks = result["checks"]
            if entry["status"] == "draft-unreviewed":
                result["author_review"] = "pending"
            try:
                spec_path = (root / entry["spec"]).resolve()
                if not spec_path.is_relative_to(root):
                    raise ValueError("scenario path outside inventory")
                spec = read(spec_path)
                scenario = spec["scenario"]
                if scenario["id"] != sid:
                    raise ValueError("scenario identity mismatch")
                result["roster"] = [{"id": a, "label": record["label"],
                                     "profile_present": a in spec.get("faction_profiles", {})}
                                    for a, record in scenario["actors"].items()]
                checks["specification"] = {"status": "read", "digest": digest(spec)}
            except ERRORS as exc:
                checks["specification"] = {"status": "blocked", "reason": str(exc)}
                results.append(result)
                continue
            try:
                result["roster_review"] = roster_review(spec, entry, owners)
            except ERRORS:
                result["roster_review"] = {"status": "blocked", "reason": "Invalid roster or perspective configuration."}
            if entry["status"] == "draft-unreviewed":
                try:
                    selection = select_rehearsal(path, sid)
                    openings = check_openings(selection, {})
                    checks["rehearsal"] = {"status": "passed" if all(
                        o["status"] == "verified-opening" for o in openings) else "blocked",
                        "perspectives": openings}
                except ERRORS as exc:
                    checks["rehearsal"] = {"status": "blocked", "reason": str(exc)}
            else:
                checks["rehearsal"] = {"status": "not-applicable"}
            checks["compilation"] = {"status": "not-checked"}
            checks["reviewed_openings"] = {"status": "not-checked"}
            if owners is not None:
                try:
                    compiled = compile_scenario(spec, owners)
                    supported(compiled["scenario"])
                    perspectives = eligible_perspectives(entry, compiled["scenario"])
                    if not perspectives:
                        raise ValueError("no eligible human perspectives")
                    checks["compilation"] = {"status": "passed",
                        "scenario_digest": compiled["scenario_digest"], "perspectives": perspectives}
                except ERRORS:
                    checks["compilation"] = {"status": "blocked",
                        "reason": "Existing compiler or mechanical validation rejected specification; run draft compiler for details."}
                if entry["status"] in ("verified-illustrative-pilot", "reviewed-illustrative"):
                    try:
                        selection = select(path, sid, owners)
                        openings = check_openings(selection, owners)
                        checks["reviewed_openings"] = {"status": "passed" if all(
                            o["status"] == "verified-opening" for o in openings) else "blocked",
                            "perspectives": openings}
                    except ERRORS:
                        checks["reviewed_openings"] = {"status": "blocked",
                            "reason": "Existing reviewed selection or opening validation rejected scenario."}
            result["resource_count"] = sum(any(u["scenario"] == sid for u in item["uses"])
                                           for item in resources) if resource_error is None else None
            results.append(result)
    return {"version": 1, "inventory_digest": digest(catalog), "resources": resources,
            "resource_discovery_error": resource_error, "results": results,
            "catalog_only_groups": [g["id"] for g in catalog["groups"] if not g["scenarios"]],
            "qualification": "Preparation diagnostics only; opening checks are not full gameplay or author review."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--owners", type=Path)
    args = parser.parse_args()
    try:
        owners = read(args.owners) if args.owners else None
        if owners is not None and not isinstance(owners, dict):
            raise ValueError("owners must be an object")
        report = prepare(args.inventory, owners)
    except ERRORS as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
