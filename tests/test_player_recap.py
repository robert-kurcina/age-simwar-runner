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


    def test_targeted_recall_finds_old_claim_without_mutation(self):
        state = mythos.initial("boothbay", 42)
        public = mythos.view(state)
        # Synthetic public projection isolates retrieval from dialogue adjudication.
        public["dialogue"] = [{"id": i, "speaker": "eleanor", "listener": "pc",
                               "claim": "Missing brother" if i == 1 else "Other topic"}
                              for i in range(1, 15)]
        before = copy.deepcopy(public)
        self.assertNotIn(public["dialogue"][0],
                         player_recap.recap(public)["earned_information"]["recent_exchanges"])
        result = player_recap.recall(public, "missing BROTHER")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["matches"][0]["kind"], "communicated_claim")
        self.assertEqual(result["matches"][0]["record"]["id"], 1)
        result["matches"][0]["record"]["claim"] = "Changed"
        self.assertEqual(public, before)

    def test_recall_pagination_and_limits(self):
        public = mythos.view(mythos.initial("boothbay", 42))
        public["dialogue"] = [{"id": i, "claim": "needle"} for i in range(5)]
        public["referee"] = {"secret": "private-only-token"}
        first = player_recap.recall(public, "needle", limit=2)
        second = player_recap.recall(public, "needle", limit=2,
                                     offset=first["next_offset"])
        last = player_recap.recall(public, "needle", limit=2,
                                   offset=second["next_offset"])
        self.assertEqual([m["record"]["id"] for p in (first, second, last)
                          for m in p["matches"]], list(range(5)))
        self.assertIsNone(last["next_offset"])
        self.assertEqual(player_recap.recall(public, "private-only-token")["total"], 0)
        for kwargs in ({"limit": 0}, {"limit": 51}, {"offset": -1}):
            with self.assertRaises(ValueError):
                player_recap.recall(public, "needle", **kwargs)
        with self.assertRaises(ValueError):
            player_recap.recall(public, " ")
