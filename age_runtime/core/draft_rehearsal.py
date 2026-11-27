"""Explicit source-independent rehearsal of self-contained unreviewed drafts."""
from copy import deepcopy
from pathlib import Path

from age_runtime.core.private_play import inventory, read, supported, start_selected, eligible_perspectives, verify
from age_runtime.core.participants import bind_factions
from age_runtime.core.source_compiler import checked_date
from age_runtime.core.runner import digest


def select_rehearsal(path, scenario_id):
    catalog = inventory(path)
    matches = [(g, e) for g in catalog["groups"] for e in g["scenarios"]
               if e["id"] == scenario_id]
    if len(matches) != 1:
        raise ValueError("scenario not found")
    group, entry = matches[0]
    if entry["status"] != "draft-unreviewed":
        raise ValueError("rehearsal requires unreviewed draft")
    if any(k in entry for k in ("briefing_context", "image_map", "game_map",
                               "carry_from", "remember_from", "presets")):
        raise ValueError("rehearsal cannot resolve reviewed external context or variants")
    root = Path(path).resolve().parent
    spec_path = (root / entry["spec"]).resolve()
    if not spec_path.is_relative_to(root):
        raise ValueError("scenario path outside inventory")
    spec = read(spec_path)
    if (not {"version", "effective_date", "scenario", "initial_refs"} <= set(spec)
            or set(spec) - {"version", "effective_date", "scenario", "initial_refs",
                            "evidence_refs", "faction_profiles"}
            or type(spec["version"]) is not int or spec["version"] != 1):
        raise ValueError("invalid rehearsal specification")
    checked_date(spec["effective_date"])
    if spec["initial_refs"] != {}:
        raise ValueError("rehearsal requires self-contained initial values")
    scenario = deepcopy(spec["scenario"])
    if scenario["id"] != scenario_id or "phase_memory" in scenario:
        raise ValueError("invalid rehearsal identity or continuity")
    if any("faction_context" in a for a in scenario["actors"].values()):
        raise ValueError("prebound faction context not permitted")
    # Preserve authored literal profiles; do not pretend the source evidence
    # was resolved. Refuse numeric references rather than inventing values.
    profiles = deepcopy(spec.get("faction_profiles", {}))
    for profile in profiles.values():
        for record in profile["properties"].values():
            if "reference" in record:
                raise ValueError("rehearsal cannot resolve referenced property")
            record.pop("evidence", None)
    if profiles:
        bind_factions(scenario, profiles, {}, spec["effective_date"])
    supported(scenario)
    eligible_perspectives(entry, scenario)
    compiled = {"version": 1, "qualification": "unreviewed-rehearsal",
                "spec_digest": digest(spec), "scenario_digest": digest(scenario),
                "dependencies": {}, "scenario": scenario}
    return catalog, group, entry, spec, compiled


def start_rehearsal(path, scenario_id, actor, opportunity_latitude=None):
    return verify(start_selected(select_rehearsal(path, scenario_id), actor, {}, opportunity_latitude=opportunity_latitude))
