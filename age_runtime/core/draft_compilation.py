"""Compile a draft-only strategic inventory without enabling reviewed gameplay."""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil

from age_runtime.core.private_play import inventory, supported, eligible_perspectives
from age_runtime.core.source_compiler import compile_scenario, parse_json
from age_runtime.core.runner import digest, initialize, verify_checkpoint


def compile_catalog(path, owners):
    """Return frozen snapshots and opening verification results, without writes."""
    catalog = inventory(path)
    root = Path(path).resolve().parent
    snapshots, results = {}, []
    for group in catalog["groups"]:
        for entry in group["scenarios"]:
            sid = entry["id"]
            if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
                raise ValueError("unsafe draft scenario identity")
            if entry["status"] != "draft-unreviewed":
                raise ValueError("draft compiler requires draft-unreviewed entries")
            spec_path = (root / entry["spec"]).resolve()
            if not spec_path.is_relative_to(root):
                raise ValueError("scenario path outside inventory")
            spec = parse_json(spec_path.read_bytes())
            snapshot = compile_scenario(spec, owners)
            scenario = snapshot["scenario"]
            if scenario["id"] != sid:
                raise ValueError("scenario identity mismatch")
            supported(scenario)
            perspectives = eligible_perspectives(entry, scenario)
            if not perspectives:
                raise ValueError("no eligible human perspectives")
            for actor in perspectives:
                variant = copy.deepcopy(scenario)
                if "model_factions" in variant:
                    order = list(variant["model_factions"]) + [
                        a for a in variant["actors"] if a not in variant["model_factions"]]
                    variant["model_factions"] = [a for a in order if a != actor]
                supported(variant)
                verify_checkpoint(variant, initialize(variant))
            snapshots[sid] = snapshot
            results.append({
                "id": sid, "status": "compiled-unreviewed",
                "spec_digest": snapshot["spec_digest"],
                "scenario_digest": snapshot["scenario_digest"],
                "perspectives": perspectives,
            })
    if not snapshots:
        raise ValueError("no draft scenarios to compile")
    return {"inventory_digest": digest(catalog), "author_review": "pending",
            "results": results}, snapshots


def write_catalog(path, owners, output):
    """Write to a new private directory only after all compilation succeeds."""
    output = Path(output).resolve()
    runner_root = Path(__file__).resolve().parents[2]
    catalog_root = Path(path).resolve().parent
    roots = [runner_root, catalog_root] + [
        Path(value).resolve() for value in owners.values()
        if isinstance(value, (str, Path))]
    if any(output.is_relative_to(root) for root in roots):
        raise ValueError("output must be outside runner, catalog and source checkouts")
    if output.exists():
        raise ValueError("output must be new")
    report, snapshots = compile_catalog(path, owners)
    output.mkdir(mode=0o700)
    try:
        for name, data in [("report.json", report)] + [
                (sid + ".snapshot.json", snapshot) for sid, snapshot in snapshots.items()]:
            target = output / name
            with target.open("x", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.write("\n")
            target.chmod(0o600)
    except BaseException:
        shutil.rmtree(output)
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("owners", type=Path, help="Existing authorized compiler owners mapping")
    parser.add_argument("output", type=Path, help="New private output directory")
    args = parser.parse_args()
    try:
        owners = parse_json(args.owners.read_bytes())
        report = write_catalog(args.inventory, owners, args.output)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
