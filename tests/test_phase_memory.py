import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from age_runtime.core.runner import digest, initialize, advance, establish_context, faction_packet, accept_faction_choice
from age_runtime.core.private_play import start, verify, briefing, model_packet, institutional_memory
from age_runtime.core.source_compiler import compile_scenario


class PhaseMemoryTests(unittest.TestCase):
    def fixture(self):
        source = json.loads((Path(__file__).resolve().parents[1] /
                             "scenarios/independent-funding-rehearsal.json").read_text())
        source["strategic_establishment"] = True
        source["end_minute"] = source["turn_minutes"]
        target = copy.deepcopy(source)
        target["id"] = "later-recovery"
        target["initial"]["central_credits"] = 9
        target["initial"]["foundation_reserve"] = 7
        spec = {"effective_date": "2000-02-01"}
        compiled = {"scenario": target, "scenario_digest": digest(target), "spec_digest": digest(spec),
                    "dependencies": {}}
        original = {"scenario": source, "scenario_digest": digest(source),
                    "spec_digest": digest({"source": source["id"]}), "dependencies": {}}
        entry = {"id": target["id"], "title": "Later recovery",
                 "remember_from": {"scenario": source["id"], "source_spec_digest": original["spec_digest"],
                                   "target_spec_digest": compiled["spec_digest"],
                                   "reason": "Same reviewed institutional identities.",
                                   "actors": {"central": [{"kind": "established_context", "id": "inc:office"}],
                                              "east": [{"kind": "established_context", "id": "inc:east_room"}]}}}
        group = {"id": "recovery"}
        catalog = {"id": "test-campaign"}
        h = {"campaign": catalog["id"], "catalog_digest": digest(catalog),
             "effective_date": "2000-01-01", "actor": "central", "compiled": original}
        state = initialize(source)
        state = establish_context(source, state, digest(state), {"details": [
            {"id": "inc:office", "kind": "facility_detail", "label": "Office",
             "description": "An old reception room.", "audience": ["central"], "basis": "Fixture."},
            {"id": "inc:east_room", "kind": "facility_detail", "label": "East room",
             "description": "A small reception room.", "audience": ["east"], "basis": "Fixture."}]})
        for actor in source["model_factions"]:
            packet = faction_packet(source, state, actor)
            state = accept_faction_choice(source, state, actor, packet,
                                          {"packet_id": packet["packet_id"], "action": None})
        state = advance(source, state)
        previous = {"version": 1, "header": h, "header_digest": digest(h), "state": state}
        return catalog, group, entry, spec, compiled, previous

    def transition(self, fixture):
        catalog, group, entry, spec, compiled, previous = fixture
        with patch("age_runtime.core.private_play.select", return_value=(catalog, group, entry, spec, compiled)):
            return start("unused", compiled["scenario"]["id"], "central", {}, previous=previous)

    def test_actor_scoped_historical_transition(self):
        f = self.fixture()
        before = digest(f[-1])
        session = self.transition(f)
        self.assertEqual(digest(f[-1]), before)
        self.assertEqual(session["state"]["values"], f[4]["scenario"]["initial"])
        self.assertEqual(session["state"]["requests"], [])
        self.assertEqual(session["state"]["negotiations"], {})
        opening = briefing(session)
        self.assertEqual(opening["established_context"], {})
        memory = opening["phase_memory"]
        self.assertEqual([r["id"] for r in memory], ["inc:office"])
        self.assertEqual(memory[0]["source_date"], "2000-01-01")
        self.assertEqual(memory[0]["source_minute"], 10080)
        self.assertEqual(memory[0]["record"]["description"], "An old reception room.")
        self.assertEqual(institutional_memory(session)["phase_memory"], memory)
        east = model_packet(session, "east")["observation"]
        self.assertEqual([r["id"] for r in east["phase_memory"]], ["inc:east_room"])
        self.assertEqual(model_packet(session, "west")["observation"]["phase_memory"], [])
        verify(session)
        tampered = copy.deepcopy(session)
        tampered["header"]["continuity"]["memory_digest"] = "wrong"
        tampered["header_digest"] = digest(tampered["header"])
        with self.assertRaises(ValueError):
            verify(tampered)

    def test_reject_inaccessible_and_unapproved_carry(self):
        for mutation in ("hidden", "duplicate", "identity", "date", "revision", "incomplete"):
            f = self.fixture()
            catalog, group, entry, spec, compiled, previous = f
            rule = entry["remember_from"]
            if mutation == "hidden":
                rule["actors"]["central"][0]["id"] = "inc:east_room"
            elif mutation == "duplicate":
                rule["actors"]["central"] *= 2
            elif mutation == "identity":
                compiled["scenario"]["actors"]["east"]["label"] = "Different Institution"
            elif mutation == "date":
                spec["effective_date"] = "2000-01-02"
            elif mutation == "revision":
                rule["source_spec_digest"] = "wrong"
            else:
                previous["state"] = initialize(previous["header"]["compiled"]["scenario"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.transition(f)

    def test_authored_memory_rejected(self):
        f = self.fixture()
        scenario = copy.deepcopy(f[4]["scenario"])
        scenario["phase_memory"] = {}
        with self.assertRaisesRegex(ValueError, "approved prior session"):
            compile_scenario({"version": 1, "effective_date": "2000-02-01",
                              "scenario": scenario, "initial_refs": {}}, {})
