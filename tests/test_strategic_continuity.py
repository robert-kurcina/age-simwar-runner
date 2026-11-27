import copy
import json
import tempfile
import unittest
from pathlib import Path

from age_runtime.core.private_play import start, update, model_packet, model_choice, verify, perspectives, pending_factions, switch_perspective, view
from age_runtime.core.runner import digest, save


class StrategicContinuityTest(unittest.TestCase):
    def test_complete_accounting_continues_without_old_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import subprocess
            def git(*args):
                return subprocess.check_output(["git", "-C", tmp, *args]).decode().strip()
            git("init")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (root / "history.md").write_text("# Context\nSynthetic regional recovery.\n")
            git("add", "history.md")
            git("commit", "-m", "Fixture evidence")
            revision = git("rev-parse", "HEAD")
            scenario = json.loads((Path(__file__).resolve().parents[1] /
                                    "scenarios/regional-cooperation-rehearsal.json").read_text())
            def spec(s, date):
                return {"version": 1, "effective_date": date, "initial_refs": {},
                        "scenario": s, "evidence_refs": {"context": {
                            "owner": "test", "revision": revision, "path": "history.md",
                            "heading": "Context", "reviewed_for": date, "classification": "canonical"}}}
            first = spec(scenario, "2000-01-01")
            next_s = copy.deepcopy(scenario)
            next_s["id"] = "regional-recovery-followup"
            second = spec(next_s, "2000-01-29")
            def entry(s, name):
                return {"id": s["scenario"]["id"], "title": name, "spec": name + ".json",
                        "status": "reviewed-illustrative"}
            a, b = entry(first, "First"), entry(second, "Second")
            b["carry_from"] = {"scenario": scenario["id"], "variables": {k:k for k in scenario["initial"]},
                               "reason": "Same ongoing recovery projects", "source_spec_digest": digest(first),
                               "target_spec_digest": digest(second)}
            catalog = {"version": 1, "id": "test", "groups": [{"id": "recovery",
                        "status": "supported-pilot", "scenarios": [a,b]}]}
            save(root / "First.json", first)
            save(root / "Second.json", second)
            save(root / "inventory.json", catalog)
            path, owners = root / "inventory.json", {"test": tmp}
            # Opt-in only. The same authored specification supports each reviewed
            # perspective without changing its initial accounting or objectives.
            self.assertEqual([x["id"] for x in perspectives(path, a["id"], owners)], ["central"])
            a["player_factions"] = ["central", "east", "west"]
            b["player_factions"] = ["central", "east", "west"]
            save(path, catalog)
            self.assertEqual([x["id"] for x in perspectives(path, a["id"], owners)],
                             ["central", "east", "west"])
            for human in a["player_factions"]:
                selected = start(path, a["id"], human, owners)
                self.assertEqual(selected["state"]["values"], scenario["initial"])
                self.assertEqual(set(pending_factions(selected)), set(scenario["actors"]) - {human})
                self.assertEqual(view(selected)["observation"]["actor"], human)
                self.assertEqual(set(view(selected)["observation"]["values"]),
                                 set(scenario["actors"][human]["visible_keys"]))
                with self.assertRaises(ValueError):
                    model_packet(selected, human)
                with self.assertRaises(ValueError):
                    switch_perspective(selected, next(x for x in scenario["actors"] if x != human))
                for model in pending_factions(selected):
                    packet = model_packet(selected, model)
                    selected = model_choice(selected, model, {"packet_id": packet["packet_id"], "action": None})
                selected = update(selected, turns=1)
                verify(selected)
            with self.assertRaises(ValueError):
                start(path, a["id"], "unknown", owners)
            a["player_factions"] = ["central", "central"]
            save(path, catalog)
            with self.assertRaises(ValueError):
                perspectives(path, a["id"], owners)
            a["player_factions"] = ["central", "east", "west"]
            save(path, catalog)
            session = start(path, a["id"], "central", owners)
            with self.assertRaises(ValueError):
                start(path, b["id"], "central", owners, previous=session)
            session = update(session, "central_support_east")
            for turn in range(4):
                for actor in ("east","west"):
                    packet = model_packet(session, actor)
                    action = "east_invest" if actor == "east" and turn == 1 else (
                             "west_invest" if actor == "west" and turn == 0 else None)
                    session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": action})
                session = update(session, turns=1)
            old = digest(session)
            with self.assertRaises(ValueError):
                start(path, b["id"], "east", owners, previous=session)
            follow = start(path, b["id"], "central", owners, previous=session)
            self.assertEqual(follow["state"]["values"], session["state"]["values"])
            self.assertEqual(follow["state"]["values"]["east_progress"], 3)
            self.assertEqual(follow["state"]["turn"], 0)
            self.assertEqual(follow["state"]["requests"], [])
            self.assertEqual(follow["state"]["negotiations"], {})
            self.assertEqual(follow["state"]["project_results"], [])
            self.assertEqual(digest(session), old)
            verify(follow)
            altered = copy.deepcopy(follow)
            altered["header"]["continuity"]["transferred"]["east_progress"]["value"] = 0
            altered["header_digest"] = digest(altered["header"])
            with self.assertRaises(ValueError):
                verify(altered)

    def test_mismatched_units_or_partial_accounting_rejected(self):
        from age_runtime.core.private_continuity import continuity_keys
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/regional-cooperation-rehearsal.json").read_text())
        for change in ("axis", "owner", "extra"):
            t = copy.deepcopy(s)
            if change == "axis":
                t["economy_projects"][0]["axes"][0]["axis"] = "shipping"
            elif change == "owner":
                t["actors"]["central"]["label"] = "Unrelated organization"
            else:
                t["initial"]["unrelated"] = 1
            with self.assertRaises(ValueError):
                continuity_keys(s, t)
