"""Export reviewed private strategic openings for offline play with a pinned runtime.

Use the existing private session format and start/verify functions. This is a
trusted-referee distribution, not a public artifact or an authorization system.
"""
import argparse
import json
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED
import os

from age_runtime.core.private_play import inventory, perspectives, start, verify
from age_runtime.core.runner import digest, initialize
from age_runtime.core.source_compiler import parse_json

SHA = re.compile(r"[a-f0-9]{40}")
ID = re.compile(r"[a-z0-9][a-z0-9_.-]*")


def openings(path, owners, scenario_ids):
    catalog = inventory(path)
    entries = {e["id"]: (g, e) for g in catalog["groups"] for e in g["scenarios"]}
    if not scenario_ids or len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("select distinct reviewed scenario IDs")
    sessions = []
    for sid in scenario_ids:
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid not in entries:
            raise ValueError("invalid scenario identity")
        group, entry = entries[sid]
        if group["status"] != "supported-pilot" or entry["status"] not in {
                "reviewed-illustrative", "verified-illustrative-pilot"}:
            raise ValueError("scenario is catalog-only")
        if entry.get("image_map"):
            raise ValueError("offline opening with external image assets unsupported")
        for actor in perspectives(path, sid, owners):
            aid = actor["id"]
            if not ID.fullmatch(aid):
                raise ValueError("invalid actor identity")
            # Standard fresh single-perspective openings only. No continuity or
            # implicit authorization to select an unreviewed scenario.
            session = verify(start(path, sid, aid, owners))
            sessions.append((sid, aid, session))
    return catalog, sessions


def export(path, owners, scenario_ids, revision, destination):
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ValueError("pinned engine revision required")
    destination = Path(destination).resolve()
    roots = [Path(__file__).resolve().parents[2], Path(path).resolve().parent]
    roots.extend(Path(v).resolve() for v in owners.values() if isinstance(v, (str, Path)))
    if any(destination.is_relative_to(r) for r in roots):
        raise ValueError("private output must be outside runner, catalog and source checkouts")
    if destination.exists():
        raise ValueError("destination already exists")
    catalog, sessions = openings(path, owners, scenario_ids)
    manifest = {"engine_revision": revision, "catalog_digest": digest(catalog),
                "openings": [{"scenario": sid, "actor": aid,
                              "title": session["header"]["title"],
                              "path": f"openings/{i}.json", "digest": digest(session)}
                             for i, (sid, aid, session) in enumerate(sessions)]}
    # Exclusive creation, restrictive permissions, no owners/source bytes.
    with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        try:
            with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
                for item, (_, _, session) in zip(manifest["openings"], sessions):
                    archive.writestr(item["path"], json.dumps(session, sort_keys=True))
        except BaseException:
            stream.close()
            destination.unlink()
            raise
    return manifest


def read_package(path, revision):
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ValueError("pinned engine revision required")
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive entry")
        if "manifest.json" not in names:
            raise ValueError("missing package manifest")
        manifest = parse_json(archive.read("manifest.json"))
        if not isinstance(manifest, dict) or set(manifest) != {"engine_revision", "catalog_digest", "openings"}:
            raise ValueError("invalid package manifest")
        if not isinstance(manifest["catalog_digest"], str) or not re.fullmatch(r"[a-f0-9]{64}", manifest["catalog_digest"]):
            raise ValueError("invalid catalog digest")
        if manifest["engine_revision"] != revision:
            raise ValueError("engine revision mismatch")
        entries = manifest["openings"]
        if not isinstance(entries, list) or not entries or set(names) != {"manifest.json"} | {
                f"openings/{i}.json" for i in range(len(entries))}:
            raise ValueError("unexpected package entries")
        seen = set()
        sessions = {}
        for i, item in enumerate(entries):
            if not isinstance(item, dict) or set(item) != {"scenario", "actor", "title", "path", "digest"} or not all(isinstance(v, str) for v in item.values()):
                raise ValueError("invalid opening record")
            if not ID.fullmatch(item["scenario"]) or not ID.fullmatch(item["actor"]):
                raise ValueError("invalid opening identity")
            key = (item["scenario"], item["actor"])
            if key in seen or item["path"] != f"openings/{i}.json":
                raise ValueError("duplicate or invalid opening identity")
            seen.add(key)
            session = verify(parse_json(archive.read(item["path"])))
            h = session["header"]
            s = h["compiled"]["scenario"]
            if (digest(session) != item["digest"] or key != (s["id"], h["actor"])
                    or h["catalog_digest"] != manifest["catalog_digest"]
                    or h["title"] != item["title"] or session["state"] != initialize(s)
                    or "continuity" in h or h.get("shared") or "image_map" in h
                    or h["compiled"].get("qualification") == "unreviewed-rehearsal"):
                raise ValueError("opening integrity mismatch")
            sessions[key] = session
    return manifest, sessions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    build = sub.add_parser("export")
    build.add_argument("inventory")
    build.add_argument("owners")
    build.add_argument("archive")
    build.add_argument("scenarios", nargs="+")
    for name in ("list", "restore"):
        cmd = sub.add_parser(name)
        cmd.add_argument("archive")
        if name == "restore":
            cmd.add_argument("scenario")
            cmd.add_argument("actor")
            cmd.add_argument("session")
    for cmd in sub.choices.values():
        cmd.add_argument("--engine-revision", required=True)
    a = p.parse_args()
    try:
        if a.command == "export":
            result = export(a.inventory, parse_json(Path(a.owners).read_bytes()),
                            a.scenarios, a.engine_revision, a.archive)
        else:
            result, sessions = read_package(a.archive, a.engine_revision)
            if a.command == "restore":
                session = sessions[(a.scenario, a.actor)]
                from age_runtime.core.private_play import briefing
                result = briefing(session)
                with os.fdopen(os.open(a.session, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
                    json.dump(session, stream, indent=2)
    except (ValueError, KeyError, TypeError, OSError, BadZipFile) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
