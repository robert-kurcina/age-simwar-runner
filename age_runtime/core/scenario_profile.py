"""Common descriptive profile of existing scenarios, not a new rules engine."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def profile(campaign_id, scenario_id):
    # Resolve only known catalog IDs, never user-supplied filesystem paths.
    for path in sorted((ROOT / "campaigns").glob("*/campaign.json")):
        manifest = read(path)
        if manifest["id"] != campaign_id:
            continue
        framework = manifest.get("framework", "strategic")
        if framework == "mythos":
            entries = manifest["scenarios"]
        elif framework == "strategic":
            entries = [s for g in manifest["groups"] for s in g["scenarios"]]
        else:
            raise ValueError("unsupported framework")
        entry = next((s for s in entries if s["id"] == scenario_id), None)
        if entry is None:
            break
        data = read(path.parent / entry["file"])
        result = {"version": 1, "campaign": campaign_id, "id": scenario_id,
                  "title": entry["title"], "framework": framework}
        if framework == "mythos":
            status = entry["status"]
            result.update(scale="personal", presentation="narrative",
                          status=status, perspectives=["protagonist"])
            if status == "trial":
                rules = read(path.parent / entry["rules"])
                result["duration"] = {"clock": "action-dependent",
                                      **({"target_spotlights": rules["pacing"]["target_spotlights"],
                                          "spotlight_budget_advisory": True} if "pacing" in rules
                                         else {"max_turns": rules["max_turns"]}),
                                      "start": rules["start"], "end": rules["end"]}
                result["conclusion"] = {"mode": "epilogue",
                    "metrics": ["Truth Preserved", "Self Preserved", "Horror Contained"],
                    "early_termination": True}
            else:
                result["duration"] = None
                result["conclusion"] = None
        else:
            minutes = data["turn_minutes"]
            end = data["end_minute"]
            result.update(scale={"Municipal":"local", "Regional":"operational",
                                 "Intermunicipal":"operational"}.get(entry.get("scope"), "strategic"),
                          status="existing", presentation="staff-briefing",
                          perspectives=sorted(data.get("actors", {})),
                          duration={"clock":"fixed-interval", "turn_minutes":minutes,
                                    "max_turns":(end + minutes - 1)//minutes,
                                    "end_minute":end},
                          conclusion={"mode":"objective-assessment", "early_termination":False,
                                      "metrics_by_actor":{k:sorted(v.get("objectives", {}))
                                                          for k,v in data.get("actors", {}).items()}})
        return result
    raise ValueError("unknown campaign or scenario")
