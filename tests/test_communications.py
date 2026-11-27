import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (
    initialize, communicate, assess_proposition, digest, verify_checkpoint, faction_packet,
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

    def test_propositions_and_private_assessment(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        s["communication_propositions"] = {
            "estimate": {"text": "Recovery can finish in three weeks.", "initial_access": ["east"]},
            "restricted": {"text": "Separate local estimate.", "initial_access": ["west"]},
        }
        state = initialize(s)
        msg = {"id": "report1", "recipients": ["foundation"], "claim": "Three weeks.",
               "proposition": "estimate", "asserts": True}
        assessment = {"proposition": "estimate", "stance": "believes", "basis": ["report1"]}
        with self.assertRaises(ValueError):
            communicate(s, state, "west", digest(state), msg)
        with self.assertRaises(ValueError):
            assess_proposition(s, state, "foundation", digest(state), assessment)
        state = communicate(s, state, "east", digest(state), msg)
        self.assertEqual(observe(s, state, "foundation")["propositions"]["estimate"]["latest_stance"], "unstated")
        state = assess_proposition(s, state, "foundation", digest(state), assessment)
        revised = dict(msg, id="report2", corrects="report1", claim="Five weeks instead.", asserts=False)
        state = communicate(s, state, "east", digest(state), revised)
        state = assess_proposition(s, state, "foundation", digest(state),
                                   dict(assessment, stance="doubts", basis=["report1", "report2"]))
        projection = observe(s, state, "foundation")["propositions"]
        self.assertEqual(projection["estimate"]["latest_stance"], "doubts")
        self.assertEqual(len(projection["estimate"]["assessments"]), 2)
        self.assertNotIn("restricted", projection)
        self.assertNotIn("estimate", observe(s, state, "west")["propositions"])
        self.assertEqual(observe(s, state, "east")["propositions"]["estimate"]["latest_stance"], "unstated")
        self.assertEqual(state["values"], s["initial"])
        for actor in s["model_factions"]:
            packet = faction_packet(s, state, actor)
            state = accept_faction_choice(s, state, actor, packet,
                                          {"packet_id": packet["packet_id"], "action": None})
        state = advance(s, state)
        verify_checkpoint(s, state)
        self.assertEqual(observe(s, state, "foundation")["propositions"]["estimate"]["latest_stance"], "doubts")
        damaged = copy.deepcopy(state)
        damaged["requests"][1]["assessment"]["basis"] = ["unreceived"]
        with self.assertRaises(ValueError):
            verify_checkpoint(s, damaged)

    def test_report_evidence_and_private_intent(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        s["communication_propositions"] = {
            "completed": {"text": "Eastern recovery is complete.",
                          "initial_access": ["east"],
                          "report_binding": {"key": "east_progress", "comparison": "at_least", "threshold": 3}}
        }
        s["actors"]["foundation"]["report_delay_minutes"] = {"east_progress": 10080}
        state = initialize(s)
        msg = {"id": "claim1", "recipients": ["foundation", "west"],
               "claim": "Eastern recovery is complete.", "proposition": "completed",
               "asserts": True, "speaker_intent": "deceive"}
        state = communicate(s, state, "east", digest(state), msg)
        self.assertEqual(observe(s, state, "east")["communications"][0]["speaker_intent"], "deceive")
        self.assertNotIn("speaker_intent", observe(s, state, "foundation")["communications"][0])
        self.assertNotIn("speaker_intent", observe(s, state, "west")["communications"][0])
        command = {"proposition": "completed", "stance": "disbelieves", "basis": ["report:0"]}
        with self.assertRaises(ValueError):
            assess_proposition(s, state, "foundation", digest(state), command)
        for actor in s["model_factions"]:
            packet = faction_packet(s, state, actor)
            state = accept_faction_choice(s, state, actor, packet,
                                          {"packet_id": packet["packet_id"], "action": None})
        state = advance(s, state)
        report = observe(s, state, "foundation")["reports"]["east_progress"]
        self.assertEqual(report["as_of_minute"], 0)
        state = assess_proposition(s, state, "foundation", digest(state), command)
        evidence = state["requests"][-1]["assessment"]["report_evidence"][0]
        self.assertEqual(evidence["value"], report["value"])
        self.assertFalse(evidence["asserts"])
        self.assertEqual(evidence["as_of_minute"], 0)
        verify_checkpoint(s, state)
        damaged = copy.deepcopy(state)
        damaged["requests"][-1]["assessment"]["report_evidence"][0]["value"] = 99
        with self.assertRaises(ValueError):
            verify_checkpoint(s, damaged)

    def test_runtime_propositions_are_scoped_and_replayable(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        s["runtime_propositions"] = True
        state = initialize(s)
        claim = {"id": "survey1", "recipients": ["foundation"],
                 "claim": "A survey estimates that reopening is feasible.",
                 "proposition": "inc:survey", "asserts": True,
                 "introduce_proposition": {"id": "inc:survey", "text": "Reopening is feasible."}}
        state = communicate(s, state, "east", digest(state), claim)
        self.assertEqual(state["values"], s["initial"])
        self.assertEqual(observe(s, state, "east")["propositions"]["inc:survey"]["sources"],
                         [{"kind": "originated_claim", "id": "survey1"}])
        self.assertEqual(observe(s, state, "foundation")["propositions"]["inc:survey"]["latest_stance"], "unstated")
        self.assertNotIn("inc:survey", observe(s, state, "west")["propositions"])
        with self.assertRaises(ValueError):
            communicate(s, state, "west", digest(state),
                        {"id": "unknown", "recipients": ["east"], "claim": "Not feasible.",
                         "proposition": "inc:survey", "asserts": False})
        with self.assertRaises(ValueError):
            communicate(s, state, "east", digest(state), dict(claim, id="survey2"))
        state = assess_proposition(s, state, "foundation", digest(state),
                                   {"proposition": "inc:survey", "stance": "doubts", "basis": ["survey1"]})
        state = communicate(s, state, "foundation", digest(state),
                            {"id": "relay", "recipients": ["west"], "claim": "Feasibility is disputed.",
                             "proposition": "inc:survey", "asserts": False})
        self.assertEqual(observe(s, state, "west")["propositions"]["inc:survey"]["latest_stance"], "unstated")
        verify_checkpoint(s, state)
        damaged = copy.deepcopy(state)
        damaged["requests"][0]["communication"]["introduce_proposition"]["id"] = "inc:other"
        with self.assertRaises(ValueError):
            verify_checkpoint(s, damaged)

    def test_directional_delivery_and_recall(self):
        from age_runtime.core.institutional_memory import recall
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        s["runtime_propositions"] = True
        s["communication_delay_minutes"] = {"east": {"foundation": 10081}}
        state = initialize(s)
        packet = faction_packet(s, state, "foundation")
        claim = {"id": "dispatch", "recipients": ["foundation", "west"],
                 "claim": "An inspection is necessary.",
                 "proposition": "inc:inspection", "asserts": True,
                 "introduce_proposition": {"id": "inc:inspection", "text": "Inspection is necessary."}}
        state = communicate(s, state, "east", digest(state), claim)
        self.assertEqual(packet, faction_packet(s, state, "foundation"))
        self.assertEqual(observe(s, state, "east")["communications"][0]["scheduled_delivery"],
                         {"foundation": 10081, "west": 0})
        self.assertEqual(observe(s, state, "west")["communications"][0]["delivery_minute"], 0)
        self.assertEqual(recall(observe(s, state, "foundation"))["communications"], [])
        self.assertNotIn("inc:inspection", observe(s, state, "foundation")["propositions"])
        assessment = {"proposition": "inc:inspection", "stance": "doubts", "basis": ["dispatch"]}
        with self.assertRaises(ValueError):
            assess_proposition(s, state, "foundation", digest(state), assessment)
        with self.assertRaises(ValueError):
            communicate(s, state, "foundation", digest(state),
                        {"id": "relay", "recipients": ["central"], "claim": "Inspection needed.",
                         "proposition": "inc:inspection", "asserts": True})
        for turn in range(2):
            for actor in s["model_factions"]:
                packet = faction_packet(s, state, actor)
                state = accept_faction_choice(s, state, actor, packet,
                                              {"packet_id": packet["packet_id"], "action": None})
            state = advance(s, state)
            verify_checkpoint(s, state)
            if turn == 0:
                self.assertEqual(observe(s, state, "foundation")["communications"], [])
        received = recall(observe(s, state, "foundation"))
        self.assertEqual(received["communications"][0]["delivery_minute"], 10081)
        self.assertEqual(received["propositions"]["inc:inspection"]["latest_stance"], "unstated")
        state = assess_proposition(s, state, "foundation", digest(state), assessment)
        verify_checkpoint(s, state)
        self.assertEqual(observe(s, state, "foundation")["propositions"]["inc:inspection"]["latest_stance"], "doubts")

    def test_invalid_delivery_routes(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        for routes in ({"east": {"west": -1}}, {"east": {"west": True}},
                       {"east": {"east": 0}}, {"missing": {"west": 0}},
                       {"east": {"missing": 0}}, {"east": []}):
            s["communication_delay_minutes"] = routes
            with self.assertRaises(ValueError):
                initialize(s)
