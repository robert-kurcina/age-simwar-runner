"""Exercise the distribution-safe full quarterly matrix through the real runner."""
import json
from pathlib import Path
import unittest

from age_runtime.core import runner
from age_runtime.core.observations import observe


class QuarterlyRehearsalTests(unittest.TestCase):
    def test_eight_turns_with_independent_choices(self):
        path = Path(__file__).resolve().parents[1] / "scenarios/quarterly-matrix-synthetic.json"
        s = json.loads(path.read_text())
        self.assertEqual(s["end_minute"] // s["turn_minutes"], 8)
        results = []
        for active in (False, True):
            state = runner.initialize(s)
            for _ in range(8):
                state = runner.submit_request(s, state, "patron_a", {"action": "patron_a_routes"})
                for actor in s["model_factions"]:
                    packet = runner.faction_packet(s, state, actor)
                    action = next(iter(packet["observation"]["available_requests"])) if active else None
                    state = runner.accept_faction_choice(s, state, actor, packet,
                                                         {"packet_id": packet["packet_id"], "action": action})
                state = runner.advance(s, state)
                runner.verify_checkpoint(s, state)
                for account in s["reserve_accounts"].values():
                    self.assertEqual(sum(state["values"][k] for k in
                                         [account["available"], account["depleted"], *account["commitments"].values()]),
                                     account["capacity"])
                for account in s["stock_accounts"].values():
                    self.assertGreaterEqual(state["values"][account["key"]], 0)
            self.assertEqual(state["turn"], 8)
            self.assertEqual(runner.advance(s, state), state)
            self.assertNotIn("patron_b_free", observe(s, state, "patron_a")["values"])
            results.append(state["values"])
        self.assertNotEqual(*results)
