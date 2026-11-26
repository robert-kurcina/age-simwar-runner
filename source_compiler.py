"""Compile reviewed structured civilian inputs from local Git repositories."""
import argparse
import copy
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from runner import digest, validate, save

VERSION = 1
CLASSIFICATIONS = {"historical", "canonical", "derived", "estimated", "hypothetical"}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("ambiguous duplicate JSON key: " + key)
        result[key] = value
    return result


def parse_json(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs)


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args],
                            capture_output=True, check=False)
    if result.returncode:
        raise ValueError("local Git source unavailable")
    return result.stdout


def checked_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expected ISO effective date")
    return date.fromisoformat(value)


def resolve_reference(ref, owners, effective_date):
    fields = {"owner", "revision", "path", "entity", "field", "effective_date", "classification"}
    if not isinstance(ref, dict) or set(ref) != fields or not all(
            isinstance(v, str) and v for v in ref.values()):
        raise ValueError("invalid reference")
    if ref["owner"] not in owners:
        raise ValueError("unapproved source owner")
    if not re.fullmatch(r"[0-9a-f]{40}", ref["revision"]):
        raise ValueError("source revision must be a full commit SHA")
    path = PurePosixPath(ref["path"])
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json" or str(path) != ref["path"]:
        raise ValueError("source path must be a relative JSON path")
    if ref["classification"] not in CLASSIFICATIONS:
        raise ValueError("unresolved or invalid source classification")
    if checked_date(ref["effective_date"]) != effective_date:
        raise ValueError("reference effective date differs from scenario")
    root = Path(owners[ref["owner"]]).resolve()
    if git(root, "cat-file", "-t", ref["revision"]).strip() != b"commit":
        raise ValueError("source revision is not a commit")
    raw = git(root, "show", ref["revision"] + ":" + str(path))
    data = parse_json(raw)
    try:
        entity = data["entities"][ref["entity"]]
        record = entity["fields"][ref["field"]]
        if set(record) != {"value", "effective_date", "classification"}:
            raise ValueError("invalid source record")
        if (record["effective_date"] != ref["effective_date"] or
                record["classification"] != ref["classification"]):
            raise ValueError("source metadata conflicts with reference")
        value = record["value"]
    except (KeyError, TypeError) as exc:
        raise ValueError("missing or malformed source selector") from exc
    if type(value) is not int or value < 0:
        raise ValueError("source must contain a nonnegative integer")
    return value, {**ref, "content_sha256": hashlib.sha256(raw).hexdigest(), "value": value}


def compile_scenario(spec, owners):
    if not isinstance(spec, dict) or set(spec) != {"version", "effective_date", "scenario", "initial_refs"}:
        raise ValueError("invalid compiler specification")
    if type(spec["version"]) is not int or spec["version"] != VERSION:
        raise ValueError("unsupported compiler specification")
    effective = checked_date(spec["effective_date"])
    scenario = copy.deepcopy(spec["scenario"])
    refs = spec["initial_refs"]
    if not isinstance(scenario, dict) or not isinstance(scenario.get("initial"), dict):
        raise ValueError("missing scenario initial state")
    if not isinstance(refs, dict) or not refs:
        raise ValueError("missing initial references")
    dependencies = {}
    for key, ref in sorted(refs.items()):
        if key in scenario["initial"]:
            raise ValueError("literal and referenced initial values conflict")
        value, provenance = resolve_reference(ref, owners, effective)
        scenario["initial"][key] = value
        dependencies[key] = provenance
    validate(scenario)
    return {"version": VERSION, "spec_digest": digest(spec),
            "scenario_digest": digest(scenario), "dependencies": dependencies,
            "scenario": scenario}


def stale_dependencies(snapshot, owners):
    """Compare pinned source file bytes with local HEAD; never mutate snapshot."""
    stale = []
    for key, ref in snapshot["dependencies"].items():
        if ref["owner"] not in owners:
            raise ValueError("unapproved source owner")
        root = Path(owners[ref["owner"]]).resolve()
        try:
            raw = git(root, "show", "HEAD:" + ref["path"])
        except ValueError:
            stale.append(key)
            continue
        if hashlib.sha256(raw).hexdigest() != ref["content_sha256"]:
            stale.append(key)
    return sorted(stale)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("owners", type=Path, help="Local JSON map of approved owner IDs to Git roots")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("scenario_output", type=Path)
    args = parser.parse_args()
    try:
        outputs = [args.snapshot.resolve(), args.scenario_output.resolve()]
        if len(set(outputs)) != 2 or any(p.exists() for p in outputs):
            raise ValueError("outputs must be distinct new files")
        result = compile_scenario(parse_json(args.spec.read_bytes()),
                                  parse_json(args.owners.read_bytes()))
        save(args.scenario_output, result["scenario"])
        save(args.snapshot, result)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
