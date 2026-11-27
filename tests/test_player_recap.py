"""Player recap must be read-only, scoped and reproducible."""
import copy
import unittest

from age_runtime.mythos import mythos, player_recap


class PlayerRecapTests(unittest.TestCase):
    def test_boothbay_recap_does_not_change_state_or_randomness(self):
        state = mythos.initial("boothbay", 42)
        before = copy.deepcopy(state)
        public = mythos.view(state)
        packet = player_recap.recap(public)
        self.assertEqual(state, before)
        self.assertEqual(packet, player_recap.recap(mythos.view(state)))
        self.assertEqual(packet["revision"], mythos.digest(state))
        self.assertEqual(packet["audience"], "player")
        self.assertEqual(packet["available_next_actions"], public["choices"])
        self.assertNotIn("referee", packet)
        self.assertNotIn("source_revision", packet)
        self.assertNotIn("npc_agency", packet)
        self.assertNotIn("secret", str(packet).lower())

    def test_packet_only_uses_public_information_and_copies_it(self):
        state = mythos.initial("boothbay", 9)
        public = mythos.view(state)
        packet = player_recap.recap(public)
        self.assertEqual(packet["earned_information"]["discoveries"], public["discoveries"])
        self.assertEqual(packet["social_continuity"]["contacts"], public["contacts"])
        packet["available_next_actions"].clear()
        self.assertEqual(public["choices"], mythos.view(state)["choices"])
        self.assertEqual(state["turn"], 0)

    def test_recap_rejects_raw_state_without_player_revision(self):
        with self.assertRaises(ValueError):
            player_recap.recap({"scenario": "boothbay", "choices": []})
