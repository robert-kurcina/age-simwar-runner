"""Referee-directed continuity between supported synthetic civilian scenarios."""
import argparse
import copy
import json
from pathlib import Path
from campaign import load_campaign
from runner import digest, initialize, validate, verify_checkpoint, save


def transfer_values(source_scenario, source_state, target, variables):
    """Apply a caller-approved mapping to a detached target template."""
    verify_checkpoint(source_scenario, source_state)
    if source_state["minute"] != source_scenario["end_minute"]:
        raise ValueError("continuity requires a completed session")
    result = copy.deepcopy(target)
    transferred = {}
    for dest, src in variables.items():
        value = source_state["values"][src]
        if dest not in result["initial"]:
            raise ValueError("unknown target continuity variable")
        result["initial"][dest] = value
        transferred[dest] = {"source_key": src, "value": value}
    validate(result)
    return result, transferred


def export_transition(manifest, source_scenario, source_state, target_id):
    manifest = Path(manifest).resolve()
    catalog = load_campaign(manifest)
    entries = {e["id"]: e for g in catalog["groups"] for e in g["scenarios"]}
    if target_id not in entries:
        raise ValueError("unknown target scenario")
    entry = entries[target_id]
    rule = entry.get("carry_from")
    if not rule or rule["scenario"] != source_scenario.get("id"):
        raise ValueError("no approved continuity mapping")
    template = json.loads((manifest.parent / entries[rule["scenario"]]["file"]).read_text())
    if {k: v for k, v in template.items() if k != "initial"} != {
            k: v for k, v in source_scenario.items() if k != "initial"}:
        raise ValueError("source scenario rules differ from catalog")
    if set(template["initial"]) != set(source_scenario["initial"]):
        raise ValueError("source initial keys differ from catalog")
    allowed = set(entries[rule["scenario"]].get("carry_from", {}).get("variables", {}))
    if any(v != template["initial"][k] and k not in allowed
           for k, v in source_scenario["initial"].items()):
        raise ValueError("source initial changes outside approved mapping")
    target = json.loads((manifest.parent / entry["file"]).read_text())
    result, transferred = transfer_values(source_scenario, source_state, target, rule["variables"])
    return {"version": 1, "campaign": catalog["id"], "catalog_digest": digest(catalog),
            "source_id": source_scenario["id"], "source_scenario_digest": digest(source_scenario),
            "source_checkpoint_digest": digest(source_state), "target_template_digest": digest(target),
            "target_scenario_digest": digest(result), "transferred": transferred,
            "scenario": result}


def verify_transition(manifest, source_scenario, source_state, transition):
    if not isinstance(transition, dict) or not isinstance(transition.get("scenario"), dict):
        raise ValueError("invalid transition")
    expected = export_transition(manifest, source_scenario, source_state,
                                 transition["scenario"].get("id"))
    if digest(expected) != digest(transition):
        raise ValueError("transition differs from verified source and mapping")
    return initialize(expected["scenario"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "source_scenario", "source_checkpoint"):
        parser.add_argument(name, type=Path)
    parser.add_argument("target_id")
    parser.add_argument("output", type=Path, help="New transition provenance JSON")
    parser.add_argument("scenario_output", type=Path, help="New derived scenario JSON")
    args = parser.parse_args()
    try:
        paths = [args.output.resolve(), args.scenario_output.resolve()]
        if len(set(paths)) != 2 or any(p.exists() for p in paths):
            raise ValueError("outputs must be distinct new files")
        source = json.loads(args.source_scenario.read_text())
        state = json.loads(args.source_checkpoint.read_text())
        transition = export_transition(args.manifest, source, state, args.target_id)
        verify_transition(args.manifest, source, state, transition)
        save(args.scenario_output, transition["scenario"])
        save(args.output, transition)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
