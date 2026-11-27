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
