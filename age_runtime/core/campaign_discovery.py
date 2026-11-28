"""Read-only campaign selection menu; no private faction context or referee values."""
from age_runtime.core.private_play import inventory, select, eligible_perspectives, start_selected, verify
from age_runtime.core.draft_rehearsal import select_rehearsal
from age_runtime.core.opportunity_latitude import DEFAULT, validate


def discover(path, owners=None):
    catalog = inventory(path)
    groups = []
    for group in catalog["groups"]:
        episodes = []
        for entry in group["scenarios"]:
            item = {"id": entry["id"], "title": entry["title"],
                    "catalog_status": entry["status"], "play_mode": None,
                    "availability": "catalog-only", "perspectives": []}
            try:
                if entry["status"] == "draft-unreviewed":
                    selection = select_rehearsal(path, entry["id"])
                    mode = "rehearse"
                    source_owners = {}
                elif (entry["status"] in ("verified-illustrative-pilot", "reviewed-illustrative")
                      and group["status"] == "supported-pilot"):
                    if owners is None:
                        item["availability"] = "requires-authorized-sources"
                        episodes.append(item)
                        continue
                    selection = select(path, entry["id"], owners)
                    mode = "start"
                    source_owners = owners
                else:
                    episodes.append(item)
                    continue
                spec, scenario = selection[3], selection[4]["scenario"]
                item["effective_date"] = spec["effective_date"]
                item["turn_minutes"] = scenario["turn_minutes"]
                item["turns"] = (scenario["end_minute"] + scenario["turn_minutes"] - 1) // scenario["turn_minutes"]
                item["opportunity_latitude"] = validate(entry.get("opportunity_latitude", DEFAULT))
                item["play_mode"] = mode
                shared = bool(scenario.get("civic_agreement"))
                item["shared_required"] = shared
                for actor in eligible_perspectives(entry, scenario):
                    try:
                        verify(start_selected(selection, actor, source_owners, shared=shared))
                    except (ValueError, TypeError, KeyError, OSError):
                        continue
                    item["perspectives"].append({"id": actor, "label": scenario["actors"][actor]["label"]})
                item["availability"] = "available" if item["perspectives"] else "blocked"
                if item["availability"] == "blocked":
                    item["play_mode"] = None
            except (ValueError, TypeError, KeyError, OSError):
                item["availability"] = "blocked"
                item["play_mode"] = None
                item["perspectives"] = []
            episodes.append(item)
        groups.append({"id": group["id"], "title": group["title"], "status": group["status"],
                       "episodes": episodes})
    return {"id": catalog["id"], "title": catalog["title"], "groups": groups,
            "guidance": "Choose an available episode and perspective. Rehearse is explicitly unreviewed; start uses reviewed registration. Openings are fresh and standard; continuity is separate."}


def progression(path, previous):
    """Player-facing next episode choices, never an automatic transition."""
    from age_runtime.core.private_play import view
    from age_runtime.core.runner import digest
    from age_runtime.core.transition_preview import transition_preview
    from age_runtime.core.source_compiler import checked_date
    from datetime import timedelta

    current = view(previous)
    header = previous["header"]
    catalog = inventory(path)
    if header["campaign"] != catalog["id"] or header["catalog_digest"] != digest(catalog):
        raise ValueError("campaign revision mismatch")
    scenario = header["compiled"]["scenario"]
    actor = header["actor"]
    observation = current["observation"]
    result = {"campaign": catalog["id"], "source": scenario["id"], "actor": actor,
              "source_session_digest": digest(previous), "complete": current["complete"],
              "qualification": current.get("qualification", "reviewed"),
              "prior_objectives": observation.get("objective_outcomes", {}),
              "retained_history": [{k: row[k] for k in ("kind", "id", "source_scenario", "source_date")}
                                   for row in observation.get("phase_memory", [])],
              "choices": []}
    if not current["complete"]:
        result["guidance"] = "Finish the current episode before choosing a continuation."
        return result
    end = checked_date(header["effective_date"]) + timedelta(days=(scenario["end_minute"] + 1439) // 1440)
    menu = discover(path)
    for group in menu["groups"]:
        for episode in group["episodes"]:
            if (episode["availability"] != "available" or episode["play_mode"] != "rehearse"
                    or episode["id"] == scenario["id"]
                    or checked_date(episode["effective_date"]) < end):
                continue
            row = {"id": episode["id"], "title": episode["title"],
                   "effective_date": episode["effective_date"], "turns": episode["turns"],
                   "fresh_perspectives": episode["perspectives"],
                   "continuation": "unavailable", "historical_candidates": 0}
            try:
                preview = transition_preview(path, previous, episode["id"])
            except (ValueError, TypeError, KeyError, OSError):
                pass
            else:
                count = len(preview["candidate_selectors"])
                row["historical_candidates"] = count
                row["continuation"] = "select-history" if count else "no-selectable-history"
                row["gap_days"] = preview["gap_days"]
            result["choices"].append(row)
    result["guidance"] = ("Choose a fresh draft opening or explicitly preview and confirm selected historical memory. "
                          "Fresh openings do not inherit records. No automatic phase advance, live obligation or resource carry.")
    return result


def bundled_catalog(root=None):
    """Discover explicitly tracked strategic rehearsal inventories, not private files."""
    from pathlib import Path
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    entries = ("scenarios/sh44ser/conflagration/inventory.json",
               "scenarios/sh44ser/production-accord/inventory.json")
    result = []
    for relative in entries:
        menu = discover(root / relative)
        episodes = [e for g in menu["groups"] for e in g["episodes"]
                    if e["availability"] == "available" and e["play_mode"] == "rehearse"]
        result.append({"id": menu["id"], "title": menu["title"], "inventory": relative,
                       "qualification": "unreviewed-rehearsal", "episodes": episodes})
    from age_runtime.core.great_war import discovery
    result.append(discovery(root))
    return result
