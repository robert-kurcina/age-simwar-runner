"""Bounded 2044 industrial cooperation rehearsal; no predictive claims."""
from pathlib import Path
import unittest

from age_runtime.core.campaign_discovery import discover
from age_runtime.core.draft_rehearsal import start_rehearsal
from age_runtime.core.private_play import pending_factions, model_packet, model_choice, update, verify, record_decision
from age_runtime.core.runner import digest

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/production-accord/inventory.json"
SID = "production-accord-critical-goods-draft"


class ProductionAccordTests(unittest.TestCase):
    def test_all_perspectives_and_full_horizon(self):
        episode = discover(ROOT)["groups"][0]["episodes"][0]
        self.assertEqual(episode["availability"], "available")
        self.assertEqual(episode["turns"], 6)
        self.assertEqual(len(episode["perspectives"]), 4)
        for actor in episode["perspectives"]:
            session = start_rehearsal(ROOT, SID, actor["id"])
            for _ in range(6):
                for faction in pending_factions(session):
                    packet = model_packet(session, faction)
                    session = model_choice(session, faction, {"packet_id": packet["packet_id"], "action": None})
                session = verify(update(session, turns=1))
            self.assertEqual(session["state"]["minute"], 259200)
            self.assertEqual(session["header"]["compiled"]["qualification"], "unreviewed-rehearsal")

    def test_fiji_investment_vs_reserve(self):
        def play(invest):
            session = start_rehearsal(ROOT, SID, "fiji")
            for turn in range(6):
                if invest and turn < 2:
                    axis = ("industrial", "energy")[turn]
                    session = record_decision(session, digest(session), "investment-" + str(turn),
                                              "Improve local chassis readiness.",
                                              action="fiji_chassis_improve_" + axis)
                for faction in pending_factions(session):
                    packet = model_packet(session, faction)
                    session = model_choice(session, faction, {"packet_id": packet["packet_id"], "action": None})
                session = verify(update(session, turns=1))
            return session["state"]["values"]
        funded, reserve = play(True), play(False)
        self.assertEqual(funded["fiji_chassis_progress"], 4)
        self.assertGreater(funded["fiji_chassis_progress"], reserve["fiji_chassis_progress"])
        self.assertEqual(funded["fiji_credits"], 0)
        self.assertEqual(reserve["fiji_credits"], 2)
