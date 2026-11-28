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
        # Neither external sponsor advances under abstention. Funding alone
        # cannot clear the industrial milestone gates.
        self.assertEqual(funded["fiji_chassis_progress"], 0)
        self.assertEqual(reserve["fiji_chassis_progress"], 0)
        self.assertEqual(funded["fiji_credits"], 0)
        self.assertEqual(reserve["fiji_credits"], 2)


    def test_milestone_gates_and_order_independence(self):
        from copy import deepcopy
        from age_runtime.core.economy import resolve_projects, validate_projects
        from age_runtime.core.private_play import decision_brief
        from age_runtime.core.runner import initialize
        opening = start_rehearsal(ROOT, SID, "fiji")
        assessment = next(p for p in decision_brief(opening)["projects"] if p["id"] == "fiji_chassis")
        self.assertTrue(assessment["dependency_blocked"])
        self.assertEqual(assessment["horizon"]["progress_if_capacity_unchanged"], 0)
        self.assertEqual(len(assessment["dependencies"]), 2)
        scenario = deepcopy(opening["header"]["compiled"]["scenario"])
        for project in scenario["economy_projects"]:
            for axis in project["axes"]:
                scenario["initial"][axis["key"]] = 3
        results = []
        for reverse in (False, True):
            s = deepcopy(scenario)
            if reverse:
                s["economy_projects"].reverse()
            state = initialize(s)
            resolve_projects(s, state, s["turn_minutes"])
            self.assertEqual(state["values"]["fiji_chassis_progress"], 0)
            self.assertEqual(state["values"]["inguria_certification_progress"], 1)
            self.assertEqual(state["values"]["caledonia_refining_progress"], 1)
            resolve_projects(s, state, 2 * s["turn_minutes"])
            self.assertEqual(state["values"]["fiji_chassis_progress"], 1)
            results.append(state["values"])
        self.assertEqual(results[0], results[1])
        for change in ("cycle", "hidden", "stale", "invalid_threshold"):
            s = deepcopy(scenario)
            if change == "cycle":
                s["project_dependencies"]["inguria_certification"] = [{"project": "fiji_chassis", "minimum_stage": 1}]
                s["actors"]["inguria"]["visible_keys"].append("fiji_chassis_progress")
            elif change == "hidden":
                s["actors"]["fiji"]["visible_keys"].remove("caledonia_refining_progress")
            elif change == "stale":
                s["actors"]["fiji"]["report_delay_minutes"] = {"caledonia_refining_progress": 1}
            else:
                s["project_dependencies"]["fiji_chassis"][0]["minimum_stage"] = 5
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_projects(s)
