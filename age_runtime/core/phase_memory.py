"""Historical actor-local carry, not live authority or accounting."""
from copy import deepcopy
from datetime import timedelta

KINDS = ("communications", "propositions", "established_context", "developments",
         "proposals", "agreements", "diplomatic_history")


def validate(s):
    if "phase_memory" not in s:
        return
    memory = s["phase_memory"]
    if not isinstance(memory, dict) or not memory or set(memory) - set(s.get("actors", {})):
        raise ValueError("invalid phase memory audience")
    from age_runtime.core.source_compiler import checked_date
    for entries in memory.values():
        if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
            raise ValueError("invalid phase memory record count")
        seen = set()
        for entry in entries:
            if (not isinstance(entry, dict) or set(entry) !=
                    {"kind", "id", "source_scenario", "source_date", "source_minute", "record"}
                    or entry["kind"] not in KINDS
                    or not isinstance(entry["id"], str) or not entry["id"]
                    or not isinstance(entry["source_scenario"], str) or not entry["source_scenario"]
                    or type(entry["source_minute"]) is not int or entry["source_minute"] < 0
                    or not isinstance(entry["record"], dict)):
                raise ValueError("invalid historical memory record")
            checked_date(entry["source_date"])
            key = (entry["source_scenario"], entry["kind"], entry["id"])
            if key in seen:
                raise ValueError("duplicate historical memory identity")
            seen.add(key)


def view(s, actor):
    return deepcopy(s.get("phase_memory", {}).get(actor, []))


def derive(catalog, entry, spec, compiled, previous):
    from age_runtime.core.private_play import verify
    from age_runtime.core.runner import digest, validate as validate_scenario
    from age_runtime.core.source_compiler import checked_date
    from age_runtime.core.observations import observe
    from age_runtime.core.institutional_memory import recall
    verify(previous)
    h = previous["header"]
    source, state = h["compiled"]["scenario"], previous["state"]
    target = compiled["scenario"]
    rule = entry.get("remember_from")
    if (not isinstance(rule, dict) or set(rule) !=
            {"scenario", "source_spec_digest", "target_spec_digest", "reason", "actors"}
            or rule["scenario"] != source["id"] or source["id"] == target["id"]
            or not isinstance(rule["reason"], str) or not rule["reason"].strip()
            or rule["source_spec_digest"] != h["compiled"]["spec_digest"]
            or rule["target_spec_digest"] != compiled["spec_digest"]
            or h["campaign"] != catalog["id"] or h["catalog_digest"] != digest(catalog)
            or state["minute"] != source["end_minute"]
            or "phase_memory" in target):
        raise ValueError("no approved historical continuity mapping")
    end = checked_date(h["effective_date"]) + timedelta(days=(state["minute"] + 1439) // 1440)
    if checked_date(spec["effective_date"]) < end:
        raise ValueError("target starts before source completion")
    actors = rule["actors"]
    if not isinstance(actors, dict) or not actors:
        raise ValueError("historical carry requires explicit actors")
    result = {}
    for actor, selectors in actors.items():
        if (actor not in source.get("actors", {}) or actor not in target.get("actors", {})
                or source["actors"][actor]["label"] != target["actors"][actor]["label"]
                or not isinstance(selectors, list) or not 1 <= len(selectors) <= 64):
            raise ValueError("historical carry requires stable approved actor identity")
        history = recall(observe(source, state, actor))
        records = []
        for selector in selectors:
            if (not isinstance(selector, dict) or set(selector) != {"kind", "id"}
                    or selector["kind"] not in KINDS
                    or not isinstance(selector["id"], str)):
                raise ValueError("invalid historical selector")
            kind, rid = selector["kind"], selector["id"]
            group = history.get(kind, {})
            if isinstance(group, list):
                record = next((item for item in group if item["id"] == rid), None)
            else:
                record = group.get(rid)
            if record is None:
                raise ValueError("historical record not accessible to actor")
            records.append({"kind": kind, "id": rid, "source_scenario": source["id"],
                            "source_date": h["effective_date"], "source_minute": state["minute"],
                            "record": deepcopy(record)})
        result[actor] = records
    scenario = {**deepcopy(target), "phase_memory": result}
    validate_scenario(scenario)
    snapshot = {**deepcopy(compiled), "scenario": scenario, "scenario_digest": digest(scenario)}
    link = {"version": 1, "classification": "historical_session_memory",
            "source_id": source["id"], "source_session_digest": digest(previous),
            "source_checkpoint_digest": digest(state), "mapping_digest": digest(rule),
            "target_template_digest": compiled["scenario_digest"],
            "target_scenario_digest": snapshot["scenario_digest"],
            "memory_digest": digest(result)}
    return snapshot, link


def verify_record(compiled, link):
    from age_runtime.core.runner import digest
    if (not isinstance(link, dict) or link.get("version") != 1
            or link.get("classification") != "historical_session_memory"
            or link.get("target_scenario_digest") != compiled["scenario_digest"]
            or "phase_memory" not in compiled["scenario"]
            or link.get("memory_digest") != digest(compiled["scenario"]["phase_memory"])):
        raise ValueError("historical continuity record mismatch")
    if any(entry["source_scenario"] != link.get("source_id")
           for entries in compiled["scenario"]["phase_memory"].values() for entry in entries):
        raise ValueError("historical source identity mismatch")
