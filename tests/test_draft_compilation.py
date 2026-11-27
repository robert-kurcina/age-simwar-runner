"""Exercise the real compiler with explicitly synthetic evidence, not private canon."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from age_runtime.core.draft_compilation import compile_catalog, write_catalog
from age_runtime.core.source_compiler import parse_json
from age_runtime.core.private_play import select
from age_runtime.core.runner import initialize, verify_checkpoint, digest

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration"


class DraftCompilationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.catalog = self.root / "catalog"
        self.catalog.mkdir()
        self.path = self.catalog / "inventory.json"
        self.inventory = parse_json((ROOT / "inventory.json").read_bytes())
        self.path.write_text(json.dumps(self.inventory), encoding="utf-8")
        self.headings = {}
        self.spec_paths = []
        for group in self.inventory["groups"]:
            for entry in group["scenarios"]:
                spec = parse_json((ROOT / entry["spec"]).read_bytes())
                self.replace_refs(spec)
                p = self.catalog / entry["spec"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(spec), encoding="utf-8")
                self.spec_paths.append(p)
        records = []
        for path, headings in sorted(self.headings.items()):
            raw = ("# Synthetic fixture\n\n" + "\n".join(
                "## " + h + "\nSynthetic evidence only.\n" for h in sorted(headings)
            )).encode("utf-8")
            records.append({"revision": "a" * 40, "path": path,
                            "blob_sha": hashlib.sha1(b"blob " + str(len(raw)).encode()
                                                     + b"\x00" + raw).hexdigest(),
                            "content_base64": base64.b64encode(raw).decode("ascii")})
        self.owners = {"synthetic-fixture": {"kind": "connector-export-v1", "files": records}}

    def replace_refs(self, value):
        if isinstance(value, dict):
            if {"owner", "revision", "path", "heading"} <= value.keys():
                # Replace identity as well as bytes; never masquerade as canon.
                path = "fixture-" + hashlib.sha256(value["path"].encode()).hexdigest() + ".md"
                self.headings.setdefault(path, set()).add(value["heading"])
                value.update(owner="synthetic-fixture", revision="a" * 40, path=path,
                             classification="historical")
            for item in value.values():
                self.replace_refs(item)
        elif isinstance(value, list):
            for item in value:
                self.replace_refs(item)

    def test_collective_compilation_and_deterministic_output(self):
        report, snapshots = compile_catalog(self.path, self.owners)
        self.assertEqual((report, snapshots), compile_catalog(self.path, self.owners))
        self.assertEqual(len(snapshots), 7)
        self.assertEqual(sum(len(r["perspectives"]) for r in report["results"]), 25)
        self.assertEqual(report["author_review"], "pending")
        for sid, snapshot in snapshots.items():
            s = snapshot["scenario"]
            self.assertEqual(digest(s), snapshot["scenario_digest"])
            self.assertEqual(sid, s["id"])
            self.assertTrue(all("faction_context" in a for a in s["actors"].values()))
            verify_checkpoint(s, initialize(s))
            self.assertNotIn("Synthetic evidence only.", json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "catalog-only"):
                select(self.path, sid, self.owners)
        out = self.root / "out"
        self.assertEqual(write_catalog(self.path, self.owners, out), report)
        self.assertEqual(len(list(out.glob("*.snapshot.json"))), 7)
        self.assertEqual(parse_json((out / "report.json").read_bytes()), report)
        with self.assertRaisesRegex(ValueError, "new"):
            write_catalog(self.path, self.owners, out)
        with self.assertRaisesRegex(ValueError, "outside"):
            write_catalog(self.path, self.owners, self.catalog / "out")

    def test_missing_or_tampered_source_no_partial_output(self):
        for owners in ({}, self.bad_owners()):
            out = self.root / "out"
            with self.assertRaises(ValueError):
                write_catalog(self.path, owners, out)
            self.assertFalse(out.exists())

    def bad_owners(self):
        owners = copy.deepcopy(self.owners)
        owners["synthetic-fixture"]["files"][0]["blob_sha"] = "0" * 40
        return owners

    def test_invalid_catalog_paths_and_review_gate(self):
        entry = next(g["scenarios"][0] for g in self.inventory["groups"] if g["scenarios"])
        for change in ({"spec": "../outside.json"}, {"id": "../outside"},
                       {"status": "reviewed-illustrative"}, {"id": "wrong-id"}):
            before = dict(entry)
            entry.update(change)
            self.path.write_text(json.dumps(self.inventory), encoding="utf-8")
            with self.assertRaises(ValueError):
                compile_catalog(self.path, self.owners)
            entry.clear()
            entry.update(before)

    def test_private_offline_openings_review_gate_and_restore(self):
        from age_runtime.core.private_openings import export, read_package
        from age_runtime.core.private_play import briefing, pending_factions, resolve_turn
        from age_runtime.core.runner import faction_packet
        group = next(g for g in self.inventory["groups"] if g["id"] == "fallout")
        entry = group["scenarios"][0]
        sid = entry["id"]
        revision = "b" * 40
        out = self.root / "private.zip"
        with self.assertRaisesRegex(ValueError, "catalog-only"):
            export(self.path, self.owners, [sid], revision, out)
        self.assertFalse(out.exists())
        # Explicitly synthetic reviewed fixture, never promote the real inventory.
        group["status"] = "supported-pilot"
        entry["status"] = "reviewed-illustrative"
        self.path.write_text(json.dumps(self.inventory), encoding="utf-8")
        manifest = export(self.path, self.owners, [sid], revision, out)
        self.assertEqual(len(manifest["openings"]), 3)
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, "already exists"):
            export(self.path, self.owners, [sid], revision, out)
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            read_package(out, "c" * 40)
        self.owners.clear()
        restored, sessions = read_package(out, revision)
        self.assertEqual(manifest, restored)
        for (scenario, actor), session in sessions.items():
            self.assertEqual(scenario, sid)
            self.assertEqual(session["header"]["actor"], actor)
            self.assertEqual(briefing(session)["turn"], 0)
            self.assertNotIn("content_base64", json.dumps(session))
            verify_checkpoint(session["header"]["compiled"]["scenario"], session["state"])
        from zipfile import ZipFile
        with ZipFile(out, "a") as archive:
            archive.writestr("../unexpected", "not a package member")
        with self.assertRaisesRegex(ValueError, "unexpected package"):
            read_package(out, revision)

    def test_offline_full_campaign_openings_and_resumption(self):
        from age_runtime.core.private_openings import export, read_package
        from age_runtime.core.private_play import (
            briefing, decision_brief, model_decision_brief, model_choice,
            pending_factions, record_decision, update, verify,
        )
        from age_runtime.core.runner import save
        # Only the temporary, explicitly synthetic evidence catalog is reviewed.
        ids = []
        for group in self.inventory["groups"]:
            if group["scenarios"]:
                group["status"] = "supported-pilot"
                for entry in group["scenarios"]:
                    entry["status"] = "reviewed-illustrative"
                    ids.append(entry["id"])
        self.path.write_text(json.dumps(self.inventory), encoding="utf-8")
        archive = self.root / "campaign.zip"
        revision = "b" * 40
        export(self.path, self.owners, ids, revision, archive)
        self.owners.clear()
        import shutil
        shutil.rmtree(self.catalog)
        manifest, sessions = read_package(archive, revision)
        self.assertEqual(len(sessions), 25)
        for (sid, actor), opening in sessions.items():
            with self.subTest(scenario=sid, actor=actor):
                session = opening
                original = digest(opening)
                path = self.root / "active.json"
                # Record one deliberate abstention, then independently route
                # scripted model abstentions. This tests plumbing, not judgment.
                session = record_decision(session, digest(session), "opening",
                                          "Retain resources and observe.")
                while not briefing(session)["complete"]:
                    before = digest(session)
                    brief = decision_brief(session)
                    self.assertEqual(brief["actor"], actor)
                    self.assertEqual(digest(session), before)
                    for faction in pending_factions(session):
                        exchange = model_decision_brief(session, faction)
                        self.assertEqual(exchange["decision_brief"]["actor"], faction)
                        session = model_choice(session, faction, {
                            "packet_id": exchange["packet"]["packet_id"], "action": None})
                    session = update(session, turns=1)
                    save(path, session)
                    restored = verify(parse_json(path.read_bytes()))
                    self.assertEqual(digest(restored), digest(session))
                    session = restored
                self.assertEqual(briefing(session)["decision_pacing"]["count"], 1)
                self.assertEqual(pending_factions(session), [])
                self.assertEqual(digest(opening), original)
                self.assertEqual(verify(session), session)

    def test_selective_resource_acquisition(self):
        from age_runtime.core.resource_acquisition import requirements, verify_resources
        real = requirements(ROOT / "inventory.json")
        self.assertEqual(len(real["resources"]), 8)
        self.assertTrue(all(r["owner"] == "robert-kurcina/vault-sh44ser"
                            for r in real["resources"]))
        plan = requirements(self.path)
        self.assertEqual(plan, requirements(self.path))
        identities = {(r["owner"], r["revision"], r["path"]) for r in plan["resources"]}
        self.assertEqual(len(identities), len(plan["resources"]))
        self.assertEqual(len(identities), len(self.headings))
        self.assertTrue(all(r["uses"] for r in plan["resources"]))
        verified = verify_resources(self.path, self.owners)
        self.assertEqual(verified["status"], "bytes-verified-not-compiled")
        self.assertNotIn("content_base64", json.dumps(verified))
        self.assertEqual(len(verified["resources"]), len(identities))
        for invalid in ({}, self.bad_owners()):
            with self.assertRaises(ValueError):
                verify_resources(self.path, invalid)
        # Reject path traversal before attempting resource reads.
        p = self.spec_paths[0]
        spec = parse_json(p.read_bytes())
        ref = next(iter(spec["evidence_refs"].values()))
        ref["path"] = "../outside.md"
        p.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pinned revision"):
            requirements(self.path)

    def test_authenticated_resource_transport_contract(self):
        from age_runtime.core.github_resources import acquire
        calls = []
        def transport(item, token):
            self.assertEqual(token, "synthetic-token")
            calls.append((item["owner"], item["revision"], item["path"]))
            record = next(r for r in self.owners[item["owner"]]["files"]
                          if r["path"] == item["path"] and r["revision"] == item["revision"])
            return {"type": "file", "path": item["path"], "encoding": "base64",
                    "sha": record["blob_sha"], "content": record["content_base64"] + "\n"}
        result = acquire(self.path, ["synthetic-fixture"], "synthetic-token", transport)
        self.assertEqual(result, self.owners)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(len(calls), len(self.headings))
        self.assertEqual(compile_catalog(self.path, result),
                         compile_catalog(self.path, self.owners))
        calls.clear()
        with self.assertRaisesRegex(ValueError, "approved"):
            acquire(self.path, [], "synthetic-token", transport)
        self.assertFalse(calls)
        for change in ({"sha": "0" * 40}, {"path": "different.md"},
                       {"encoding": "none"}, {"type": "symlink"}):
            def invalid(item, token):
                return {**transport(item, token), **change}
            with self.assertRaises(ValueError):
                acquire(self.path, ["synthetic-fixture"], "synthetic-token", invalid)

    def test_actual_drafts_rehearse_without_sources(self):
        from age_runtime.core.draft_rehearsal import start_rehearsal
        from age_runtime.core.private_play import briefing, decision_brief, pending_factions, model_decision_brief, model_choice, update
        from age_runtime.core.private_openings import openings
        count = 0
        for group in self.inventory["groups"]:
            for entry in group["scenarios"]:
                sid = entry["id"]
                for actor in entry["player_factions"]:
                    session = start_rehearsal(ROOT / "inventory.json", sid, actor)
                    self.assertEqual(briefing(session)["qualification"], "unreviewed-rehearsal")
                    self.assertEqual(decision_brief(session)["qualification"], "unreviewed-rehearsal")
                    self.assertEqual(session["header"]["compiled"]["dependencies"], {})
                    self.assertNotIn("evidence", session["header"]["compiled"])
                    for faction in pending_factions(session):
                        exchange = model_decision_brief(session, faction)
                        session = model_choice(session, faction, {
                            "packet_id": exchange["packet"]["packet_id"], "action": None})
                    session = update(session, turns=1)
                    self.assertEqual(briefing(session)["turn"], 1)
                    count += 1
                with self.assertRaisesRegex(ValueError, "catalog-only"):
                    select(ROOT / "inventory.json", sid, {})
                with self.assertRaisesRegex(ValueError, "catalog-only"):
                    openings(ROOT / "inventory.json", {}, [sid])
        self.assertEqual(count, 25)

    def test_rehearsal_refuses_missing_mechanical_values(self):
        from age_runtime.core.draft_rehearsal import start_rehearsal
        entry = next(g["scenarios"][0] for g in self.inventory["groups"] if g["scenarios"])
        path = self.catalog / entry["spec"]
        spec = parse_json(path.read_bytes())
        spec["initial_refs"] = {"missing": {}}
        path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "self-contained"):
            start_rehearsal(self.path, entry["id"], entry["player_factions"][0])
