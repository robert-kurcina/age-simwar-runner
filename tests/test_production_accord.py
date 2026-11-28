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
        # Isolate milestone mechanics from separately tested licence gate.
        scenario.pop("project_permissions")
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


    def test_permission_lifecycle_blocks_progress_independently(self):
        from copy import deepcopy
        from age_runtime.core.economy import resolve_projects, validate_projects
        from age_runtime.core.negotiation import apply, resolve
        from age_runtime.core.private_play import decision_brief
        from age_runtime.core.runner import initialize
        opening = start_rehearsal(ROOT, SID, "fiji")
        assessment = next(p for p in decision_brief(opening)["projects"] if p["id"] == "fiji_chassis")
        self.assertTrue(assessment["permission_blocked_next_resolution"])
        s = deepcopy(opening["header"]["compiled"]["scenario"])
        for project in s["economy_projects"]:
            for axis in project["axes"]:
                s["initial"][axis["key"]] = 3
        for key in ("inguria_certification_progress", "caledonia_refining_progress"):
            s["initial"][key] = 1
        turn = s["turn_minutes"]
        def proposal(state):
            apply(s, state, "fiji", {"kind": "propose", "id": "licence",
                  "recipient": "inguria", "permission": "chassis_licence", "due_minute": 3 * turn})
        for route in ("unanswered", "rejected", "accepted", "revoked", "expired"):
            state = initialize(s)
            proposal(state)
            if route == "rejected":
                apply(s, state, "inguria", {"kind": "reject", "id": "licence"})
            elif route in ("accepted", "revoked", "expired"):
                apply(s, state, "inguria", {"kind": "accept", "id": "licence"})
                if route == "revoked":
                    apply(s, state, "inguria", {"kind": "revoke", "id": "licence"})
            minute = 3 * turn if route == "expired" else turn
            resolve(s, state, minute)
            resolve_projects(s, state, minute)
            self.assertEqual(state["values"]["fiji_chassis_progress"], int(route == "accepted"), route)
            row = next(r for r in state["project_results"] if r["id"] == "fiji_chassis")
            self.assertEqual(row["outcome"], "clear" if route == "accepted" else "permission_blocked")
        for invalid in (["unknown"], ["chassis_licence", "chassis_licence"]):
            bad = deepcopy(s)
            bad["project_permissions"]["fiji_chassis"] = invalid
            with self.assertRaises(ValueError):
                validate_projects(bad)
        bad = deepcopy(s)
        bad["project_permissions"] = {"vanuatu_maintenance": ["chassis_licence"]}
        with self.assertRaises(ValueError):
            validate_projects(bad)


    def test_integrated_industrial_routes(self):
        from age_runtime.core.private_play import decision_brief

        def play(route):
            session = start_rehearsal(ROOT, SID, "fiji")
            t = 43200
            history = []
            for turn in range(6):
                # Each sponsor retains its own decision. These are scripted
                # inputs, not independent LLM deliberation.
                choices = {}
                if turn == 0:
                    session = record_decision(session, digest(session), "licence-request",
                        "Request temporary chassis documentation.",
                        negotiation_command={"kind": "propose", "id": "licence",
                            "recipient": "inguria", "permission": "chassis_licence",
                            "due_minute": (5 if route == "expiry" else 6) * t})
                    session = record_decision(session, digest(session), "industrial",
                        "Improve chassis industrial capacity.", action="fiji_chassis_improve_industrial")
                    choices = {"inguria": {"kind": "reject" if route == "refusal" else "accept", "id": "licence"},
                               "caledonia": "caledonia_refining_improve_materials",
                               "vanuatu": "vanuatu_support_caledonia" if route != "no-funding" else None}
                elif turn == 1:
                    session = record_decision(session, digest(session), "energy",
                        "Improve chassis energy capacity.", action="fiji_chassis_improve_energy")
                    choices = {"inguria": "inguria_certification_improve_industrial",
                               "caledonia": "caledonia_refining_improve_energy",
                               "vanuatu": "vanuatu_maintenance_improve_energy"}
                elif turn == 2:
                    choices = {"inguria": "inguria_support_fiji",
                               "vanuatu": "vanuatu_maintenance_improve_industrial"}
                elif turn == 3 and route == "revocation":
                    choices = {"inguria": {"kind": "revoke", "id": "licence"}}
                elif turn == 5 and route == "cooperation":
                    # The licence expires at the final resolution. Renewal
                    # cannot occur while an equivalent permission is active.
                    # Retain the actual achieved milestones, not a fabricated stage.
                    pass
                for actor in pending_factions(session):
                    packet = model_packet(session, actor)
                    session = model_choice(session, actor,
                        {"packet_id": packet["packet_id"], "action": choices.get(actor)})
                session = verify(update(session, turns=1))
                history.append(session["state"]["values"]["fiji_chassis_progress"])
            final = decision_brief(session)
            self.assertTrue(final["complete"])
            self.assertFalse(final["recovery_assessment"]["alternatives"])
            return session, history

        expected = {
            "cooperation": [0, 0, 1, 2, 3, 3],
            "refusal": [0, 0, 0, 0, 0, 0],
            "no-funding": [0, 0, 0, 0, 0, 0],
            "revocation": [0, 0, 1, 1, 1, 1],
            "expiry": [0, 0, 1, 2, 2, 2],
        }
        for route, milestones in expected.items():
            with self.subTest(route=route):
                session, actual = play(route)
                self.assertEqual(actual, milestones)
                self.assertEqual(session["state"]["values"]["fiji_credits"], 1)
                self.assertEqual(verify(session), session)
