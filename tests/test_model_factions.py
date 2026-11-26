import unittest
from age_runtime.core.runner import initialize, advance, submit_request, faction_packet, accept_faction_choice, verify_checkpoint
from age_runtime.core.observations import observe
from tests.test_economy import fixture

def scenario():
    s = fixture()
    s["events"] = []
    s["constraints"] = []
    s["initial"]["credits"] = 1
    s["actors"]["council"]["visible_keys"].append("credits")
    s["action_catalog"] = {"recruit": {"description": "Improve labor capacity", "actors": ["council"]}}
    s["administrative_reviews_per_turn"] = 1
    s["capacity_actions"] = {"recruit": {"project": "repair", "capacity": "labor", "resource": "credits", "cost": 1}}
    s["model_factions"] = ["council"]
    return s

class ModelFactionTests(unittest.TestCase):
    def test_model_choice_and_abstention_replay(self):
        s = scenario()
        a = initialize(s)
        packet = faction_packet(s, a, "council")
        with self.assertRaises(ValueError):
            advance(s, a)
        with self.assertRaises(ValueError):
            submit_request(s, a, "council", {"action": "recruit"})
        b = accept_faction_choice(s, a, "council", packet, {"packet_id": packet["packet_id"], "action": "recruit"})
        c = accept_faction_choice(s, a, "council", packet, {"packet_id": packet["packet_id"], "action": None})
        self.assertEqual(b["values"], a["values"])
        self.assertEqual(observe(s, b, "other")["own_requests"], [])
        self.assertEqual(advance(s, b)["values"]["stage"], 1)
        self.assertEqual(advance(s, c)["values"]["stage"], 0)
        for state in (advance(s, b), advance(s, c)):
            verify_checkpoint(s, state)
        with self.assertRaises(ValueError):
            accept_faction_choice(s, b, "council", packet, {"packet_id": packet["packet_id"], "action": None})
        d = advance(s, b)
        new = faction_packet(s, d, "council")
        with self.assertRaises(ValueError):
            accept_faction_choice(s, d, "council", new, {"packet_id": packet["packet_id"], "action": None})

    def test_reject_unsupported_response_and_tamper(self):
        s = scenario()
        a = initialize(s)
        p = faction_packet(s, a, "council")
        for response in ({"packet_id":p["packet_id"],"action":"invent"},
                         {"packet_id":p["packet_id"],"action":"recruit","cost":0}):
            with self.assertRaises(ValueError):
                accept_faction_choice(s, a, "council", p, response)
        b = accept_faction_choice(s, a, "council", p, {"packet_id":p["packet_id"],"action":None})
        b["requests"][0]["origin"] = "player"
        with self.assertRaises(ValueError):
            verify_checkpoint(s,b)


    def test_asymmetric_priorities_and_delayed_goal_reports(self):
        s = scenario()
        a = s["actors"]["council"]
        a["objectives"] = {
            "repair": {"description": "Restore service", "key": "stage",
                       "comparison": "at_least", "threshold": 2},
            "reserve": {"description": "Retain funds", "key": "credits",
                        "comparison": "at_least", "threshold": 1}}
        a["strategy"] = {"motivation": "Prioritize service continuity",
                         "priorities": ["repair", "reserve"]}
        other = s["actors"]["other"]
        other["visible_keys"] = ["stage"]
        other["report_delay_minutes"] = {"stage": 10080}
        other["objectives"] = {"wait": {"description": "Delay commitment",
                              "key": "stage", "comparison": "at_most", "threshold": 0}}
        other["strategy"] = {"motivation": "Protect institutional autonomy",
                             "priorities": ["wait"]}
        state = initialize(s)
        packet = faction_packet(s, state, "council")
        own = packet["observation"]["faction_strategy"]
        self.assertEqual([g["id"] for g in own["goals"]], ["repair", "reserve"])
        self.assertNotIn("Protect institutional autonomy", str(packet))
        visible = observe(s, state, "other")["faction_strategy"]
        self.assertIsNone(visible["goals"][0]["observed_result"])
        self.assertNotIn("Prioritize service continuity", str(visible))
        chosen = accept_faction_choice(s, state, "council", packet,
                   {"packet_id": packet["packet_id"], "action": "recruit"})
        after = advance(s, chosen)
        next_packet = faction_packet(s, after, "council")
        self.assertFalse(next_packet["observation"]["faction_strategy"]["goals"][1]["observed_result"]["met"])
        self.assertTrue(observe(s, after, "other")["faction_strategy"]["goals"][0]["observed_result"]["met"])
        verify_checkpoint(s, after)
        for priorities in ([], ["repair"], ["reserve", "reserve"], ["repair", "unknown"]):
            a["strategy"]["priorities"] = priorities
            with self.assertRaises(ValueError):
                initialize(s)
        a["strategy"]["priorities"] = ["repair", "reserve"]
        a["visible_keys"].remove("credits")
        with self.assertRaises(ValueError):
            initialize(s)
