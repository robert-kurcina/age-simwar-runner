"""Scenario-authored hypothetical variants; never override referenced facts."""
from copy import deepcopy
import re
from age_runtime.core.runner import digest, validate


def options(entry):
    records = entry.get("presets", {})
    if not isinstance(records, dict) or "standard" in records:
        raise ValueError("invalid preset catalog")
    result = [{"id": "standard", "label": "Standard — configured baseline"}]
    for key, record in records.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
            raise ValueError("invalid preset ID")
        if not isinstance(record, dict) or set(record) != {
                "label", "reason", "base_spec_digest", "resources", "report_delays"}:
            raise ValueError("invalid preset fields")
        if any(not isinstance(record[k], str) or not record[k].strip()
               for k in ("label", "reason")):
            raise ValueError("preset label and rationale required")
        result.append({"id": key, "label": record["label"]})
    return result


def apply(entry, spec, compiled, preset):
    options(entry)
    if preset == "standard":
        return compiled, {"id": "standard", "label": "Standard — configured baseline"}
    if preset not in entry.get("presets", {}):
        raise ValueError("unknown scenario preset")
    record = entry["presets"][preset]
    if record["base_spec_digest"] != digest(spec):
        raise ValueError("preset base specification changed")
    result = deepcopy(compiled)
    s = result["scenario"]
    resource = "aid_packages" if s.get("community_assistance") else "restoration_credits"
    resources, delays = record["resources"], record["report_delays"]
    if not isinstance(resources, dict) or not isinstance(delays, dict):
        raise ValueError("invalid preset maps")
    changes = {}
    for key, value in resources.items():
        if (key != resource or key not in spec["scenario"]["initial"]
                or key in compiled["dependencies"] or type(value) is not int or value < 0):
            raise ValueError("only illustrative civilian resource budgets may vary")
        changes[key] = {"baseline": s["initial"][key], "variant": value}
        s["initial"][key] = value
    for actor, fields in delays.items():
        if actor not in s.get("actors", {}) or not isinstance(fields, dict):
            raise ValueError("invalid preset actor")
        profile = s["actors"][actor]
        for key, value in fields.items():
            if (key not in profile.get("visible_keys", []) or type(value) is not int
                    or not 0 <= value <= s["end_minute"]):
                raise ValueError("invalid preset reporting delay")
            profile.setdefault("report_delay_minutes", {})[key] = value
    validate(s)
    result["base_scenario_digest"] = compiled["scenario_digest"]
    result["scenario_digest"] = digest(s)
    result["preset_digest"] = digest(record)
    result["preset_changes"] = {"resources": changes, "report_delays": deepcopy(delays)}
    return result, {"id": preset, "label": record["label"], "reason": record["reason"],
                    "classification": "hypothetical", "digest": digest(record)}
