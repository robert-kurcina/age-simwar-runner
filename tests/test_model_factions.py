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
