"""Private author-review packet and explicit digest-bound reviewed staging.

Compilation verifies provenance and mechanics, not historical interpretation.
No author approval is inferred; public inventory and source files stay intact.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from age_runtime.core.draft_compilation import compile_catalog
from age_runtime.core.private_play import inventory, read
from age_runtime.core.private_openings import openings
from age_runtime.core.runner import digest


def review_packet(path, owners):
    report, snapshots = compile_catalog(path, owners)
    catalog = inventory(path)
    if report["inventory_digest"] != digest(catalog):
        raise ValueError("inventory changed during review preparation")
    return {"version": 1, "inventory_digest": report["inventory_digest"],
            "author_review": "pending",
            "scenarios": [{**row, "snapshot_digest": digest(snapshots[row["id"]])}
                          for row in report["results"]],
            "review_requirements": ["dated faction identity and authority",
                                    "historical interpretation and opening knowledge",
                                    "illustrative dates, quantities and objective thresholds",
                                    "publication and private distribution scope"]}


def stage_reviewed(path, owners, approvals, output):
    """Stage only explicitly approved exact snapshots in a new private directory."""
    packet = review_packet(path, owners)
    if (not isinstance(approvals, dict) or set(approvals) != {"packet_digest", "scenarios"}
            or approvals["packet_digest"] != digest(packet)
            or not isinstance(approvals["scenarios"], dict) or not approvals["scenarios"]):
        raise ValueError("explicit matching author approval required")
    selected = approvals["scenarios"]
    known = {row["id"]: row for row in packet["scenarios"]}
    for sid, approval in selected.items():
        if (sid not in known or not isinstance(approval, dict)
                or set(approval) != {"snapshot_digest", "reason"}
                or approval["snapshot_digest"] != known[sid]["snapshot_digest"]
                or not isinstance(approval["reason"], str) or not approval["reason"].strip()):
            raise ValueError("invalid or stale scenario approval")
    root = Path(path).resolve().parent
    output = Path(output).resolve()
    protected = [Path(__file__).resolve().parents[2], root]
    protected.extend(Path(v).resolve() for v in owners.values() if isinstance(v, (str, Path)))
    if any(output.is_relative_to(p) for p in protected):
        raise ValueError("private output must be outside runner, catalog and source checkouts")
    catalog = inventory(path)
    if digest(catalog) != packet["inventory_digest"]:
        raise ValueError("inventory changed after review")
    staged = deepcopy(catalog)
    specs = {}
    for group in staged["groups"]:
        group["scenarios"] = [e for e in group["scenarios"] if e["id"] in selected]
        if not group["scenarios"]:
            group["status"] = "catalog-only"
            continue
        group["status"] = "supported-pilot"
        for entry in group["scenarios"]:
            sid = entry["id"]
            source = (root / entry["spec"]).resolve()
            if not source.is_relative_to(root):
                raise ValueError("scenario path outside inventory")
            spec = read(source)
            if digest(spec) != known[sid]["spec_digest"]:
                raise ValueError("scenario changed after review")
            entry["spec"] = sid + ".json"
            entry["status"] = "reviewed-illustrative"
            specs[entry["spec"]] = spec
    output.mkdir(mode=0o700)
    try:
        for name, data in {**specs, "inventory.json": staged, "approval.json": approvals,
                           "review-packet.json": packet}.items():
            with (output / name).open("x", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
            (output / name).chmod(0o600)
        # Existing reviewed initialization checks every selected perspective.
        _, sessions = openings(output / "inventory.json", owners, list(selected))
        for sid, actor, session in sessions:
            compiled = session["header"]["compiled"]
            if compiled["spec_digest"] != known[sid]["spec_digest"]:
                raise ValueError("staged opening spec mismatch")
        # Recheck the exact input snapshot bindings before returning success.
        if review_packet(path, owners) != packet:
            raise ValueError("source changed during staging")
    except BaseException:
        shutil.rmtree(output)
        raise
    return {"status": "staged-reviewed", "scenarios": sorted(selected),
            "openings": len(sessions), "inventory_digest": digest(staged)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("packet", "stage"):
        cmd = sub.add_parser(name)
        cmd.add_argument("inventory", type=Path)
        cmd.add_argument("owners", type=Path)
        if name == "stage":
            cmd.add_argument("approvals", type=Path)
            cmd.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        owners = read(args.owners)
        if args.command == "packet":
            result = review_packet(args.inventory, owners)
            result = {**result, "packet_digest": digest(result)}
        else:
            result = stage_reviewed(args.inventory, owners, read(args.approvals), args.output)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
