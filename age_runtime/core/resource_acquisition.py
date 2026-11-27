"""Plan and verify selective pinned resource acquisition in the runner.

Acquisition transport is supplied by the authorized operator (local Git or
connector export). This module does not contact a vault, modify its contents,
or create an alternative compiler.
"""
import argparse
from pathlib import Path, PurePosixPath
import hashlib
import json
import re

from age_runtime.core.private_play import inventory
from age_runtime.core.source_compiler import parse_json, read_pinned_source
from age_runtime.core.runner import digest


def requirements(path):
    """Enumerate only explicit references consumed by existing entry points."""
    catalog = inventory(path)
    root = Path(path).resolve().parent
    needed = {}

    def add(ref, scenario, use):
        if not isinstance(ref, dict):
            raise ValueError("invalid resource reference")
        owner, revision, name = (ref.get(k) for k in ("owner", "revision", "path"))
        if not all(isinstance(v, str) and v for v in (owner, revision, name)):
            raise ValueError("missing resource identity")
        relative = PurePosixPath(name)
        if (not re.fullmatch(r"[0-9a-f]{40}", revision) or relative.is_absolute()
                or ".." in relative.parts or str(relative) != name or name == "."):
            raise ValueError("resource requires pinned revision and relative path")
        needed.setdefault((owner, revision, name), set()).add((scenario, use))

    for group in catalog["groups"]:
        for entry in group["scenarios"]:
            sid = entry["id"]
            spec_path = (root / entry["spec"]).resolve()
            if not spec_path.is_relative_to(root):
                raise ValueError("scenario path outside inventory")
            spec = parse_json(spec_path.read_bytes())
            if spec["scenario"]["id"] != sid:
                raise ValueError("scenario identity mismatch")
            for field in ("initial_refs", "evidence_refs"):
                for key, ref in spec.get(field, {}).items():
                    add(ref, sid, field + ":" + key)
            for actor, profile in spec.get("faction_profiles", {}).items():
                for prop, record in profile["properties"].items():
                    for field in ("reference", "evidence"):
                        if field in record:
                            add(record[field], sid, "profile:" + actor + ":" + prop + ":" + field)
            if entry.get("image_map") is not None:
                add(entry["image_map"], sid, "image_map")
    return {"version": 1, "inventory_digest": digest(catalog),
            "resources": [{"owner": owner, "revision": revision, "path": name,
                           "uses": [{"scenario": sid, "field": use} for sid, use in sorted(uses)]}
                          for (owner, revision, name), uses in sorted(needed.items())]}


def verify_resources(path, owners):
    """Verify actual transferred bytes through the existing source reader."""
    plan = requirements(path)
    results = []
    for item in plan["resources"]:
        raw = read_pinned_source(owners, item["owner"], item["revision"], item["path"])
        results.append({**item, "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest()})
    return {**plan, "resources": results,
            "status": "bytes-verified-not-compiled"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--owners", type=Path, help="Optional authorized source mapping to verify")
    args = parser.parse_args()
    try:
        result = (verify_resources(args.inventory, parse_json(args.owners.read_bytes()))
                  if args.owners else requirements(args.inventory))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
