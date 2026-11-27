import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (
    initialize, communicate, digest, verify_checkpoint, faction_packet,
    accept_faction_choice, advance,
)
from age_runtime.core.observations import observe


class CommunicationsTest(unittest.TestCase):
    def test_scoped_correction_and_replay(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        state = initialize(s)
        old = copy.deepcopy(state)
        packet = faction_packet(s, state, "foundation")
        command = {"id": "estimate", "recipients": ["foundation"],
                   "claim": "Recovery estimated at three weeks."}
        state = communicate(s, state, "east", digest(state), command)
        self.assertEqual(state["values"], old["values"])
        self.assertEqual(state["ledger"], old["ledger"])
        self.assertEqual(state["minute"], old["minute"])
        self.assertEqual(observe(s, state, "west")["communications"], [])
        self.assertEqual(observe(s, state, "foundation")["communications"][0]["claim"], command["claim"])
        with self.assertRaises(ValueError):
            accept_faction_choice(s, state, "foundation", packet, {"packet_id": packet["packet_id"], "action": None})
        with self.assertRaises(ValueError):
            communicate(s, state, "east", digest(old), command)
        with self.assertRaises(ValueError):
            communicate(s, state, "east", digest(state), command)
        correction = {"id": "revision", "recipients": ["foundation"], "corrects": "estimate",
                      "claim": "Revised estimate: five weeks."}
        with self.assertRaises(ValueError):
            communicate(s, state, "west", digest(state), correction)
        state = communicate(s, state, "east", digest(state), correction)
        for actor in s["model_factions"]:
            packet = faction_packet(s, state, actor)
            state = accept_faction_choice(s, state, actor, packet,
                                          {"packet_id": packet["packet_id"], "action": None})
        state = advance(s, state)
        verify_checkpoint(s, state)
        self.assertEqual(len(observe(s, state, "foundation")["communications"]), 2)
        self.assertEqual(observe(s, state, "west")["communications"], [])
        tampered = copy.deepcopy(state)
        tampered["requests"][0]["minute"] += 1
        with self.assertRaises(ValueError):
            verify_checkpoint(s, tampered)
