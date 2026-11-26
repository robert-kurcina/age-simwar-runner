import tempfile
import unittest
from pathlib import Path
import age_runtime.mythos.game as game
import age_runtime.mythos.mythos as mythos

class MythosTrialTests(unittest.TestCase):
    def test_catalog(self):
        c = {x["id"]: x for x in game.catalog()}
        self.assertEqual(len(c["mythos"]["scenarios"]), 3)
        self.assertIn("civic-recovery", c)

    def test_play_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "session.json"
            v = mythos.start("boothbay", p, 42)
            self.assertEqual(v["turn"], 0)
            self.assertNotIn("attributes", v)
            self.assertNotIn("primary_threat", str(v))
            old = v["revision"]
            v = mythos.act(p, "inspect_docks", old)
            self.assertEqual(v["turn"], 1)
            self.assertEqual(v["time"], "1927-10-13T09:00:00")
            with self.assertRaisesRegex(ValueError, "stale"):
                mythos.act(p, "depart", old)
            v = mythos.act(p, "depart", v["revision"])
            self.assertEqual(v["ending"]["reason"], "depart")
            self.assertEqual(v["choices"], [])
            self.assertEqual(mythos.inspect(p), v)

    def test_limit_and_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "session.json"
            with self.assertRaises(ValueError):
                mythos.start("ram-island", p, 42)
            v = mythos.start("boothbay", p, 42)
            with self.assertRaises(ValueError):
                mythos.act(p, "report", v["revision"])
            for _ in range(20):
                v = mythos.act(p, "observe", v["revision"])
            self.assertEqual(v["turn"], 20)
            self.assertEqual(v["ending"]["reason"], "limit")
            self.assertEqual(v["choices"], [])

    def test_tamper(self):
        s = mythos.initial("boothbay", 1)
        s["discoveries"].append("invented")
        with self.assertRaisesRegex(ValueError, "replay"):
            mythos.verify(s)

    def test_resources_and_recovery(self):
        s = mythos.initial("boothbay", 42)
        for _ in range(8):
            s = mythos.step(s, "observe")
        self.assertEqual(s["fatigue"], 1)
        s = mythos.step(s, "buy_meal")
        self.assertEqual(s["resources"]["cash_cents"], 2125)
        self.assertEqual(s["fatigue"], 0)
        for _ in range(2):
            s = mythos.step(s, "use_flask")
        self.assertEqual(s["resources"]["flask_servings"], 0)
        with self.assertRaises(ValueError):
            mythos.step(s, "use_flask")
        mythos.verify(s)

    def test_scores_and_inventory_projection(self):
        s = mythos.initial("boothbay", 42)
        v = mythos.view(s)
        self.assertFalse(any(x.startswith(("$", "Flask")) for x in v["inventory"]))
        self.assertEqual(v["resources"]["cash_cents"], 2200)
        s = mythos.step(s, "depart")
        self.assertEqual(s["ending"]["scores"]["Self Preserved"], 10.0)
        self.assertEqual(s["ending"]["scores"]["Truth Preserved"], 1.0)
        mythos.verify(s)

    def test_earned_revelation_and_account(self):
        def choose(state, action):
            return mythos.step(state, action)
        for seed in range(200):
            s = mythos.initial("boothbay", seed)
            self.assertNotIn("follow_eleanor", [x["id"] for x in mythos.view(s)["choices"]])
            s = choose(s, "talk_eleanor")
            if "eleanor_account" not in s["flags"]:
                continue
            self.assertIn("follow_eleanor", [x["id"] for x in mythos.view(s)["choices"]])
            s = choose(s, "inspect_docks")
            if "badge" not in s["flags"]:
                continue
            s = choose(s, "report")
            self.assertIsNone(s["ending"])
            self.assertIn("written_account", s["flags"])
            self.assertEqual(s["containment"], 0)
            s = choose(s, "leave_copy")
            self.assertTrue(s["ending"]["account_entrusted"])
            self.assertFalse(s["ending"]["account_relayed"])
            self.assertEqual(s["ending"]["scores"]["Horror Contained"], 1.0)
            mythos.verify(s)
            break
        else:
            self.fail("No successful evidence route")

    def test_timed_observation_once(self):
        s = mythos.initial("boothbay", 42)
        for _ in range(4):
            s = mythos.step(s, "rest_room")
        self.assertEqual(s["events_seen"], ["evening"])
        s = mythos.step(s, "observe")
        self.assertEqual(len(s["observations"]), 1)
        mythos.verify(s)

    def test_npc_continuity_and_visibility(self):
        a = mythos.initial("boothbay", 42)
        b = mythos.initial("boothbay", 42)
        self.assertEqual(a["npcs"], b["npcs"])
        self.assertEqual(a["npcs"]["elias"]["attributes"]["Willpower"], 4)
        self.assertEqual(mythos.view(a)["contacts"], [])
        for seed in range(200):
            s = mythos.step(mythos.initial("boothbay", seed), "talk_eleanor")
            if s["last_result"]["success"]:
                s = mythos.step(s, "follow_eleanor")
                self.assertEqual(s["npcs"]["eleanor"]["encounters"], 2)
                self.assertEqual(s["npcs"]["eleanor"]["disclosed"].count("eleanor_account"), 1)
                self.assertEqual(mythos.view(s)["contacts"][0]["name"], "Eleanor")
                v = str(mythos.view(s))
                for key in ("known_topics", "motivation", "secret", "attributes", "disclosed"):
                    self.assertNotIn(key, v)
                mythos.verify(s)
                s["npcs"]["eleanor"]["attributes"]["Willpower"] = 5
                with self.assertRaisesRegex(ValueError, "replay"):
                    mythos.verify(s)
                break
        else:
            self.fail("No successful first conversation")

    def test_npc_profile_rejects_unknown_topic(self):
        import copy
        story, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        next(a for a in rules["actions"] if a["id"] == "talk_eleanor")["disclosure"] = "invented"
        with self.assertRaisesRegex(ValueError, "disclosure"):
            mythos.npc_profiles(story, rules)

    def test_castine_independent_replay_and_endings(self):
        def run(seed, route):
            s = mythos.initial("castine", seed)
            for action in route:
                s = mythos.step(s, action)
            mythos.verify(s)
            return s
        self.assertEqual(run(42, ["inspect_wharf", "depart"]),
                         run(42, ["inspect_wharf", "depart"]))
        self.assertEqual(run(42, ["depart"])["ending"]["reason"], "depart")
        self.assertEqual(mythos.initial("castine", 42)["resources"], {"cash_cents": 3800})
        for seed in range(200):
            s = mythos.initial("castine", seed)
            for action in ("inspect_wharf", "inspect_ledger", "secure_estate"):
                s = mythos.step(s, action)
            if "sanctuary" in s["flags"] and len(s["discoveries"]) >= 2:
                s = mythos.step(s, "prepare_case")
                s = mythos.step(s, "entrust_case")
                self.assertTrue(s["ending"]["account_entrusted"])
                self.assertEqual(s["ending"]["scores"]["Horror Contained"], 1.0)
                mythos.verify(s)
                break
        else:
            self.fail("No successful Castine report route")

    def test_castine_background_clock_and_hidden_state(self):
        s = mythos.initial("castine", 42)
        self.assertEqual(s["npcs"]["zebediah"]["attributes"]["Willpower"], 4)
        self.assertNotIn("father_account", [a["id"] for a in mythos.view(s)["choices"]])
        for seed in range(200):
            s = mythos.step(mythos.initial("castine", seed), "secure_estate")
            if "sanctuary" in s["flags"]:
                for _ in range(7):
                    s = mythos.step(s, "rest_estate")
                self.assertIn("convergence", s["events_seen"])
                self.assertFalse(any("convergence" in x for x in s["observations"]))
                mythos.verify(s)
                break
        else:
            self.fail("No estate access")

    def test_boothbay_dxd_favor_and_replay(self):
        a = mythos.initial("boothbay", 42)
        self.assertEqual(a["dxd"]["favor"], 3)
        self.assertEqual(a["dxd"]["attributes"]["INT"], 9)
        a = mythos.step(a, "visit_elias")
        self.assertEqual(a["dxd"]["favor"], 2)
        t = a["dxd"]["tests"][0]
        self.assertEqual(t["inputs"]["favor"], 1)
        self.assertEqual(t["result"]["tn"], 10)
        b = mythos.step(mythos.initial("boothbay", 42), "visit_elias")
        self.assertEqual(a, b)
        self.assertNotIn("dxd", mythos.view(a))
        self.assertNotIn("favor", str(mythos.view(a)))
        self.assertEqual(mythos.view(a)["setting"], "Fear!")
        mythos.verify(a)
        a["dxd"]["favor"] += 1
        with self.assertRaisesRegex(ValueError, "replay"):
            mythos.verify(a)

    def test_boothbay_no_test_no_favor_cost(self):
        s = mythos.initial("boothbay", 42)
        for _ in range(4):
            s = mythos.step(s, "observe")
        self.assertEqual(s["dxd"]["tests"], [])
        self.assertEqual(s["dxd"]["favor"], 3)
        self.assertEqual(s["fatigue"], 0)
        mythos.verify(s)
