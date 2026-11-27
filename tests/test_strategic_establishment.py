import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (initialize, establish_context, digest, verify_checkpoint,
                                     faction_packet, accept_faction_choice, advance)
from age_runtime.core.observations import observe
from age_runtime.core.institutional_memory import recall, reminder_index


class StrategicEstablishmentTests(unittest.TestCase):
    def scenario(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["strategic_establishment"] = True
        return s

    def detail(self):
        return {"id": "inc:meeting_room", "kind": "facility_detail",
                "label": "Meeting room", "description": "A room with plain white walls.",
                "audience": ["central", "east"], "basis": "Ordinary meeting setting."}

    def test_scoped_establishment_revision_and_replay(self):
        s = self.scenario()
        state = initialize(s)
        old = copy.deepcopy(state)
        hidden = faction_packet(s, state, "west")
        visible = faction_packet(s, state, "east")
        detail = self.detail()
        state = establish_context(s, state, digest(state), {"details": [detail]})
        self.assertEqual(faction_packet(s, state, "west"), hidden)
        self.assertNotEqual(faction_packet(s, state, "east"), visible)
        self.assertEqual(state["values"], old["values"])
        self.assertEqual(state["ledger"], old["ledger"])
        self.assertEqual(state["minute"], old["minute"])
        central = observe(s, state, "central")
        self.assertEqual(central["decision_pacing"]["count"], 0)
        self.assertEqual(central["own_requests"], [])
        record = recall(central)["established_context"][detail["id"]]
        self.assertEqual(record["description"], detail["description"])
        self.assertNotIn("basis", record)
        self.assertNotIn("audience", record)
        self.assertEqual(reminder_index(central)["recent_established_ids"], [detail["id"]])
        self.assertEqual(observe(s, state, "foundation")["established_context"], {})
        with self.assertRaises(ValueError):
            establish_context(s, state, digest(old), {"details": [detail]})
        for actor in s["model_factions"]:
            packet = faction_packet(s, state, actor)
            state = accept_faction_choice(s, state, actor, packet,
                                          {"packet_id": packet["packet_id"], "action": None})
        state = advance(s, state)
        change = {"id": detail["id"], "before": detail["description"],
                  "after": "The walls are now painted pale blue.", "basis": "Routine redecoration."}
        state = establish_context(s, state, digest(state), {"changes": [change]})
        record = observe(s, state, "east")["established_context"][detail["id"]]
        self.assertEqual(record["description"], change["after"])
        self.assertEqual(record["established_minute"], 0)
        self.assertEqual(record["updated_minute"], 10080)
        self.assertEqual(record["history"][0]["before"], change["before"])
        self.assertNotIn("basis", record["history"][0])
        self.assertEqual(observe(s, state, "west")["established_context"], {})
        with self.assertRaises(ValueError):
            establish_context(s, state, digest(state), {"changes": [change]})
        verify_checkpoint(s, state)
        damaged = copy.deepcopy(state)
        damaged["requests"][-1]["establishment"]["changes"][0]["before"] = "Incorrect."
        with self.assertRaises(ValueError):
            verify_checkpoint(s, damaged)

    def test_rejection_atomic_and_no_mechanical_fields(self):
        s = self.scenario()
        state = initialize(s)
        old = copy.deepcopy(state)
        detail = self.detail()
        for malformed in (dict(detail, audience=["unknown"]), dict(detail, audience=[]),
                          dict(detail, resources=10), dict(detail, kind="permission"),
                          dict(detail, id="central_capacity")):
            with self.assertRaises(ValueError):
                establish_context(s, state, digest(state), {"details": [detail, malformed]})
            self.assertEqual(state, old)
        with self.assertRaises(ValueError):
            establish_context(s, state, digest(state), {"details": [detail, detail]})
        state = establish_context(s, state, digest(state), {"details": [detail]})
        with self.assertRaises(ValueError):
            establish_context(s, state, digest(state), {"details": [detail]})
        with self.assertRaises(ValueError):
            establish_context(s, state, digest(state), {"changes": [
                {"id": detail["id"], "before": detail["description"], "after": "Changed.",
                 "basis": "Test.", "audience": ["west"]}]})
        disabled = self.scenario()
        del disabled["strategic_establishment"]
        off = initialize(disabled)
        self.assertNotIn("established_context", observe(disabled, off, "central"))
        with self.assertRaises(ValueError):
            establish_context(disabled, off, digest(off), {"details": [detail]})
        bad = self.scenario()
        bad["strategic_establishment"] = False
        with self.assertRaises(ValueError):
            initialize(bad)
