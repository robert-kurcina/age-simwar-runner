"""Compile reviewed structured civilian inputs from local Git repositories."""
import argparse
import base64
import binascii
import copy
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from age_runtime.core.runner import digest, validate, save

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


def read_pinned_source(owners, owner, revision, path):
    """Read a Git blob or trusted connector export without changing provenance.

    Connector entries are operator-supplied assertions of repository identity
    and commit/path binding. Git blob SHA verifies the transferred bytes,
    not the authenticity of a fabricated manifest.
    """
    if owner not in owners or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("unapproved or unpinned source")
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or str(relative) != path or path == ".":
        raise ValueError("invalid source path")
    source = owners[owner]
    if not isinstance(source, dict):
        root = Path(source).resolve()
        if git(root, "cat-file", "-t", revision).strip() != b"commit":
            raise ValueError("source revision is not a commit")
        return git(root, "show", revision + ":" + path)
    if set(source) != {"kind", "files"} or source["kind"] != "connector-export-v1" or not isinstance(source["files"], list):
        raise ValueError("invalid connector source manifest")
    matches = []
    identities = set()
    for record in source["files"]:
        if not isinstance(record, dict) or set(record) != {"revision", "path", "blob_sha", "content_base64"} or not all(isinstance(v, str) for v in record.values()):
            raise ValueError("invalid connector source record")
        identity = (record["revision"], record["path"])
        if identity in identities:
            raise ValueError("duplicate connector source identity")
        identities.add(identity)
        if identity == (revision, path):
            matches.append(record)
    if len(matches) != 1:
        raise ValueError("pinned connector source unavailable")
    record = matches[0]
    try:
        raw = base64.b64decode(record["content_base64"], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid connector source encoding") from exc
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    if blob != record["blob_sha"]:
        raise ValueError("connector source blob mismatch")
    return raw


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
    raw = read_pinned_source(owners, ref["owner"], ref["revision"], str(path))
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


def resolve_evidence(ref, owners):
    """Bind reviewed narrative evidence without treating prose as a numeric fact."""
    fields = {"owner", "revision", "path", "heading", "reviewed_for", "classification"}
    if not isinstance(ref, dict) or set(ref) != fields or not all(
            isinstance(v, str) and v for v in ref.values()):
        raise ValueError("invalid evidence reference")
    if ref["owner"] not in owners:
        raise ValueError("unapproved evidence owner")
    if not re.fullmatch(r"[0-9a-f]{40}", ref["revision"]):
        raise ValueError("evidence requires full commit SHA")
    path = PurePosixPath(ref["path"])
    if path.is_absolute() or ".." in path.parts or path.suffix != ".md" or str(path) != ref["path"]:
        raise ValueError("evidence must reference a relative Markdown path")
    if ref["classification"] not in {"canonical", "historical"}:
        raise ValueError("invalid evidence classification")
    checked_date(ref["reviewed_for"])
    raw = read_pinned_source(owners, ref["owner"], ref["revision"], str(path))
    lines = raw.decode("utf-8").splitlines()
    headings = []
    fence = None
    for i, line in enumerate(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        match = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append((i, len(match.group(1)), match.group(2)))
    matches = [(i, level) for i, level, name in headings if name == ref["heading"]]
    if len(matches) != 1:
        raise ValueError("missing or ambiguous evidence heading")
    start, level = matches[0]
    end = next((i for i, depth, _ in headings if i > start and depth <= level), len(lines))
    section = "\n".join(lines[start:end])
    return {**ref, "content_sha256": hashlib.sha256(raw).hexdigest(),
            "section_sha256": hashlib.sha256(section.encode()).hexdigest()}


def compile_scenario(spec, owners):
    if not isinstance(spec, dict) or not {"version", "effective_date", "scenario", "initial_refs"} <= set(spec) or set(spec) - {"version", "effective_date", "scenario", "initial_refs", "evidence_refs", "faction_profiles"}:
        raise ValueError("invalid compiler specification")
    if type(spec["version"]) is not int or spec["version"] != VERSION:
        raise ValueError("unsupported compiler specification")
    effective = checked_date(spec["effective_date"])
    scenario = copy.deepcopy(spec["scenario"])
    if "phase_memory" in scenario:
        raise ValueError("historical memory must derive from approved prior session")
    refs = spec["initial_refs"]
    if not isinstance(scenario, dict) or not isinstance(scenario.get("initial"), dict):
        raise ValueError("missing scenario initial state")
    if not isinstance(refs, dict):
        raise ValueError("invalid initial references")
    evidence_refs = spec.get("evidence_refs", {})
    if not isinstance(evidence_refs, dict) or not (refs or evidence_refs):
        raise ValueError("missing source references")
    evidence = {}
    for key, ref in sorted(evidence_refs.items()):
        if not isinstance(ref, dict) or ref.get("reviewed_for") != spec["effective_date"]:
            raise ValueError("evidence review date differs from scenario")
        evidence[key] = resolve_evidence(ref, owners)
    dependencies = {}
    for key, ref in sorted(refs.items()):
        if key in scenario["initial"]:
            raise ValueError("literal and referenced initial values conflict")
        value, provenance = resolve_reference(ref, owners, effective)
        scenario["initial"][key] = value
        dependencies[key] = provenance
    if "faction_profiles" in spec:
        from age_runtime.core.participants import bind_factions
        bind_factions(scenario, spec["faction_profiles"], owners, spec["effective_date"])
    validate(scenario)
    return {"version": VERSION, "spec_digest": digest(spec),
            "scenario_digest": digest(scenario), "dependencies": dependencies,
            "scenario": scenario, **({"evidence": evidence} if evidence else {})}


def compile_variation(spec, variation, owners):
    """Compile an explicit, bounded civilian variation without changing its base."""
    fields = {"version", "id", "base_digest", "initial_overrides", "report_delays"}
    if not isinstance(variation, dict) or set(variation) != fields:
        raise ValueError("invalid variation fields")
    if type(variation["version"]) is not int or variation["version"] != VERSION:
        raise ValueError("unsupported variation version")
    if not isinstance(variation["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", variation["id"]):
        raise ValueError("invalid variation ID")
    if variation["base_digest"] != digest(spec):
        raise ValueError("variation base revision mismatch")
    base = compile_scenario(spec, owners)
    scenario = copy.deepcopy(base["scenario"])
    overrides = variation["initial_overrides"]
    delays = variation["report_delays"]
    if not isinstance(overrides, dict) or not isinstance(delays, dict):
        raise ValueError("invalid variation maps")
    approved = {}
    # Limit variations to civilian fixture resource budgets and reporting delays.
    # Do not override factual source values or expand the supported simulation scope.
    eligible = {
        "service-restoration": {"restoration_credits"},
        "community-assistance": {"aid_packages"},
        "civic-agreement": set(),
    }
    if scenario["id"] not in eligible:
        raise ValueError("variation unsupported for this scenario")
    for key, record in sorted(overrides.items()):
        if key not in eligible[scenario["id"]] or key not in scenario["initial"]:
            raise ValueError("initial override not permitted")
        if not isinstance(record, dict) or set(record) != {"value", "reason"}:
            raise ValueError("override requires value and reason")
        value, reason = record["value"], record["reason"]
        if type(value) is not int or value < 0 or not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalid override")
        approved[key] = {"original": scenario["initial"][key], "value": value,
                         "reason": reason, "classification": "hypothetical"}
        scenario["initial"][key] = value
    for actor, actor_delays in sorted(delays.items()):
        if actor not in scenario.get("actors", {}) or not isinstance(actor_delays, dict):
            raise ValueError("invalid reporting actor")
        profile = scenario["actors"][actor]
        for key, delay in sorted(actor_delays.items()):
            if key not in profile.get("visible_keys", []) or type(delay) is not int or delay < 0:
                raise ValueError("invalid report delay override")
            profile.setdefault("report_delay_minutes", {})[key] = delay
    scenario["id"] += "--" + variation["id"]
    validate(scenario)
    return {**base, "base_scenario_digest": base["scenario_digest"],
            "variation_digest": digest(variation), "variation_id": variation["id"],
            "initial_overrides": approved, "report_delays": copy.deepcopy(delays),
            "scenario_digest": digest(scenario), "scenario": scenario}


def stale_dependencies(snapshot, owners):
    """Compare pinned source file bytes with local HEAD; never mutate snapshot."""
    stale = []
    for key, ref in list(snapshot["dependencies"].items()) + [("evidence:" + key, ref) for key, ref in snapshot.get("evidence", {}).items()]:
        if ref["owner"] not in owners:
            raise ValueError("unapproved source owner")
        if isinstance(owners[ref["owner"]], dict):
            raise ValueError("connector export has no local HEAD for staleness comparison")
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
    parser.add_argument("owners", type=Path, help="Approved owner IDs mapped to Git roots or connector exports")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("scenario_output", type=Path)
    parser.add_argument("--variation", type=Path, help="Optional pinned civilian variation JSON")
    args = parser.parse_args()
    try:
        outputs = [args.snapshot.resolve(), args.scenario_output.resolve()]
        if len(set(outputs)) != 2 or any(p.exists() for p in outputs):
            raise ValueError("outputs must be distinct new files")
        spec = parse_json(args.spec.read_bytes())
        owners = parse_json(args.owners.read_bytes())
        result = (compile_variation(spec, parse_json(args.variation.read_bytes()), owners)
                  if args.variation else compile_scenario(spec, owners))
        save(args.scenario_output, result["scenario"])
        save(args.snapshot, result)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
