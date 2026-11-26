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
                mythos.start("not-a-scenario", p, 42)
            v = mythos.start("boothbay", p, 42)
            with self.assertRaises(ValueError):
                mythos.act(p, "report", v["revision"])
            for _ in range(20):
                v = mythos.act(p, "observe", v["revision"])
            self.assertEqual(v["turn"], 20)
            self.assertIsNone(v["ending"])
            self.assertEqual(v["pacing"]["completed_spotlights"], 0)
            v = mythos.act(p, "depart", v["revision"])
            self.assertEqual(v["ending"]["reason"], "depart")
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
        self.assertEqual(s["dxd"]["concerns"]["fatigue"], 0)
        s = mythos.step(s, "buy_meal")
        self.assertEqual(s["resources"]["cash_cents"], 2125)
        self.assertEqual(s["dxd"]["concerns"]["fatigue"], 0)
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
        self.assertEqual(s["dxd"]["concerns"]["fatigue"], 0)
        mythos.verify(s)

    def test_full_dxd_character_records_and_physical_test(self):
        from age_runtime.core import dxd
        s = mythos.initial("boothbay", 42)
        expected = set(dxd.ATTRIBUTES)
        self.assertEqual(set(s["dxd"]["attributes"]), expected)
        for npc in s["npcs"].values():
            self.assertEqual(set(npc["dxd_attributes"]), expected)
        self.assertEqual(len(s["dxd"]["inactive_major_attributes"]), 2)
        for record in s["dxd"]["inactive_major_attributes"].values():
            self.assertEqual(set(record), expected)
        self.assertEqual(mythos.view(s)["contacts"], [])
        s = mythos.step(s, "clear_dock_obstruction")
        record = s["dxd"]["tests"][-1]
        self.assertEqual(record["components"]["attribute"], dxd.attribute_dm(s["dxd"]["attributes"]["STR"]))
        self.assertEqual(s["discoveries"], [])
        self.assertEqual(s["dxd"]["favor"], 3)
        mythos.verify(s)
        self.assertNotIn("inactive_major_attributes", str(mythos.view(s)))
        with self.assertRaises(ValueError):
            dxd.validate_attributes({"INT": 9})
        bad = dict(s["dxd"]["attributes"], SIZ=True)
        with self.assertRaises(ValueError):
            dxd.validate_attributes(bad)

    def test_boothbay_concerns_are_private_and_activity_specific(self):
        s = mythos.initial("boothbay", 42)
        s = mythos.step(s, "clear_dock_obstruction")
        self.assertEqual(s["dxd"]["concerns"]["fatigue"], 1)
        s = mythos.step(s, "rest_room")
        self.assertEqual(s["dxd"]["concerns"]["fatigue"], 0)
        self.assertNotIn("capacity", mythos.view(s)["condition"])
        self.assertNotIn("sanity", mythos.view(s)["condition"])
        mythos.verify(s)

    def test_inspiration_automatic_and_replay(self):
        import copy
        from age_runtime.core import dxd_inspiration
        _, rules = mythos.load("boothbay")
        action = copy.deepcopy(next(a for a in rules["actions"] if a["id"] == "inspect_docks"))
        action["test"]["tn"] = 16
        for seed in range(100):
            s = mythos.initial("boothbay", seed)
            s["turn"] = 1
            mythos.resolve_dxd(s, rules, action)
            self.assertEqual(len(s["dxd"]["inspirations"]), 1)
            self.assertEqual(s["dxd"]["concerns"]["weariness"], 1)
            self.assertTrue(s["dxd"]["tests"][-1]["inspired"])
            self.assertEqual(len(s["dxd"]["tests"][-1]["result"]["active"]["kept"]), 3)
            self.assertEqual(len(s["dxd"]["tests"][-1]["initial_result"]["active"]["kept"]), 2)
            s["turn"] = 2
            mythos.resolve_dxd(s, rules, action)
            self.assertEqual(len(s["dxd"]["inspirations"]), 1)
            self.assertEqual(s["dxd"]["tests"][-1]["components"]["inspiration"], 1)
            self.assertNotIn("probability", str(mythos.view(s)))
            break
        original = mythos.step(mythos.initial("boothbay", 42), "inspect_docks")
        mythos.verify(original)

    def test_castine_dxd_profiles_and_sanctuary(self):
        from age_runtime.core import dxd, dxd_conditions
        s = mythos.initial("castine", 42)
        self.assertEqual(set(s["dxd"]["attributes"]), set(dxd.ATTRIBUTES))
        self.assertEqual(len(s["dxd"]["inactive_major_attributes"]), 2)
        for npc in s["npcs"].values():
            self.assertEqual(set(npc["dxd_attributes"]), set(dxd.ATTRIBUTES))
        self.assertNotIn("sanity", mythos.view(s)["condition"])
        self.assertNotIn("prepare_case", [x["id"] for x in mythos.view(s)["choices"]])
        for seed in range(100):
            a = mythos.step(mythos.initial("castine", seed), "secure_estate")
            if "sanctuary" in a["flags"]:
                self.assertEqual(a["discoveries"], [])
                self.assertNotIn("prepare_case", [x["id"] for x in mythos.view(a)["choices"]])
                self.assertEqual(a["dxd"]["tests"][0]["inputs"]["tn"], 7)
                a = mythos.step(a, "rest_estate")
                mythos.verify(a)
                break
        else:
            self.fail("No sanctuary route")

    def test_derived_body_profiles_in_both_trials(self):
        from age_runtime.core import dxd_character, dxd_conditions
        for sid in ("boothbay", "castine"):
            s = mythos.initial(sid, 42)
            _, rules = mythos.load(sid)
            pc = s["dxd"]
            self.assertEqual(pc["attributes"]["SIZ"], 12)
            self.assertEqual(pc["body"]["weight_pounds"], 166)
            self.assertEqual(pc["attributes"]["MOV"], pc["body"]["run"])
            self.assertEqual(pc["concerns"]["capacity"], dxd_conditions.capacities(pc["attributes"]))
            for nid, npc in s["npcs"].items():
                expected = dxd_character.derive(rules["dxd"]["npc_attributes"][nid],
                                                rules["dxd"]["body_profiles"][nid])
                self.assertEqual(npc["body"], expected)
                self.assertEqual(npc["dxd_attributes"], expected["attributes"])
            self.assertNotIn("weight_pounds", str(mythos.view(s)))
            mythos.verify(s)

    def test_emicted_favor_after_exhaustion_not_during_last_spend(self):
        from age_runtime.core import dxd
        _, rules = mythos.load("boothbay")
        action = next(a for a in rules["actions"] if a["id"] == "visit_elias")
        s = mythos.initial("boothbay", 42)
        s["dxd"]["favor"] = 1
        s["turn"] = 1
        mythos.resolve_dxd(s, rules, action)
        self.assertEqual(s["dxd"]["favor"], 0)
        self.assertEqual(s["dxd"]["tests"][-1]["components"]["emicted"], 0)
        s["turn"] = 2
        mythos.resolve_dxd(s, rules, action)
        self.assertEqual(s["dxd"]["tests"][-1]["inputs"]["favor"], 0)
        self.assertEqual(s["dxd"]["tests"][-1]["components"]["emicted"], 1)
        self.assertEqual(dxd.emicted_favor(available=0, maximum=3, enabled=False), 0)

    def test_castine_ledger_gathers_independent_skills(self):
        s = mythos.step(mythos.initial("castine", 42), "inspect_ledger")
        t = s["dxd"]["tests"][-1]
        self.assertEqual([(x["name"], x["effective_level"]) for x in t["gathered"]["skill"]],
                         [("Interview", 2), ("Forensics", 1)])
        self.assertEqual(t["components"]["skill"], 3)
        self.assertNotIn("gathered", str(mythos.view(s)))
        mythos.verify(s)

    def test_boothbay_disclosure_triggers_separate_shock_test(self):
        for seed in range(200):
            s = mythos.step(mythos.initial("boothbay", seed), "talk_eleanor")
            if "eleanor_account" not in s["flags"]:
                continue
            s = mythos.step(s, "follow_eleanor")
            if "water_warning" not in s["flags"]:
                continue
            self.assertEqual(s["dxd"]["tests"][-1]["action"], "follow_eleanor:morale")
            self.assertEqual(s["dxd"]["morale"]["events"][-1]["kind"], "shock")
            self.assertEqual(s["dxd"]["morale"]["revelations"], [])
            self.assertNotIn("morale_event", str(mythos.view(s)))
            mythos.verify(s)
            break
        else:
            self.fail("No disclosure route")

    def test_ram_island_clock_and_earned_revelation(self):
        for seed in range(200):
            s = mythos.initial("ram-island", seed)
            self.assertNotIn("inspect_reflections", [a["id"] for a in mythos.view(s)["choices"]])
            for _ in range(8):
                s = mythos.step(s, "observe")
            self.assertIn("winter_signs", s["flags"])
            s = mythos.step(s, "inspect_reflections")
            if "physical_record" not in s["flags"]:
                continue
            s = mythos.step(s, "find_journal")
            if "journal_found" not in s["flags"]:
                continue
            s = mythos.step(s, "compare_journal")
            if "ancestry_understood" not in s["flags"]:
                continue
            self.assertEqual(s["dxd"]["morale"]["events"][-1]["trigger"], "amazement")
            self.assertEqual(s["events_seen"].count("winter"), 1)
            self.assertNotIn("secret", str(mythos.view(s)))
            mythos.verify(s)
            break
        else:
            self.fail("No earned ancestry route")

    def test_ram_island_limit_and_replay(self):
        s = mythos.initial("ram-island", 42)
        for _ in range(20):
            s = mythos.step(s, "observe")
        self.assertEqual(s["ending"]["reason"], "limit")
        self.assertEqual(s["turn"], 20)
        self.assertIn("spring_contact", s["flags"])
        self.assertEqual(s["dxd"]["morale"]["revelations"], [])
        mythos.verify(s)

    def test_ram_island_progression_is_calendar_driven(self):
        s = mythos.initial("ram-island", 42)
        self.assertEqual(s["progression"]["stage"], 1)
        for _ in range(8):
            s = mythos.step(s, "observe")
        self.assertEqual(s["progression"]["stage"], 2)
        for _ in range(5):
            s = mythos.step(s, "observe")
        self.assertEqual(s["progression"]["stage"], 3)
        self.assertNotIn("talk_matteo", [a["id"] for a in mythos.view(s)["choices"]])
        for _ in range(7):
            s = mythos.step(s, "observe")
        self.assertEqual(s["progression"]["stage"], 4)
        self.assertEqual(len(s["progression"]["changes"]), 3)
        self.assertNotIn("progression", mythos.view(s))
        mythos.verify(s)

    def test_ram_island_stabilization_never_reverses_existing_stage(self):
        from datetime import datetime
        _, rules = mythos.load("ram-island")
        s = mythos.initial("ram-island", 42)
        mythos.advance_events(s, rules, datetime.fromisoformat("1926-11-20T00:00:00"))
        self.assertEqual(s["progression"]["stage"], 2)
        s["progression"]["arrested"] = True
        mythos.advance_events(s, rules, datetime.fromisoformat("1927-03-05T00:00:00"))
        self.assertEqual(s["progression"]["stage"], 2)
        self.assertEqual(len(s["progression"]["changes"]), 1)
        self.assertIn("spring_contact", s["flags"])

    def test_contextual_inspiration_enrichment_and_replay(self):
        # Locate a genuine triggered Inspiration through committed actions.
        for seed in range(200):
            s = mythos.initial("ram-island", seed)
            for _ in range(8):
                s = mythos.step(s, "observe")
            s = mythos.step(s, "inspect_reflections")
            if "physical_record" not in s["flags"]:
                continue
            s = mythos.step(s, "find_journal")
            if "journal_found" not in s["flags"]:
                continue
            s = mythos.step(s, "compare_journal")
            prompt = mythos.view(s)["memory_prompt"]
            if prompt is None:
                continue
            original_tests = __import__("copy").deepcopy(s["dxd"]["tests"])
            original_concerns = __import__("copy").deepcopy(s["dxd"]["concerns"])
            original_tag = s["dxd"]["inspirations"][-1]["tag"]
            text = "You recall the discipline of enduring difficult circumstances during the war."
            mythos.apply_memory(s, prompt["event"], text)
            self.assertEqual(s["dxd"]["tests"], original_tests)
            self.assertEqual(s["dxd"]["concerns"], original_concerns)
            self.assertEqual(s["dxd"]["inspirations"][-1]["tag"], original_tag)
            self.assertEqual(mythos.view(s)["memories"][-1], text)
            self.assertIsNone(mythos.view(s)["memory_prompt"])
            with self.assertRaises(ValueError):
                mythos.apply_memory(s, prompt["event"], text)
            mythos.verify(s)
            s = mythos.step(s, "observe")
            mythos.verify(s)
            break
        else:
            self.fail("No committed Inspiration found")

    def test_boothbay_scene_and_alternative_leads(self):
        for seed in range(30):
            s = mythos.step(mythos.initial("boothbay", seed), "inspect_docks")
            if "badge" not in s["flags"]:
                continue
            self.assertIn("compare_almanac", [a["id"] for a in mythos.view(s)["choices"]])
            s = mythos.step(s, "compare_almanac")
            self.assertTrue(mythos.view(s)["scene"]["pressure"])
            self.assertNotIn("inspect_cave_entrance", [a["id"] for a in mythos.view(s)["choices"]])
            s = mythos.step(s, "wait_for_tide")
            self.assertEqual(s["time"], "1927-10-14T02:00:00")
            s = mythos.step(s, "inspect_cave_entrance")
            self.assertIn("cave_observed", s["flags"])
            self.assertNotIn("primary_threat", str(mythos.view(s)))
            mythos.verify(s)
            break
        else:
            self.fail("No badge route")

    def test_boothbay_second_search_not_unconditional(self):
        s = mythos.initial("boothbay", 42)
        self.assertNotIn("recheck_luggage", [a["id"] for a in mythos.view(s)["choices"]])
        for seed in range(60):
            s = mythos.step(mythos.initial("boothbay", seed), "inspect_room")
            if "paperwork" in s["flags"]:
                continue
            s = mythos.step(s, "inspect_docks")
            if "badge" not in s["flags"]:
                continue
            s = mythos.step(s, "recheck_luggage")
            self.assertIn("paperwork", s["flags"])
            self.assertNotIn("recheck_luggage", [a["id"] for a in mythos.view(s)["choices"]])
            mythos.verify(s)
            break
        else:
            self.fail("No alternate luggage route")

    def test_boothbay_opposition_and_demeanor(self):
        s = mythos.initial("boothbay", 42)
        for action in ("talk_eleanor", "visit_elias", "inspect_room"):
            s = mythos.step(s, action)
        self.assertIn("police_attention", s["flags"])
        self.assertTrue(s["narrative_events"]["clocks"]["official_attention"]["resolved"])
        self.assertIn("speak_burroughs", [a["id"] for a in mythos.view(s)["choices"]])
        s = mythos.step(s, "speak_burroughs")
        self.assertIn("police_clearance" if s["last_result"]["success"] else "police_refusal", s["flags"])
        self.assertTrue(any(c["name"] == "Chief Burroughs" and "demeanor" in c for c in mythos.view(s)["contacts"]))
        mythos.verify(s)

    def test_demeanor_limits(self):
        s = mythos.initial("boothbay", 42)
        for _ in range(5):
            mythos.change_demeanor(s, "eleanor", 1)
        self.assertEqual(s["relationships"]["eleanor"], 3)
        for _ in range(5):
            mythos.change_demeanor(s, "eleanor", -1)
        self.assertEqual(s["relationships"]["eleanor"], 0)
        mythos.change_demeanor(s, "eleanor", 1)
        self.assertEqual(s["relationships"]["eleanor"], 0)

    def test_spatial_movement_and_route_replay(self):
        s = mythos.initial("boothbay", 42)
        v = mythos.view(s)
        self.assertEqual(v["scene"]["zone"], "town")
        self.assertNotIn("move:Devil's Throat Sea Caves", [a["id"] for a in v["choices"]])
        before = mythos.digest(s)
        with self.assertRaises(ValueError):
            mythos.step(s, "move:Devil's Throat Sea Caves")
        self.assertEqual(mythos.digest(s), before)
        s = mythos.step(s, "move:Creek Inlet South")
        self.assertEqual(s["time"], "1927-10-13T08:20:00")
        self.assertEqual(s["transitions"][-1]["terrain"], ["Rough"])
        self.assertEqual(mythos.view(s)["scene"]["zone"], "inlet")
        self.assertEqual(s["dxd"]["tests"], [])
        mythos.verify(s)

    def test_npc_availability_and_single_anchor(self):
        s = mythos.initial("boothbay", 42)
        self.assertIsNone(s["npcs"]["burroughs"]["location"])
        self.assertFalse(any(a["id"].startswith("speak_burroughs") for a in mythos.view(s)["choices"]))
        for action in ("talk_eleanor", "visit_elias", "inspect_room"):
            s = mythos.step(s, action)
        self.assertIsNone(s["npcs"]["burroughs"]["location"])
        self.assertIn("speak_burroughs_diner", [a["id"] for a in mythos.view(s)["choices"]])
        s = mythos.step(s, "speak_burroughs_diner")
        self.assertEqual(s["npcs"]["burroughs"]["location"], "Harbor Diner")
        self.assertNotIn("speak_burroughs", [a["id"] for a in mythos.view(s)["choices"]])
        mythos.verify(s)

    def test_spatial_window_and_terrain_cost(self):
        from age_runtime.mythos import spatial
        _, rules = mythos.load("boothbay")
        cfg = rules["spatial"]
        docks, cave = "Harbor Docks", "Devil's Throat Sea Caves"
        self.assertIsNone(spatial.route(cfg, docks, cave, "1927-10-14T02:00:00", []))
        self.assertIsNone(spatial.route(cfg, docks, cave, "1927-10-14T02:25:00", ["tide_window_known"]))
        self.assertEqual(spatial.route(cfg, docks, cave, "1927-10-14T02:00:00", ["tide_window_known"])["minutes"], 10)
        self.assertIsNotNone(spatial.route(cfg, cave, docks, "1927-10-14T03:00:00", []))

    def test_spotlight_lifecycle_advisory_and_replayed(self):
        s = mythos.initial("boothbay", 42)
        start = s["time"]
        s = mythos.narrative_step(s, {"kind": "open", "id": "journal", "label": "Understand the fisherman's account"})
        self.assertEqual(s["time"], start)
        self.assertEqual(s["turn"], 0)
        s = mythos.step(s, "observe")
        s = mythos.step(s, "move:Creek Inlet South")
        self.assertEqual(s["pacing"]["scene"], "inlet_inquiry")
        self.assertEqual(s["pacing"]["current"], "journal")
        self.assertEqual(len(s["pacing"]["spotlights"][0]["activities"]), 2)
        before = (s["time"], s["turn"], mythos.digest(s["dxd"]))
        s = mythos.narrative_step(s, {"kind": "complete", "id": "journal"})
        self.assertEqual((s["time"], s["turn"], mythos.digest(s["dxd"])), before)
        self.assertEqual(mythos.view(s)["pacing"]["completed_spotlights"], 1)
        with self.assertRaises(ValueError):
            mythos.narrative_step(s, {"kind": "complete", "id": "journal"})
        with self.assertRaises(ValueError):
            mythos.narrative_step(s, {"kind": "open", "id": "journal", "label": "Duplicate"})
        for n in range(24):
            key = "trial_" + str(n)
            s = mythos.narrative_step(s, {"kind": "open", "id": key, "label": "Synthetic character exchange"})
            s = mythos.narrative_step(s, {"kind": "complete", "id": key})
        self.assertEqual(mythos.view(s)["pacing"]["completed_spotlights"], 25)
        self.assertEqual(mythos.view(s)["pacing"]["remaining_spotlights"], 0)
        self.assertIsNone(s["ending"])
        mythos.verify(s)

    def test_scene_eligibility_and_abandoned_spotlight(self):
        s = mythos.initial("boothbay", 42)
        before = mythos.digest(s)
        with self.assertRaises(ValueError):
            mythos.narrative_step(s, {"kind": "scene", "id": "official_attention"})
        self.assertEqual(mythos.digest(s), before)
        s = mythos.narrative_step(s, {"kind": "open", "id": "inquiries", "label": "Follow the evidence"})
        s = mythos.step(s, "talk_eleanor")
        self.assertEqual(s["pacing"]["scene"], "town_inquiry")
        s = mythos.step(s, "visit_elias")
        s = mythos.step(s, "inspect_room")
        self.assertIn("official_attention", mythos.view(s)["pacing"]["scene"]["eligible_frames"])
        before = (s["time"], s["turn"], mythos.digest(s["dxd"]))
        s = mythos.narrative_step(s, {"kind": "scene", "id": "official_attention"})
        self.assertEqual((s["time"], s["turn"], mythos.digest(s["dxd"])), before)
        self.assertEqual(s["pacing"]["current"], "inquiries")
        s = mythos.narrative_step(s, {"kind": "abandon", "id": "inquiries"})
        self.assertEqual(mythos.view(s)["pacing"]["completed_spotlights"], 0)
        mythos.verify(s)

    def test_second_resolution_and_beat_metadata(self):
        from unittest.mock import patch
        import copy
        story, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        rules["actions"].append({"id": "test_beat", "label": "Synthetic immediate beat",
                                 "seconds": 10, "interval_seconds": 10,
                                 "narrative_beat": True, "repeatable": True})
        with patch.object(mythos, "load", return_value=(story, rules)):
            s = mythos.initial("boothbay", 42)
            s = mythos.step(s, "test_beat")
            self.assertEqual(s["time"], "1927-10-13T08:00:10")
            self.assertEqual(mythos.view(s)["pacing"]["interval_seconds"], 10)
            self.assertEqual(mythos.view(s)["pacing"]["narrative_beats"], 1)
            self.assertEqual(mythos.view(s)["pacing"]["completed_spotlights"], 0)
            mythos.verify(s)

    def test_tide_spotlight_and_deadline(self):
        for seed in range(30):
            s = mythos.step(mythos.initial("boothbay", seed), "inspect_docks")
            if "badge" not in s["flags"]:
                continue
            s = mythos.step(s, "compare_almanac")
            s = mythos.narrative_step(s, {"kind": "open", "id": "tide", "label": "Investigate the tidal cave"})
            s = mythos.step(s, "wait_for_tide")
            s = mythos.step(s, "inspect_cave_entrance")
            s = mythos.narrative_step(s, {"kind": "complete", "id": "tide"})
            self.assertEqual(mythos.view(s)["pacing"]["completed_spotlights"], 1)
            mythos.verify(s)
            break
        else:
            self.fail("No successful tide route")
        s = mythos.initial("boothbay", 42)
        while not s["ending"]:
            choices = mythos.view(s)["choices"]
            if not any(a["id"] == "observe" for a in choices):
                s = mythos.step(s, choices[0]["id"])
            else:
                s = mythos.step(s, "observe")
        self.assertGreater(s["turn"], 20)
        mythos.verify(s)

    def test_supported_spotlight_budgets(self):
        from age_runtime.mythos import pacing
        _, rules = mythos.load("boothbay")
        for target in (6, 12, 24):
            self.assertEqual(pacing.initial({"target_spotlights": target}, rules["scene"], rules["start_location"])["target"], target)
        with self.assertRaises(ValueError):
            pacing.initial({"target_spotlights": 20}, rules["scene"], rules["start_location"])
        self.assertEqual(mythos.view(mythos.initial("boothbay", 42))["pacing"]["target_spotlights"], 24)

    def test_terminal_spotlight_and_revision(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "session.json"
            v = mythos.start("boothbay", path, 42)
            old = v["revision"]
            v = mythos.narrative(path, {"kind": "open", "id": "exit", "label": "Withdraw"}, old)
            with self.assertRaisesRegex(ValueError, "stale"):
                mythos.act(path, "depart", old)
            v = mythos.act(path, "depart", v["revision"])
            at = v["time"]
            v = mythos.narrative(path, {"kind": "complete", "id": "exit"}, v["revision"])
            self.assertEqual(v["time"], at)
            self.assertEqual(v["pacing"]["completed_spotlights"], 1)
            self.assertEqual(v["ending"]["reason"], "depart")
            with self.assertRaises(ValueError):
                mythos.narrative(path, {"kind": "open", "id": "new", "label": "New focus"}, v["revision"])
            self.assertEqual(mythos.inspect(path), v)

    def test_sleep_room_replays_and_advances_events(self):
        s = mythos.initial("boothbay", 42)
        s = mythos.step(s, "move:Sailor's Rest Boarding House")
        self.assertEqual(s["dxd"]["activity"]["limit_seconds"], 45 * 3600)
        s = mythos.step(s, "sleep_room")
        self.assertEqual(s["time"], "1927-10-13T17:10:00")
        self.assertEqual(s["dxd"]["activity"]["status"], "awake")
        self.assertEqual(s["dxd"]["activity"]["awake_seconds"], 0)
        self.assertEqual(s["resources"]["cash_cents"], 2050)
        mythos.verify(s)

    def test_interrupted_sleep_and_early_waking(self):
        from unittest.mock import patch
        import copy
        story, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        rules["events"].append({"id": "test_interrupt", "at": "1927-10-13T10:10:00",
                                "observation": "A disturbance interrupts sleep.",
                                "interrupt_activity": True,
                                "locations": ["Sailor's Rest Boarding House"]})
        with patch.object(mythos, "load", return_value=(story, rules)):
            s = mythos.initial("boothbay", 42)
            s = mythos.step(s, "move:Sailor's Rest Boarding House")
            s = mythos.step(s, "sleep_room")
            self.assertEqual(s["time"], "1927-10-13T10:10:00")
            self.assertEqual(s["last_result"]["interrupted"], "event")
            self.assertEqual(s["dxd"]["activity"]["sleep_seconds"], 7200)
            self.assertEqual({x["id"] for x in mythos.view(s)["choices"]}, {"continue_sleep", "wake_early"})
            s = mythos.step(s, "continue_sleep")
            self.assertEqual(s["time"], "1927-10-13T17:10:00")
            self.assertEqual(s["dxd"]["activity"]["status"], "awake")
            self.assertEqual(s["resources"]["cash_cents"], 2050)
            mythos.verify(s)

    def test_activity_fractional_recovery_and_deprivation(self):
        from age_runtime.core import dxd_conditions as c
        s = mythos.initial("boothbay", 42)["dxd"]
        concerns, attrs = s["concerns"], s["attributes"]
        c.add(concerns, fatigue=5, stress=8, weariness=5)
        clock = c.activity_initial(attrs)
        for seconds in (30, 30):
            c.advance_activity(concerns, clock, seconds, "rest", attributes=attrs)
        self.assertEqual(concerns["fatigue"], 4)
        self.assertEqual(concerns["stress"], 8)
        c.advance_activity(concerns, clock, 600, "quiet", safe=True, attributes=attrs)
        self.assertLess(concerns["stress"], 8)
        clock = c.activity_initial(attrs, awake_seconds=45 * 3600)
        w = concerns["weariness"]
        c.advance_activity(concerns, clock, 3600, "active", attributes=attrs)
        self.assertEqual(concerns["weariness"], w + 1)

    def test_forced_sleep_checks_and_waking(self):
        from age_runtime.core import dxd_conditions as c
        import copy
        pc = mythos.initial("boothbay", 42)["dxd"]
        attrs = pc["attributes"]
        for seed in range(100):
            concerns = copy.deepcopy(pc["concerns"])
            c.add(concerns, weariness=concerns["capacity"]["endurance"] * 2)
            clock = c.activity_initial(attrs, awake_seconds=45 * 3600)
            elapsed = c.advance_activity(concerns, clock, 10800, "active", seed=seed, attributes=attrs)
            if clock["pending_sleep_seconds"] != 0:
                continue
            self.assertLess(elapsed, 10800)
            self.assertFalse(clock["checks"][-1]["result"]["passed"])
            c.begin_sleep(concerns, clock, attrs)
            needed = clock["required_sleep_seconds"]
            c.advance_activity(concerns, clock, needed, "sleep", attributes=attrs)
            self.assertTrue(c.wake(concerns, clock, attrs, seed=seed))
            self.assertEqual(clock["awake_seconds"], 0)
            break
        else:
            self.fail("No forced sleep case")

    def test_named_clocks_and_warning_progress(self):
        from age_runtime.mythos import events
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        self.assertEqual(events.projection(s, rules)["clocks"], [])
        events.advance_time(s, rules, 7200)
        self.assertFalse(s["narrative_events"]["clocks"]["warning_arrangements"]["resolved"])
        s["flags"].append("local_warning")
        events.advance_time(s, rules, 1799)
        self.assertEqual(events.next_boundary(s, rules), 1)
        events.advance_time(s, rules, 1)
        self.assertEqual(events.projection(s, rules)["clocks"][0]["marks"], 1)
        events.advance_time(s, rules, 1800)
        self.assertIn("warning_distributed", s["flags"])
        before = len(s["narrative_events"]["ledger"])
        events.advance_time(s, rules, 3600)
        self.assertEqual(len(s["narrative_events"]["ledger"]), before)

    def test_encounter_scope_and_dice(self):
        from age_runtime.mythos import events
        _, rules = mythos.load("boothbay")
        for seed in range(100):
            s = mythos.initial("boothbay", seed)
            s["narrative_events"]["encounter"]["dice"] = 6
            events.encounter_check(s, rules, "overflow")
            check = s["narrative_events"]["encounter"]["checks"][-1]
            self.assertEqual(check["severity"], max(0, check["rolls"].count(1) - check["rolls"].count(6)))
            self.assertEqual(s["narrative_events"]["encounter"]["dice"], 3)
            self.assertNotEqual(check["event"], "landward_crabs")
            if check["event"]:
                self.assertEqual(check["event"], "violet_filaments")
                self.assertIn("filament_anomaly", s["flags"])
                break
        else:
            self.fail("No eligible encounter")
        s = mythos.initial("boothbay", seed)
        s["location"] = "Harbor Diner"
        s["narrative_events"]["encounter"]["dice"] = 6
        events.encounter_check(s, rules, "overflow")
        self.assertIsNone(s["narrative_events"]["encounter"]["checks"][-1]["event"])

    def test_encounter_progress_replays(self):
        s = mythos.initial("boothbay", 42)
        for _ in range(18):
            s = mythos.step(s, "observe")
        e = s["narrative_events"]["encounter"]
        self.assertEqual(len(e["checks"]), 1)
        self.assertEqual(e["dice"], 3)
        self.assertEqual(e["checks"][0]["kind"], "overflow")
        mythos.verify(s)

    def test_gm_context_separate_and_bounded(self):
        s = mythos.initial("boothbay", 42)
        public = mythos.view(s)
        packet = mythos.gm_context(s)
        self.assertEqual(packet["audience"], "gm_only")
        self.assertEqual(packet["player_surface"]["revision"], public["revision"])
        self.assertNotIn("referee", public)
        self.assertNotIn("official_attention", str(public["event_pressure"]))
        self.assertIn("official_attention", [x["id"] for x in packet["referee"]["clocks"]])
        self.assertEqual(packet["referee"]["participants"], [])
        self.assertIn("watch_patterns", packet["referee"]["approaches"]["inspect_docks"])
        s = mythos.step(s, "move:Harbor Diner")
        packet = mythos.gm_context(s)
        self.assertIn("eleanor", [x["id"] for x in packet["referee"]["participants"]])
        self.assertNotIn("secret", str(mythos.view(s)["contacts"]))

    def test_proposal_reuses_authority_and_replays(self):
        s = mythos.initial("boothbay", 42)
        request = {"action": "inspect_docks", "approach": "watch_patterns",
                   "intent": "Watch the fishermen and inspect the exposed waterfront."}
        result = mythos.step(s, "inspect_docks", request)
        self.assertEqual(result["turn"], 1)
        self.assertEqual(result["dxd"]["tests"][0]["gathered"]["attribute"][0]["name"], "REF")
        self.assertEqual(result["history"][-1], {"proposal": request})
        self.assertEqual(result["last_result"]["approach"], "watch_patterns")
        self.assertIn("dos", result["last_result"]["adjudication"])
        self.assertEqual(result["used"], ["inspect_docks"])
        mythos.verify(result)
        with self.assertRaises(ValueError):
            mythos.step(result, "inspect_docks", request)

    def test_invalid_proposals_leave_state_unchanged(self):
        s = mythos.initial("boothbay", 42)
        before = mythos.digest(s)
        request = {"action": "inspect_docks", "approach": "watch_patterns", "intent": "Look carefully."}
        for invalid in (dict(request, grant=["invented"]), dict(request, approach="invented"),
                        dict(request, action="read_journal"), dict(request, intent="")):
            with self.assertRaises(ValueError):
                mythos.step(s, "inspect_docks", invalid)
        self.assertEqual(mythos.digest(s), before)

    def test_proposal_revision_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "session.json"
            v = mythos.start("boothbay", path, 42)
            request = {"action": "inspect_docks", "approach": "watch_patterns",
                       "intent": "Inspect through patient observation."}
            with self.assertRaisesRegex(ValueError, "stale"):
                mythos.act(path, "inspect_docks", "stale", request)
            self.assertEqual(mythos.inspect(path), v)
            v = mythos.act(path, "inspect_docks", v["revision"], request)
            self.assertEqual(mythos.inspect(path), v)
