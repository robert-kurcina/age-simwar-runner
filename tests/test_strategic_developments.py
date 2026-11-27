import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (initialize, negotiate, schedule_development, digest,
                                     verify_checkpoint, faction_packet, accept_faction_choice, advance)
from age_runtime.core.observations import observe
from age_runtime.core.institutional_memory import recall


class StrategicDevelopmentTests(unittest.TestCase):
    def scenario(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["initial"]["inspection_completed"] = 0
        for actor in ("central", "foundation"):
            s["actors"][actor]["visible_keys"].append("inspection_completed")
        s["actors"]["central"]["report_delay_minutes"] = {"inspection_completed": 10080}
        s["permission_terms"] = {
            "visit": {"issuer": "central", "grantee": "foundation",
                      "description": "Inspect the local service office.",
                      "max_due_minute": 40320}}
        s["event_templates"] = {
            "inspection": {"description": "The authorized visit was completed.",
                           "participant": "foundation", "audience": ["central", "foundation"],
                           "requires": {"foundation_reserve": 1}, "permission": "visit",
                           "outcome": "inspection_completed"}}
        return s

    def choose(self, s, state, actor, action=None):
        packet = faction_packet(s, state, actor)
        return accept_faction_choice(s, state, actor, packet,
                                     {"packet_id": packet["packet_id"], "action": action})

    def authorized(self, s):
        state = initialize(s)
        state = negotiate(s, state, "central", digest(state),
                          {"kind": "propose", "id": "permit", "recipient": "foundation",
                           "permission": "visit", "due_minute": 40320})
        return self.choose(s, state, "foundation", {"kind": "accept", "id": "permit"})

    def command(self, **changes):
        return dict({"template": "inspection", "due_minute": 10080, "permission_id": "permit",
                     "rationale": "Reviewed inspection opportunity."}, **changes)

    def finish_first_turn(self, s, state):
        for actor in ("east", "west"):
            state = self.choose(s, state, actor)
        return advance(s, state)

    def test_resolution_delay_and_replay(self):
        s = self.scenario()
        state = self.authorized(s)
        hidden = faction_packet(s, state, "west")
        old = copy.deepcopy(state)
        state = schedule_development(s, state, digest(state), self.command())
        self.assertEqual(state["values"], old["values"])
        self.assertEqual(state["ledger"], old["ledger"])
        self.assertEqual(state["minute"], 0)
        self.assertEqual(faction_packet(s, state, "west"), hidden)
        self.assertEqual(observe(s, state, "foundation")["developments"], [])
        with self.assertRaises(ValueError):
            schedule_development(s, state, digest(old), self.command())
        with self.assertRaises(ValueError):
            schedule_development(s, state, digest(state), self.command())
        state = self.finish_first_turn(s, state)
        self.assertEqual(state["generated_events"]["inspection"]["status"], "completed")
        self.assertEqual(state["values"]["inspection_completed"], 1)
        self.assertEqual(state["values"]["foundation_reserve"], 2)
        self.assertEqual(observe(s, state, "central")["values"]["inspection_completed"], 0)
        self.assertEqual(observe(s, state, "central")["developments"], [])
        result = recall(observe(s, state, "foundation"))["developments"][0]
        self.assertEqual(result["id"], "inspection")
        self.assertNotIn("rationale", result)
        self.assertEqual(observe(s, state, "west")["developments"], [])
        self.assertNotIn("inspection_completed", observe(s, state, "west")["values"])
        for actor in s["model_factions"]:
            state = self.choose(s, state, actor)
        state = advance(s, state)
        self.assertEqual(observe(s, state, "central")["values"]["inspection_completed"], 1)
        self.assertEqual(observe(s, state, "central")["developments"][0]["id"], "inspection")
        verify_checkpoint(s, state)
        broken = copy.deepcopy(state)
        broken["generated_events"]["inspection"]["status"] = "scheduled"
        with self.assertRaises(ValueError):
            verify_checkpoint(s, broken)

    def test_revoked_permission_cannot_be_replaced(self):
        s = self.scenario()
        state = self.authorized(s)
        state = schedule_development(s, state, digest(state), self.command(due_minute=20160))
        state = negotiate(s, state, "central", digest(state), {"kind": "revoke", "id": "permit"})
        state = self.finish_first_turn(s, state)
        state = negotiate(s, state, "central", digest(state),
                          {"kind": "propose", "id": "replacement", "recipient": "foundation",
                           "permission": "visit", "due_minute": 40320})
        state = self.choose(s, state, "foundation", {"kind": "accept", "id": "replacement"})
        state = self.finish_first_turn(s, state)
        self.assertEqual(state["generated_events"]["inspection"]["status"], "prerequisite_unmet")
        self.assertEqual(state["values"]["inspection_completed"], 0)
        self.assertEqual(observe(s, state, "foundation")["developments"], [])
        verify_checkpoint(s, state)

    def test_invalid_selection_and_protected_outcomes(self):
        s = self.scenario()
        state = initialize(s)
        with self.assertRaises(ValueError):
            schedule_development(s, state, digest(state), self.command())
        state = self.authorized(s)
        original = copy.deepcopy(state)
        for command in (self.command(due_minute=40320), self.command(due_minute=1),
                        self.command(permission_id="wrong"), self.command(updates={"foundation_reserve": 10})):
            with self.assertRaises(ValueError):
                schedule_development(s, state, digest(state), command)
        self.assertEqual(state, original)
        for key in ("foundation_reserve", "east_credits", "central_progress", "central_capacity"):
            bad = self.scenario()
            bad["event_templates"]["inspection"]["outcome"] = key
            with self.assertRaises(ValueError):
                initialize(bad)
        bad = self.scenario()
        bad["actors"]["west"]["visible_keys"].append("inspection_completed")
        with self.assertRaises(ValueError):
            initialize(bad)
        bad = self.scenario()
        bad["event_templates"]["inspection"]["requires"] = {"central_credits": 1}
        with self.assertRaises(ValueError):
            initialize(bad)
        disabled = self.scenario()
        del disabled["event_templates"]
        self.assertNotIn("developments", observe(disabled, initialize(disabled), "central"))
