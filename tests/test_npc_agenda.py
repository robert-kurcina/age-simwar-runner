"""Weekly agenda expectations remain advisory and mechanically neutral."""
import copy
import unittest
from datetime import datetime

from age_runtime.mythos import mythos, npc_agenda


class NPCAgendaTests(unittest.TestCase):
    def test_weekday_windows_and_privacy(self):
        _, rules = mythos.load("boothbay")
        state = mythos.initial("boothbay", 42)
        before = copy.deepcopy(state)
        packet = mythos.gm_context(state, compact=True)
        agenda = packet["referee"]["npc_agendas"]["eleanor"]
        self.assertEqual(agenda["expected"]["label"], "Morning diner shift")
        self.assertEqual(agenda["authority"], "advisory_only")
        self.assertNotIn("npc_agendas", mythos.view(state))
        self.assertEqual(state, before)
        mythos.verify(state)
        windows = rules["npc_agendas"]["eleanor"]
        for at in ("1927-10-13T04:00:00", "1927-10-13T12:00:00",
                   "1927-10-13T16:00:00", "1927-10-16T09:00:00"):
            self.assertIsNone(npc_agenda.expected(windows, datetime.fromisoformat(at)))
        self.assertEqual(npc_agenda.expected(windows, datetime.fromisoformat(
            "1927-10-14T13:00:00"))["label"], "Afternoon diner shift")

    def test_multilocation_and_validation(self):
        _, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        rules["npcs"]["eleanor"]["eligible_locations"].append("Harbor Docks")
        windows = rules["npc_agendas"]["eleanor"]
        windows.append({"days": [3], "start_minute": 730, "end_minute": 765,
                        "location": "Harbor Docks", "label": "Midday errand"})
        npc_agenda.validate(rules)
        state = mythos.initial("boothbay", 42)
        state["time"] = "1927-10-13T12:30:00"
        before = copy.deepcopy(state)
        agenda = npc_agenda.projection(state, rules)["eleanor"]
        self.assertEqual(agenda["expected"]["location"], "Harbor Docks")
        self.assertEqual(agenda["established_location"], "Harbor Diner")
        self.assertIn("different_established_location", agenda["constraints"])
        self.assertEqual(state, before)
        windows.append(dict(windows[-1]))
        with self.assertRaises(ValueError):
            npc_agenda.validate(rules)
        windows.pop()
        windows[-1]["location"] = "Unreviewed location"
        with self.assertRaises(ValueError):
            npc_agenda.validate(rules)

    def test_sleep_and_committed_work_remain_constraints(self):
        _, rules = mythos.load("boothbay")
        state = mythos.initial("boothbay", 42)
        state["npcs"]["eleanor"]["activity"]["status"] = "asleep"
        state["timed_detail_events"].append({"npc": "eleanor", "status": "scheduled"})
        context = npc_agenda.projection(state, rules)["eleanor"]
        self.assertIn("asleep", context["constraints"])
        self.assertIn("committed_task", context["constraints"])
        self.assertIsNotNone(context["expected"])
