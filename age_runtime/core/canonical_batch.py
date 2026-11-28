"""Private batch preparation; reuse existing source and compilation contracts."""
import argparse
import json
import os
from pathlib import Path
import shutil

from age_runtime.core import github_resources
from age_runtime.core.draft_compilation import write_catalog
from age_runtime.core.private_play import inventory, read
from age_runtime.core.reviewed_delivery import review_packet
from age_runtime.core.resource_acquisition import verify_resources
from age_runtime.core.runner import digest


def prepare(paths, output, *, owners=None, token=None, approved_owners=(), transport=github_resources.fetch):
    paths = [Path(p).resolve() for p in paths]
    output = Path(output).resolve()
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("select distinct inventories")
    if (owners is None) == (token is None):
        raise ValueError("choose exactly one authorized source input")
    protected = [Path(__file__).resolve().parents[2], *(p.parent for p in paths)]
    if owners is not None:
        protected.extend(Path(v).resolve() for v in owners.values() if isinstance(v, (str, Path)))
    if any(output.is_relative_to(p) for p in protected):
        raise ValueError("private output must be outside runner, catalogs and sources")
    # Cache exact pinned retrievals across inventories; acquire still verifies each.
    cache = {}
    def cached(item, credential):
        key = tuple(item[k] for k in ("owner", "revision", "path"))
        if key not in cache:
            cache[key] = transport(item, credential)
        return cache[key]

    output.mkdir(mode=0o700)
    try:
        results = []
        for index, path in enumerate(paths):
            source = owners if owners is not None else github_resources.acquire(
                path, approved_owners, token, cached)
            verified = verify_resources(path, source)
            directory = output / ("catalog-" + str(index))
            report = write_catalog(path, source, directory)
            packet = review_packet(path, source)
            if (report["inventory_digest"] != packet["inventory_digest"]
                    or report["inventory_digest"] != verified["inventory_digest"]):
                raise ValueError("inventory changed during batch")
            for row in packet["scenarios"]:
                snapshot = read(directory / (row["id"] + ".snapshot.json"))
                if digest(snapshot) != row["snapshot_digest"]:
                    raise ValueError("compiled snapshot changed during batch")
            for name, data in (("review-packet.json", {**packet, "packet_digest": digest(packet)}),
                               ("verified-resources.json", verified)):
                with (directory / name).open("x", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2, ensure_ascii=False)
                (directory / name).chmod(0o600)
            results.append({"catalog": inventory(path)["id"], "directory": directory.name,
                            "scenarios": len(packet["scenarios"]),
                            "perspectives": sum(len(r["perspectives"]) for r in packet["scenarios"]),
                            "packet_digest": digest(packet)})
        summary = {"status": "compiled-unreviewed", "author_review": "pending", "catalogs": results}
        with (output / "manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2)
        (output / "manifest.json").chmod(0o600)
        return summary
    except BaseException:
        shutil.rmtree(output)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("inventories", nargs="+", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--owners", type=Path)
    group.add_argument("--github", action="store_true")
    parser.add_argument("--allow-owner", action="append", default=[])
    args = parser.parse_args()
    try:
        result = prepare(args.inventories, args.output,
                         owners=read(args.owners) if args.owners else None,
                         token=os.environ.get("GH_TOKEN", "") if args.github else None,
                         approved_owners=args.allow_owner)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
