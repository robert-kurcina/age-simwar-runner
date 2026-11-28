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
            if not s["last_result"]["success"]:
                self.assertIsNone(s["ending"])
                self.assertIn("account_custody_declined", s["flags"])
                mythos.verify(s)
                continue
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
        self.assertEqual(t["result"]["tn"], 7)
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
            expected = dxd_conditions.capacities(pc["attributes"])
            expected["resilience"] += pc["skills"].get("Grit", 0)
            self.assertEqual(pc["concerns"]["capacity"], expected)
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
            if not choices:
                ref = mythos.gm_context(s)["referee"]
                offers = ref["local_capabilities"] + mythos.view(s).get("danger", [])
                self.assertTrue(offers, "Live session must have a playable opportunity")
                offer = offers[0]
                s = mythos.step(s, offer["action"], {"action": offer["action"],
                    "approach": offer["approach"], "intent": "Complete the remaining available activity."})
            elif not any(a["id"] == "observe" for a in choices):
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

    def test_action_clock_eligibility_uses_shared_pre_mark_snapshot(self):
        from age_runtime.mythos import events
        _, rules = mythos.load("boothbay")
        trigger = {"action": "observe", "marks": 1}
        first = {"name": "First", "source": "test", "segments": 1,
                 "triggers": [trigger], "grant": ["first_done"]}
        second = {"name": "Second", "source": "test", "segments": 1,
                  "triggers": [trigger], "requires_flags": ["first_done"],
                  "grant": ["second_done"]}
        for clocks in ({"first": first, "second": second},
                       {"second": second, "first": first}):
            with self.subTest(order=list(clocks)):
                state = mythos.initial("boothbay", 42)
                # Exercise the clock mechanism directly; the synthetic clock
                # configuration is not an authored Boothbay scenario.
                state["narrative_events"]["clocks"] = {
                    key: {"marks": 0, "resolved": False, "seconds": 0}
                    for key in clocks}
                cfg = dict(rules, event_clocks=clocks, encounter_table=[])
                events.complete_action(state, cfg, {"id": "observe"}, True, 0)
                self.assertIn("first_done", state["flags"])
                self.assertNotIn("second_done", state["flags"])
                events.complete_action(state, cfg, {"id": "observe"}, True, 0)
                self.assertIn("second_done", state["flags"])

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

    def test_independent_npc_native_test_uses_own_profile_and_replays(self):
        from age_runtime.core import dxd
        s = mythos.initial("boothbay", 42)
        for action in ("talk_eleanor", "visit_elias", "inspect_room", "speak_burroughs"):
            s = mythos.step(s, action)
        s = mythos.establish_step(s, {"details": [{"id": "inc:case", "kind": "object",
            "label": "Case", "description": "A mundane old case.", "basis": "His own possession",
            "custodian": "burroughs", "properties": {"appearance": "Faded initials"}}]})
        req = {"id": "evt:examine", "npc": "burroughs", "object": "inc:case",
               "basis": "He tries to decipher its faded markings."}
        scheduled = mythos.establish_step(s, {"npc_native_test": req})
        self.assertEqual(scheduled["time"], s["time"])
        self.assertNotIn("test", scheduled["timed_detail_events"][-1])
        with self.assertRaises(ValueError):
            mythos.establish_step(scheduled, {"npc_native_test": dict(req, id="evt:again")})
        elapsed = mythos.step(scheduled, "observe")
        event = elapsed["timed_detail_events"][-1]
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["work_seconds"], 600)
        self.assertEqual(event["test"]["inputs"]["dm"],
                         dxd.attribute_dm(elapsed["npcs"]["burroughs"]["dxd_attributes"]["INT"]) + 2)
        self.assertEqual(event["test"]["result"], dxd.test("42:npc-test:burroughs:inc:case", **event["test"]["inputs"]))
        self.assertEqual(elapsed["dxd"]["tests"], s["dxd"]["tests"])
        self.assertEqual(elapsed["dxd"]["favor"], s["dxd"]["favor"])
        self.assertEqual(elapsed["detail_changes"], s["detail_changes"])
        self.assertNotIn("timed_detail_events", mythos.view(elapsed))
        with self.assertRaises(ValueError):
            mythos.establish_step(elapsed, {"npc_native_test": dict(req, id="evt:retry")})
        mythos.verify(elapsed)
        with self.assertRaises(ValueError):
            mythos.establish_step(scheduled, {"npc_activity": {"npc": "burroughs",
                "mode": "rest", "safe": True, "minutes": 10, "basis": "He rests."}})
        interrupted = mythos.dialogue_step(scheduled, {"npc": "burroughs", "speaker": "pc",
            "claim": "Chief, may I speak with you?", "stance": "unstated", "intent": "unstated"})
        interrupted = mythos.step(interrupted, "observe")
        event = interrupted["timed_detail_events"][-1]
        self.assertEqual(event["status"], "interrupted")
        self.assertEqual(event["interruption"], "interaction")
        self.assertEqual(event["work_seconds"], 0)
        self.assertNotIn("test", event)
        self.assertNotIn("assessment", event)
        mythos.verify(interrupted)
        resume = {"operation": "resume", "id": "evt:examine", "npc": "burroughs", "basis": "He returns to the same examination."}
        resumed = mythos.establish_step(interrupted, {"npc_task": resume})
        resumed = mythos.step(resumed, "observe")
        event = resumed["timed_detail_events"][-1]
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["work_seconds"], 600)
        self.assertEqual(event["test"], elapsed["timed_detail_events"][-1]["test"])
        mythos.verify(resumed)
        cancelled = mythos.establish_step(interrupted, {"npc_task": dict(resume, operation="cancel")})
        with self.assertRaises(ValueError):
            mythos.establish_step(cancelled, {"npc_task": resume})
        mythos.verify(cancelled)
        changed = mythos.establish_step(interrupted, {"changes": [{"id": "inc:case",
            "property": "appearance", "before": "Faded initials", "after": "Obscured initials",
            "basis": "Established changed appearance"}]})
        with self.assertRaises(ValueError):
            mythos.establish_step(changed, {"npc_task": resume})
        mythos.verify(changed)

    def test_independent_npc_travel_reuses_route_and_time(self):
        import copy
        s = mythos.initial("boothbay", 42)
        for action in ("talk_eleanor", "visit_elias", "inspect_room", "speak_burroughs"):
            s = mythos.step(s, action)
        before = copy.deepcopy(s)
        req = {"npc": "burroughs", "destination": "Harbor Diner", "basis": "He visits the diner."}
        traveling = mythos.establish_step(s, {"npc_travel": req})
        self.assertEqual(s, before)
        self.assertEqual(traveling["time"], s["time"])
        self.assertEqual(traveling["npc_travel"][0]["route"]["seconds"], 300)
        self.assertEqual(traveling["npcs"]["burroughs"]["location"], "Harbor Docks")
        _, rules = mythos.load("boothbay")
        self.assertFalse(mythos.npc_available(traveling, rules, {"npc": "burroughs", "location": "Harbor Docks"}))
        with self.assertRaises(ValueError):
            mythos.establish_step(traveling, {"npc_travel": req})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_travel": dict(req, destination="Devil's Throat Sea Caves")})
        elapsed = mythos.step(traveling, "observe")
        self.assertEqual(elapsed["npc_travel"][0]["status"], "completed")
        self.assertEqual(elapsed["npc_travel"][0]["resolved_at"], traveling["npc_travel"][0]["due"])
        self.assertEqual(elapsed["npcs"]["burroughs"]["location"], "Harbor Diner")
        self.assertEqual(elapsed["location"], "Harbor Docks")
        self.assertNotIn("npc_travel", mythos.view(elapsed))
        mythos.verify(elapsed)

    def test_social_epistemic_hypotheses_revisions_and_reparation(self):
        from age_runtime.mythos import epistemic
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        def say(s, speaker, claim, **extra):
            return mythos.dialogue_step(s, {"npc": "eleanor", "speaker": speaker,
                "claim": claim, "stance": "unstated", "intent": "unstated", **extra})
        s = say(s, "pc", "Perhaps your brother left voluntarily.")
        hyp = {"id": "hyp:departure", "npc": "eleanor", "text": "Her brother left voluntarily.", "source": 1}
        s = mythos.establish_step(s, {"hypothesis": hyp})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"hypothesis": dict(hyp, id="hyp:remote", npc="elias")})
        s = say(s, "eleanor", "Perhaps he did leave of his own accord.", proposition="hyp:departure", asserts=True)
        s = say(s, "pc", "No, I have changed my mind.", proposition="hyp:departure", asserts=False, listener_stance="doubts")
        s = say(s, "pc", "He may have left voluntarily after all.", proposition="hyp:departure", asserts=True)
        req = {"npc": "eleanor", "proposition": "hyp:departure", "stance": "doubts", "asserts": True,
               "sources": [1, 3, 4], "basis": "The accounts conflict."}
        s = mythos.establish_step(s, {"belief_revision": req})
        p = next(p for p in epistemic.proposition_projection(s, mythos.load("boothbay")[1], {"eleanor", "elias"}) if p["id"] == "hyp:departure")
        self.assertFalse(p["established"])
        self.assertTrue(p["actors"]["eleanor"]["conflicting_accounts"])
        self.assertEqual(p["actors"]["eleanor"]["latest_stance"]["stance"], "doubts")
        self.assertNotIn("elias", p["actors"])
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"belief_revision": dict(req, npc="elias")})
        s = say(s, "pc", "You are a liar.")
        harm = {"npc": "eleanor", "claims": [5], "kind": "harm", "basis": "An actual personal insult."}
        s = mythos.establish_step(s, {"social_demeanor": harm})
        self.assertEqual(s["relationships"]["eleanor"], -1)
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"social_demeanor": harm})
        s = mythos.step(mythos.step(s, "move:Harbor Docks"), "move:Harbor Diner")
        s = say(s, "pc", "I was wrong to insult you. I apologize.")
        s = say(s, "eleanor", "I appreciate that, though I haven't forgotten.",
                reaction={"tension": "Some resentment remains."})
        s = mythos.establish_step(s, {"social_demeanor": {"npc": "eleanor", "claims": [6, 7],
            "kind": "reparation", "basis": "She acknowledges the sincere apology as meaningful reparation."}})
        self.assertEqual(s["relationships"]["eleanor"], 0)
        self.assertEqual(s["relationship_changes"][-1]["requested_delta"], 1)
        self.assertEqual(len(s["belief_revisions"]), 1)
        self.assertNotIn("dynamic_propositions", mythos.view(s))
        mythos.verify(s)

    def test_npc_agency_competing_objectives_and_independent_examination(self):
        from age_runtime.mythos import npc_agency
        from age_runtime.core import dxd
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.dialogue_step(s, {"npc": "eleanor", "speaker": "pc",
            "claim": "I am looking for your brother.", "stance": "unstated", "intent": "unstated"})
        goal = {"operation": "create", "id": "goal:brother", "npc": "eleanor",
                "goal": "Learn what happened to her brother.", "priority": "urgent",
                "intention": "Ask about the inquiries.", "basis": "Her established motivation",
                "sources": [{"kind": "claim", "id": 1}]}
        s = mythos.establish_step(s, {"npc_objective": goal})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_objective": dict(goal, id="goal:unknown", sources=[{"kind": "claim", "id": 99}])})
        s = mythos.establish_step(s, {"npc_objective": dict(goal, id="goal:work", goal="Keep the diner running.",
            priority="normal", intention="Attend to her work.", sources=[])})
        review = {k: v for k, v in goal.items() if k != "goal"}
        review.update(operation="review", status="deferred", priority="normal",
                      intention="Wait until her duties permit another conversation.")
        s = mythos.establish_step(s, {"npc_objective": review})
        self.assertEqual(npc_agency.project(s)["goal:brother"]["status"], "deferred")
        self.assertEqual(npc_agency.project(s)["goal:work"]["status"], "active")
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_objective": dict(review, status="achieved", sources=[])})
        s = mythos.establish_step(s, {"details": [{"id": "inc:tin", "kind": "object",
            "label": "Tin", "description": "An old tin.", "basis": "Her own possession",
            "custodian": "eleanor", "properties": {"appearance": "Faded initials"}}]})
        s = mythos.establish_step(s, {"npc_native_test": {"id": "evt:marks", "npc": "eleanor",
            "object": "inc:tin", "basis": "She examines the faint marking."}})
        s = mythos.step(s, "observe")
        event = s["timed_detail_events"][-1]
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["test"]["inputs"]["dm"], dxd.attribute_dm(s["npcs"]["eleanor"]["dxd_attributes"]["INT"]) + 1)
        self.assertEqual(event["test"]["inputs"]["favor"], 0)
        self.assertEqual(s["npcs"]["eleanor"]["favor"], 1)
        self.assertNotIn("npc_agency", mythos.view(s))
        mythos.verify(s)

    def test_npc_testimony_is_private_received_claim_not_direct_observation(self):
        import copy
        from age_runtime.mythos import epistemic
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.dialogue_step(s, {"npc": "eleanor", "speaker": "pc",
            "claim": "I am looking for your brother.", "stance": "unstated", "intent": "unstated"})
        req = {"speaker": "eleanor", "listener": "burroughs",
               "claim": "The newspaper man is looking for my brother.",
               "stance": "believes", "intent": "sincere", "listener_stance": "doubts",
               "source": {"kind": "claim", "id": 1}}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_testimony": req})
        for action in ("talk_eleanor", "visit_elias", "inspect_room", "speak_burroughs"):
            s = mythos.step(s, action)
        self.assertEqual(s["npcs"]["burroughs"]["location"], "Harbor Docks")
        s = mythos.establish_step(s, {"npc_travel": {"npc": "burroughs",
            "destination": "Harbor Diner", "basis": "He seeks Eleanor's account."}})
        self.assertEqual(s["npc_travel"][0]["status"], "traveling")
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_testimony": req})
        s = mythos.step(s, "observe")
        self.assertEqual(s["npc_travel"][0]["status"], "completed")
        self.assertEqual(s["npcs"]["burroughs"]["location"], "Harbor Diner")
        self.assertEqual(s["location"], "Harbor Docks")
        before = copy.deepcopy(s)
        after = mythos.establish_step(s, {"npc_testimony": req})
        self.assertEqual(s, before)
        self.assertEqual(after["time"], s["time"])
        self.assertEqual(after["flags"], s["flags"])
        self.assertEqual(after["relationships"], s["relationships"])
        self.assertEqual(after["action_observations"], [])
        self.assertEqual(epistemic.public_projection(after), epistemic.public_projection(before))
        self.assertEqual(epistemic.referee_projection(after, {"burroughs"})[-1]["listener_stance"], "doubts")
        mythos.verify(after)
        from age_runtime.core import dxd
        social = {"id": "social:account", "claim": after["dialogue"][-1]["id"],
                  "basis": "She tries to persuade him of the significance of her account."}
        judged = mythos.establish_step(after, {"npc_social_test": social})
        result = judged["npc_social_tests"][-1]
        self.assertEqual(result["result"], dxd.opposed("42:npc-social:eleanor:burroughs:claim:1", **result["inputs"]))
        self.assertEqual(judged["npcs"]["eleanor"]["favor"], 0)
        self.assertEqual(judged["npcs"]["burroughs"]["favor"], 0)
        self.assertEqual(judged["dxd"], after["dxd"])
        self.assertEqual(judged["dialogue"], after["dialogue"])
        self.assertEqual(judged["flags"], after["flags"])
        self.assertEqual(judged["relationships"], after["relationships"])
        self.assertNotIn("npc_social_tests", mythos.view(judged))
        with self.assertRaises(ValueError):
            mythos.establish_step(judged, {"npc_social_test": dict(social, id="social:retry")})
        mythos.verify(judged)
        # A private hypothesis may be transmitted, contradicted and relayed to the PC
        # without disclosing canonical facts or private source metadata.
        h = mythos.establish_step(after, {"hypothesis": {"id": "hyp:inquiry", "npc": "eleanor",
            "text": "The visitor is conducting a newspaper inquiry.", "source": 1}})
        h = mythos.dialogue_step(mythos.step(h, "move:Harbor Diner"), {"npc": "eleanor", "speaker": "eleanor",
            "claim": "You're investigating for the paper?", "stance": "doubts", "intent": "sincere",
            "proposition": "hyp:inquiry", "asserts": True})
        linked = dict(req, claim="He may be investigating for the newspaper.", source={"kind": "claim", "id": h["dialogue"][-1]["id"]})
        h = mythos.establish_step(h, {"npc_testimony": linked})
        with self.assertRaises(ValueError):
            mythos.establish_step(h, {"npc_testimony": dict(linked, asserts=False)})
        h = mythos.establish_step(h, {"npc_testimony": dict(linked, claim="He is not investigating for a newspaper.",
            asserts=False, intent="deceive", stance="believes")})
        cid = h["dialogue"][-1]["id"]
        h = mythos.dialogue_step(h, {"npc": "burroughs", "speaker": "burroughs",
            "claim": "Eleanor tells me this isn't a newspaper inquiry.", "stance": "doubts", "intent": "sincere",
            "proposition": "hyp:inquiry", "asserts": False, "relay": cid})
        self.assertNotIn("relay_source", epistemic.public_projection(h)[-1])
        self.assertEqual(h["dialogue"][-1]["relay_source"], cid)
        mythos.verify(h)
        self.assertEqual(epistemic.referee_projection(after, {"elias"}), [])
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"npc_testimony": req})
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"npc_testimony": dict(req, source={"kind": "claim", "id": 99})})

    def test_consequential_demeanor_is_attributed_bounded_and_persistent(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.establish_step(s, {"details": [{"id": "inc:cup", "kind": "object",
            "label": "Cup", "description": "Her brother's cup.", "basis": "Established possession",
            "custodian": "eleanor"}]})
        s = mythos.establish_step(s, {"transfers": [{"id": "inc:cup", "from": "eleanor", "to": "pc",
            "pc_authorization": "I accept.", "npc_consent": "Here.", "basis": "Voluntary transfer"}]})
        s = mythos.establish_step(s, {"object_action": {"id": "act:drop", "object": "inc:cup",
            "before": "intact", "outcome": "destroyed", "authorization": "I drop it deliberately.",
            "basis": "Certain breakage", "remnants": "Ceramic fragments"}})
        obs = {"id": "obs:cup", "npc": "eleanor", "action": "act:drop",
               "kind": "witnessed", "basis": "She observes the deliberate act."}
        req = {"npc": "eleanor", "observation": "obs:cup", "severity": "significant",
               "basis": "She regards the destruction of her cherished cup as a betrayal."}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"consequential_demeanor": req})
        discovered = mythos.establish_step(s, {"action_observation": dict(obs, kind="discovered",
            basis="She notices the fragments.")})
        with self.assertRaises(ValueError):
            mythos.establish_step(discovered, {"consequential_demeanor": req})
        seen = mythos.establish_step(s, {"action_observation": obs})
        before = copy.deepcopy(seen)
        after = mythos.establish_step(seen, {"consequential_demeanor": req})
        self.assertEqual(seen, before)
        self.assertEqual(after["relationships"]["eleanor"], -2)
        self.assertEqual(after["relationship_changes"][-1]["requested_delta"], -2)
        self.assertEqual(after["relationship_changes"][-1]["action"], "act:drop")
        self.assertEqual(after["npcs"], seen["npcs"])
        self.assertEqual(after["dxd"], seen["dxd"])
        self.assertEqual(after["time"], seen["time"])
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"consequential_demeanor": req})
        returned = mythos.step(mythos.step(after, "move:Harbor Docks"), "move:Harbor Diner")
        self.assertEqual(returned["relationships"]["eleanor"], -2)
        self.assertEqual(mythos.gm_context(returned)["referee"]["consequential_demeanor"]
                         ["eleanor"][0]["observation"], "obs:cup")
        self.assertNotIn("consequential_demeanor", mythos.view(returned))
        mythos.verify(returned)

    def test_integrated_eleanor_continuity_across_conflict_and_recovery(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")

        def say(state, speaker, claim, **extra):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": speaker,
                "claim": claim, "stance": "unstated", "intent": "unstated", **extra})

        s = say(s, "eleanor", "That was my brother's cup.",
                reaction={"attachment": "Her brother's cup is cherished.",
                          "significance": "The cup reminds her of her missing brother."})
        s = say(s, "pc", "Have you heard from your brother?")
        s = mythos.establish_step(s, {"details": [
            {"id": "inc:cup", "kind": "object", "label": "Cup", "description": "Her brother's ceramic cup.",
             "basis": "Established personal possession", "custodian": "eleanor"},
            {"id": "inc:tin", "kind": "object", "label": "Tin", "description": "A small tin.",
             "basis": "Established mundane possession", "custodian": "eleanor",
             "properties": {"condition": "Dusty"}}]})
        s = mythos.step(mythos.step(s, "move:Harbor Docks"), "move:Harbor Diner")
        s = say(s, "pc", "Any news about your brother today?")
        s = mythos.establish_step(s, {"behavior": {"id": "pat:questions", "npc": "eleanor",
            "kind": "recurring", "evidence": ["claim:2", "claim:3"],
            "interpretation": "He repeatedly asks about my brother."}})
        s = mythos.establish_step(s, {"expectation": {"operation": "create", "id": "exp:question",
            "npc": "eleanor", "pattern": "pat:questions",
            "expectation": "His next statement will concern my brother."}})
        s = mythos.establish_step(s, {"transfers": [{"id": "inc:cup", "from": "eleanor", "to": "pc",
            "pc_authorization": "I accept the cup.", "npc_consent": "Here, take it.",
            "basis": "Voluntary transfer"}]})
        s = mythos.establish_step(s, {"object_action": {"id": "act:drop", "object": "inc:cup",
            "before": "intact", "outcome": "destroyed", "authorization": "I drop the cup.",
            "basis": "Certain breakage on hard floor", "remnants": "Broken ceramic fragments"}})
        incident = s
        obs = {"id": "obs:cup", "npc": "eleanor", "action": "act:drop",
               "kind": "witnessed", "basis": "She sees the cup fall from his hand."}
        s = mythos.establish_step(s, {"action_observation": obs})
        episode = {"id": "emo:cup", "npc": "eleanor", "claim_ids": [],
            "observation": "obs:cup", "emotion": "Grief and anger", "intensity": "acute",
            "expression": "She stares at the fragments, speechless.",
            "cause": "Loss of her cherished cup", "stress": {"eleanor": "severe"}}
        s = mythos.establish_step(s, {"emotion": episode})
        s = say(s, "eleanor", "That was his cup!", reaction={"tension": "Resentment over its destruction."})
        s = say(s, "pc", "Just coffee, please.")
        s = mythos.establish_step(s, {"expectation": {"operation": "assess", "id": "exp:question",
            "npc": "eleanor", "outcome": "contradicted", "evidence": ["claim:5"],
            "interpretation": "He asks for coffee instead."}})
        s = mythos.establish_step(s, {"npc_activity": {"npc": "eleanor", "mode": "rest",
            "safe": True, "minutes": 30, "basis": "She takes a quiet break in safety."}})
        s = mythos.step(s, "move:Harbor Docks")
        s = mythos.step(s, "wait:30")
        self.assertIsNone(s["npcs"]["eleanor"]["activity_plan"])
        s = mythos.establish_step(s, {"npc_initiative": {"operation": "schedule", "id": "evt:tidy",
            "npc": "eleanor", "object": "inc:tin", "delay_minutes": 30,
            "basis": "She chooses to tidy her belongings after her break."}})
        for _ in range(3):
            s = mythos.step(s, "observe")
        s = mythos.step(s, "move:Harbor Diner")
        packet = mythos.gm_context(s)["referee"]
        self.assertEqual(s["npcs"]["eleanor"]["concerns"]["stress"], 0)
        self.assertEqual(packet["emotional_context"]["eleanor"]["last_episode"]["id"], "emo:cup")
        self.assertEqual(packet["relational_context"]["eleanor"]["current"]["attachment"]["claim_id"], 1)
        self.assertEqual(packet["relational_context"]["eleanor"]["current"]["tension"]["claim_id"], 4)
        self.assertEqual(packet["behavioral_context"]["eleanor"]["interpretations"][0]["id"], "pat:questions")
        self.assertEqual(packet["npc_expectations"]["eleanor"][0]["status"], "contradicted")
        self.assertEqual(packet["action_observations"]["eleanor"][0]["actor"], "pc")
        self.assertIn("competing motivations", packet["literary_synthesis"])
        entities = {e["id"]: e for e in mythos.view(s)["established_details"]}
        self.assertEqual(entities["inc:cup"]["lifecycle"], "destroyed")
        self.assertEqual(entities["inc:tin"]["properties"]["condition"], "Clean")
        self.assertEqual(s["timed_detail_events"][0]["status"], "completed")
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"emotion": dict(episode, id="emo:repeat")})
        mythos.verify(s)

        # Same physical outcome, different NPC epistemic history.
        unseen = mythos.step(mythos.step(incident, "move:Harbor Docks"), "move:Harbor Diner")
        unseen = mythos.establish_step(unseen, {"action_observation": dict(obs,
            kind="discovered", basis="She notices the fragments later.")})
        packet = mythos.gm_context(unseen)["referee"]
        self.assertIsNone(packet["action_observations"]["eleanor"][0]["actor"])
        self.assertNotIn("obs:cup", packet["behavioral_context"]["eleanor"]["evidence"])
        self.assertEqual(packet["behavioral_context"]["eleanor"]["interpretations"][0]["id"], "pat:questions")
        mythos.verify(unseen)

    def test_expectations_are_prospective_and_reassessed_from_new_evidence(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        def say(state, claim):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": "pc",
                "claim": claim, "stance": "unstated", "intent": "unstated"})
        s = say(s, "Any news about your brother?")
        s = mythos.step(mythos.step(s, "move:Harbor Docks"), "move:Harbor Diner")
        s = say(s, "Has your brother been found?")
        s = mythos.establish_step(s, {"behavior": {"id": "pat:questions", "npc": "eleanor",
            "kind": "recurring", "evidence": ["claim:1", "claim:2"],
            "interpretation": "He keeps asking about my brother."}})
        create = {"operation": "create", "id": "exp:question", "npc": "eleanor",
                  "pattern": "pat:questions", "expectation": "His next statement will concern my brother."}
        before = copy.deepcopy(s)
        pending = mythos.establish_step(s, {"expectation": create})
        self.assertEqual(s, before)
        with self.assertRaises(ValueError):
            mythos.establish_step(pending, {"expectation": dict(create, id="exp:duplicate")})
        assess = {"operation": "assess", "id": "exp:question", "npc": "eleanor",
                  "outcome": "contradicted", "evidence": ["claim:2"],
                  "interpretation": "His next statement concerns coffee instead."}
        with self.assertRaises(ValueError):
            mythos.establish_step(pending, {"expectation": assess})
        pending = say(pending, "Just coffee, please.")
        assess["evidence"] = ["claim:3"]
        resolved = mythos.establish_step(pending, {"expectation": assess})
        packet = mythos.gm_context(resolved)["referee"]
        result = packet["npc_expectations"]["eleanor"][0]
        self.assertEqual(result["status"], "contradicted")
        self.assertEqual(set(result["observed_basis"]), {"claim:1", "claim:2", "claim:3"})
        self.assertIn("competing motivations", packet["literary_synthesis"])
        self.assertNotIn("npc_expectations", mythos.view(resolved))
        for key in ("time", "turn", "dxd", "relationships", "npcs"):
            self.assertEqual(resolved[key], pending[key])
        with self.assertRaises(ValueError):
            mythos.establish_step(resolved, {"expectation": assess})
        mythos.verify(resolved)

    def test_observed_ordinary_routines_support_expectations(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        arrival = {"id": "routine:first", "npc": "eleanor", "kind": "arrival",
                   "basis": "She sees him enter."}
        s = mythos.establish_step(s, {"routine_observation": arrival})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"routine_observation": dict(arrival, id="routine:duplicate")})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"routine_observation": dict(arrival, id="routine:remote", npc="elias")})
        s = mythos.step(s, "buy_meal")
        meal = {"id": "routine:meal", "npc": "eleanor", "kind": "activity",
                "basis": "She served his meal and saw him rest."}
        s = mythos.establish_step(s, {"routine_observation": meal})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"routine_observation": dict(arrival, id="routine:late")})
        s = mythos.step(mythos.step(s, "move:Harbor Docks"), "move:Harbor Diner")
        s = mythos.establish_step(s, {"routine_observation": dict(arrival, id="routine:return")})
        s = mythos.step(s, "buy_meal")
        s = mythos.establish_step(s, {"routine_observation": dict(meal, id="routine:meal2")})
        s = mythos.establish_step(s, {"behavior": {"id": "pat:meals", "npc": "eleanor",
            "kind": "recurring", "evidence": ["routine:meal", "routine:meal2"],
            "interpretation": "He often eats at the diner."}})
        s = mythos.establish_step(s, {"expectation": {"operation": "create", "id": "exp:meal",
            "npc": "eleanor", "pattern": "pat:meals", "expectation": "He may order another meal."}})
        packet = mythos.gm_context(s)["referee"]
        self.assertEqual(packet["behavioral_context"]["eleanor"]["evidence"]["routine:meal"]["kind"], "activity")
        self.assertEqual(packet["npc_expectations"]["eleanor"][0]["status"], "pending")
        cues = packet["contextual_reminders"]["eleanor"]["observed_routines"]
        self.assertIn("routine:meal", {c["id"] for c in cues})
        self.assertIn("routine:meal2", {c["id"] for c in cues})
        self.assertNotIn("He often eats at the diner.", str(cues))
        self.assertNotIn("basis", cues[0])
        from age_runtime.mythos import reminders
        self.assertNotIn("elias", reminders.projection(s, {"elias"}))
        before = copy.deepcopy(s)
        reminders.projection(s, {"eleanor"})
        self.assertEqual(s, before)
        self.assertNotIn("routine_observations", mythos.view(s))
        self.assertNotIn("routine_source", mythos.view(s))
        mythos.verify(s)

    def test_behavioral_recognition_requires_observed_distinct_turns(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")

        def say(state, speaker, claim):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": speaker,
                "claim": claim, "stance": "unstated", "intent": "unstated"})

        s = say(s, "pc", "Have you heard anything about your brother?")
        s = say(s, "pc", "Any news from the docks?")
        s = say(s, "eleanor", "No news.")
        req = {"id": "pat:questions", "npc": "eleanor", "kind": "recurring",
               "evidence": ["claim:1", "claim:2"],
               "interpretation": "He often asks about my brother's disappearance."}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"behavior": req})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"behavior": dict(req, kind="salient", evidence=["claim:3"])})
        s = mythos.step(mythos.step(s, "move:Harbor Docks"), "move:Harbor Diner")
        s = say(s, "pc", "Have you heard from your brother today?")
        req["evidence"] = ["claim:1", "claim:4"]
        before = copy.deepcopy(s)
        after = mythos.establish_step(s, {"behavior": req})
        self.assertEqual(s, before)
        for key in ("time", "turn", "dxd", "relationships", "flags", "npcs"):
            self.assertEqual(after[key], s[key])
        packet = mythos.gm_context(after)["referee"]["behavioral_context"]["eleanor"]
        self.assertEqual(packet["observed_turns"], 2)
        self.assertEqual(packet["interpretations"][0]["id"], "pat:questions")
        self.assertNotIn("claim:3", packet["evidence"])
        self.assertNotIn("behavioral_recognition", mythos.view(after))
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"behavior": dict(req, id="pat:duplicate")})
        moved = mythos.step(after, "move:Harbor Docks")
        self.assertNotIn("eleanor", mythos.gm_context(moved)["referee"]["behavioral_context"])
        mythos.verify(moved)

    def test_action_observations_and_silent_duress(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.establish_step(s, {"details": [{"id": "inc:cup", "kind": "object",
            "label": "Cup", "description": "An old ceramic cup.", "basis": "Local object",
            "custodian": "eleanor"}]})
        s = mythos.establish_step(s, {"transfers": [{"id": "inc:cup", "from": "eleanor", "to": "pc",
            "pc_authorization": "I accept.", "npc_consent": "Take it.", "basis": "Voluntary transfer"}]})
        s = mythos.establish_step(s, {"object_action": {"id": "act:drop", "object": "inc:cup",
            "before": "intact", "outcome": "destroyed", "authorization": "I drop it.",
            "basis": "Certain breakage", "remnants": "Ceramic fragments"}})
        obs = {"id": "obs:cup", "npc": "eleanor", "action": "act:drop",
               "kind": "witnessed", "basis": "She saw the cup fall from the PC's hand."}
        self.assertEqual(mythos.gm_context(s)["referee"]["action_observations"]["eleanor"], [])
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"action_observation": dict(obs, npc="elias")})
        seen = mythos.establish_step(s, {"action_observation": obs})
        episode = {"id": "emo:silent", "npc": "eleanor", "claim_ids": [],
                   "observation": "obs:cup", "emotion": "Shock and grief",
                   "intensity": "acute", "expression": "She stares at the fragments.",
                   "cause": "Witnessed loss of a cherished object", "stress": {"eleanor": "severe"}}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"emotion": episode})
        after = mythos.establish_step(seen, {"emotion": episode})
        self.assertEqual(after["npcs"]["eleanor"]["concerns"]["stress"], 6)
        self.assertEqual(after["dialogue"], [])
        self.assertEqual(after["action_observations"][0]["actor"], "pc")
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"emotion": dict(episode, id="emo:again")})
        self.assertNotIn("action_observations", mythos.view(after))
        mythos.verify(after)
        moved = mythos.step(s, "move:Harbor Docks")
        returned = mythos.step(moved, "move:Harbor Diner")
        with self.assertRaises(ValueError):
            mythos.establish_step(returned, {"action_observation": obs})
        found = mythos.establish_step(returned, {"action_observation": dict(obs,
            kind="discovered", basis="She notices the fragments on the floor.")})
        self.assertIsNone(found["action_observations"][0]["actor"])
        with self.assertRaises(ValueError):
            mythos.establish_step(found, {"emotion": dict(episode, stress={"pc": "severe"})})
        found = mythos.establish_step(found, {"emotion": episode})
        self.assertEqual(found["npcs"]["eleanor"]["concerns"]["stress"], 6)
        mythos.verify(found)

    def test_certain_object_destruction_retains_identity_and_remnants(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.establish_step(s, {"details": [{"id": "inc:cup", "kind": "object",
            "label": "Cup", "description": "An old ceramic cup.", "basis": "Local mundane object",
            "custodian": "eleanor", "properties": {"condition": "Intact"}}]})
        req = {"id": "act:drop", "object": "inc:cup", "before": "intact", "outcome": "destroyed",
               "authorization": "I drop the cup onto the hard floor.",
               "basis": "Uncontested certain breakage", "remnants": "Broken ceramic fragments"}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"object_action": req})
        s = mythos.establish_step(s, {"transfers": [{"id": "inc:cup", "from": "eleanor", "to": "pc",
            "pc_authorization": "I accept the cup.", "npc_consent": "Here, take it.", "basis": "Voluntary transfer"}]})
        before = copy.deepcopy(s)
        after = mythos.establish_step(s, {"object_action": req})
        self.assertEqual(s, before)
        self.assertEqual(after["time"], s["time"])
        self.assertEqual(after["turn"], s["turn"])
        for key in ("flags", "inventory", "discoveries", "resources", "relationships", "dxd"):
            self.assertEqual(after[key], s[key])
        obj = next(e for e in mythos.view(after)["established_details"] if e["id"] == "inc:cup")
        self.assertEqual(obj["lifecycle"], "destroyed")
        self.assertIsNone(obj["custodian"])
        self.assertEqual(obj["properties"]["condition"], "Broken ceramic fragments")
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"object_action": dict(req, id="act:again")})
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"changes": [{"id": "inc:cup", "property": "condition",
                "before": "Broken ceramic fragments", "after": "Intact", "basis": "Unsupported restoration"}]})
        self.assertNotIn("object_actions", mythos.view(after))
        self.assertEqual(mythos.gm_context(after)["referee"]["object_actions"][0]["id"], "act:drop")
        moved = mythos.step(after, "move:Harbor Docks")
        self.assertFalse(any(e["id"] == "inc:cup" for e in mythos.view(moved)["established_details"]))
        returned = mythos.step(moved, "move:Harbor Diner")
        self.assertEqual(next(e for e in mythos.view(returned)["established_details"]
                              if e["id"] == "inc:cup")["lifecycle"], "destroyed")
        mythos.verify(returned)

    def test_npc_lifecycle_schedule_duress_sleep_and_remote_waking(self):
        from datetime import datetime, timedelta
        from age_runtime.core import dxd_conditions
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        schedule = {"operation": "schedule", "npc": "eleanor", "basis": "A reviewed daily work routine",
                    "windows": [{"start_minute": 490, "end_minute": 500,
                                 "mode": "low_energy", "label": "Quiet accounting"}]}
        s = mythos.establish_step(s, {"npc_lifecycle": schedule})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_lifecycle": dict(schedule, windows=schedule["windows"]*2)})
        scheduled = mythos.step(s, "move:Harbor Docks")
        self.assertEqual(mythos.gm_context(scheduled)["referee"]["npc_temporal"]["eleanor"]
                         ["current_occupation"]["label"], "Quiet accounting")
        scheduled = mythos.step(scheduled, "observe")
        self.assertEqual(scheduled["npcs"]["eleanor"]["activity"]["activity"], "low_energy")
        self.assertIsNone(mythos.gm_context(scheduled)["referee"]["npc_temporal"]["eleanor"]["current_occupation"])
        scheduled = mythos.step(scheduled, "observe")
        self.assertEqual(scheduled["npcs"]["eleanor"]["activity"]["activity"], "active")
        duress = mythos.establish_step(scheduled, {"npc_lifecycle": {
            "operation": "duress", "npc": "eleanor", "minutes": 20, "interval_minutes": 10,
            "basis": "Established prolonged disturbing surroundings."}})
        duress = mythos.step(mythos.step(duress, "observe"), "observe")
        self.assertEqual(duress["npcs"]["eleanor"]["concerns"]["stress"], 2)
        self.assertIsNone(duress["npcs"]["eleanor"]["activity_plan"])
        asleep = mythos.establish_step(duress, {"npc_lifecycle": {
            "operation": "sleep", "npc": "eleanor", "basis": "She retires to an established private resting place."}})
        self.assertEqual(asleep["time"], duress["time"])
        clock = asleep["npcs"]["eleanor"]["activity"]
        self.assertEqual(clock["status"], "asleep")
        self.assertEqual(clock["required_sleep_seconds"], dxd_conditions.required_sleep(
            asleep["npcs"]["eleanor"]["concerns"], asleep["npcs"]["eleanor"]["dxd_attributes"]))
        due = datetime.fromisoformat(asleep["time"]) + timedelta(seconds=clock["required_sleep_seconds"])
        _, rules = mythos.load("boothbay")
        self.assertFalse(mythos.npc_available(asleep, rules, {"npc": "eleanor", "location": "Harbor Diner"}))
        with self.assertRaises(ValueError):
            mythos.establish_step(asleep, {"npc_lifecycle": {"operation": "awaken", "npc": "eleanor", "basis": "Remote attempt."}})
        # Advance the protagonist independently; NPC sleep is on the same clock.
        awake = asleep
        while datetime.fromisoformat(awake["time"]) < due:
            awake = mythos.step(awake, "rest_room")
        self.assertEqual(awake["npcs"]["eleanor"]["activity"]["status"], "awake")
        self.assertIsNotNone(awake["npcs"]["eleanor"]["morning_until"])
        self.assertNotIn("npc_temporal", mythos.view(awake))
        mythos.verify(awake)

    def test_npc_temporal_recovery_uses_established_activity_and_shared_clock(self):
        import copy
        from age_runtime.core import dxd_conditions
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.dialogue_step(s, {"npc": "eleanor", "speaker": "eleanor",
                 "claim": "I need a quiet moment.", "stance": "unstated", "intent": "unstated"})
        s = mythos.establish_step(s, {"emotion": {
            "id": "emo:distress", "npc": "eleanor", "claim_ids": [1],
            "emotion": "Distress", "intensity": "acute", "expression": "Her voice falters.",
            "cause": "A significant emotional encounter", "stress": {"eleanor": "severe"}}})
        request = {"npc": "eleanor", "mode": "rest", "safe": True, "minutes": 10,
                   "basis": "She takes a quiet break from work in safety."}
        before = copy.deepcopy(s)
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_activity": dict(request, npc="elias")})
        planned = mythos.establish_step(s, {"npc_activity": request})
        self.assertEqual(s, before)
        self.assertEqual(planned["time"], s["time"])
        self.assertEqual(planned["npcs"]["eleanor"]["concerns"], s["npcs"]["eleanor"]["concerns"])
        with self.assertRaises(ValueError):
            mythos.establish_step(planned, {"npc_activity": request})
        moved = mythos.step(planned, "move:Harbor Docks")
        elapsed = mythos.step(moved, "observe")
        npc = elapsed["npcs"]["eleanor"]
        expected = max(0, 6 - npc["concerns"]["capacity"]["recovery_rate"])
        self.assertEqual(npc["concerns"]["stress"], expected)
        self.assertIsNone(npc["activity_plan"])
        for nid in elapsed["npcs"]:
            from datetime import datetime
            seconds = int((datetime.fromisoformat(elapsed["time"]) -
                           datetime.fromisoformat(s["time"])).total_seconds())
            self.assertEqual(elapsed["npcs"][nid]["activity"]["awake_seconds"],
                             s["npcs"][nid]["activity"]["awake_seconds"] + seconds)
        self.assertEqual(elapsed["emotional_episodes"], s["emotional_episodes"])
        baseline = mythos.step(mythos.step(s, "move:Harbor Docks"), "observe")
        self.assertEqual(baseline["npcs"]["eleanor"]["concerns"]["stress"], 6)
        interrupted = mythos.dialogue_step(planned, {"npc": "eleanor", "speaker": "pc",
            "claim": "One more question.", "stance": "unstated", "intent": "unstated"})
        self.assertIsNone(interrupted["npcs"]["eleanor"]["activity_plan"])
        mythos.verify(elapsed)
        mythos.verify(interrupted)
        self.assertNotIn("npc_temporal", mythos.view(elapsed))

    def test_contextual_reminders_are_shared_bounded_and_read_only(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")

        def say(state, speaker, claim, **extra):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": speaker,
                                               "claim": claim, "stance": "unstated",
                                               "intent": "unstated", **extra})

        s = say(s, "eleanor", "My brother used to sit here.",
                reaction={"significance": "Private emotional association"})
        s = say(s, "pc", "I will ask about him at the docks.")
        s = say(s, "eleanor", "Thank you for offering to ask.")
        s = mythos.establish_step(s, {"agreement": {
            "operation": "create", "id": "agr:ask", "kind": "commitment",
            "npc": "eleanor", "issuer": "pc", "terms": "Ask about her brother at the docks",
            "condition": None, "claim_ids": [2, 3]}})
        for n in range(8):
            s = say(s, "eleanor", "Ordinary exchange " + str(n))
        before = copy.deepcopy(s)
        packet = mythos.gm_context(s)["referee"]["contextual_reminders"]["eleanor"]
        self.assertEqual(s, before)
        self.assertEqual(len(packet["utterances"]), 5)
        self.assertEqual(packet["utterances"][0]["claim_id"], 1)
        self.assertEqual(packet["utterances"][-1]["claim_id"], 11)
        self.assertNotIn("Private emotional association", str(packet))
        self.assertEqual(packet["active_agreements"][0]["id"], "agr:ask")
        self.assertEqual(packet["last_shared_exchange"]["minutes_ago"], 0)
        self.assertNotIn("contextual_reminders", mythos.view(s))
        moved = mythos.step(s, "move:Harbor Docks")
        self.assertNotIn("eleanor", mythos.gm_context(moved)["referee"]["contextual_reminders"])
        returned = mythos.step(moved, "move:Harbor Diner")
        packet = mythos.gm_context(returned)["referee"]["contextual_reminders"]["eleanor"]
        self.assertGreater(packet["last_shared_exchange"]["minutes_ago"], 0)
        self.assertEqual(packet["active_agreements"][0]["id"], "agr:ask")
        returned = say(returned, "eleanor", "Never mind, you need not ask.")
        returned = mythos.establish_step(returned, {"agreement": {
            "operation": "resolve", "id": "agr:ask", "status": "released", "claim_ids": [12]}})
        self.assertEqual(mythos.gm_context(returned)["referee"]["contextual_reminders"]
                         ["eleanor"]["active_agreements"], [])
        mythos.verify(returned)

    def test_emotional_episode_native_stress_and_private_continuity(self):
        import copy
        from age_runtime.core import dxd_conditions
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        claim = {"npc": "eleanor", "speaker": "eleanor",
                 "claim": "What have you done?!", "stance": "unstated", "intent": "unstated"}
        episode = {"id": "emo:confrontation", "npc": "eleanor", "claim_ids": [1],
                   "emotion": "Anger and grief", "intensity": "acute",
                   "expression": "She shouts, then struggles to speak.",
                   "cause": "An emotionally significant interpersonal confrontation",
                   "stress": {"eleanor": "severe", "pc": "significant"}}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"emotion": episode})
        s = mythos.dialogue_step(s, claim)
        before = copy.deepcopy(s)
        after = mythos.establish_step(s, {"emotion": episode})
        expected_npc = copy.deepcopy(before["npcs"]["eleanor"]["concerns"])
        expected_pc = copy.deepcopy(before["dxd"]["concerns"])
        dxd_conditions.add(expected_npc, stress=6)
        dxd_conditions.add(expected_pc, stress=3)
        self.assertEqual(after["npcs"]["eleanor"]["concerns"], expected_npc)
        self.assertEqual(after["dxd"]["concerns"], expected_pc)
        self.assertEqual(s, before)
        for key in ("time", "turn", "flags", "inventory", "discoveries", "resources", "relationships"):
            self.assertEqual(after[key], before[key])
        self.assertNotIn("emotional_episodes", mythos.view(after))
        context = mythos.gm_context(after)["referee"]["emotional_context"]["eleanor"]
        self.assertEqual(context["last_episode"]["intensity"], "acute")
        self.assertEqual(context["degrees"], dxd_conditions.degrees(expected_npc))
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"emotion": dict(episode, id="emo:duplicate")})
        for bad in (dict(episode, id="emo:bad", stress={"elias": "severe"}),
                    dict(episode, id="emo:bad", stress={"pc": 100}),
                    dict(episode, id="emo:bad", pc_emotion="fear")):
            with self.assertRaises(ValueError):
                mythos.establish_step(after, {"emotion": bad})
        quieter = dict(episode, id="emo:quiet", emotion="Relief", intensity="subsiding",
                       expression="She lowers her voice.", stress={})
        after = mythos.establish_step(after, {"emotion": quieter})
        self.assertEqual(after["npcs"]["eleanor"]["concerns"], expected_npc)
        moved = mythos.step(after, "move:Harbor Docks")
        self.assertNotIn("eleanor", mythos.gm_context(moved)["referee"]["emotional_context"])
        returned = mythos.step(moved, "move:Harbor Diner")
        self.assertEqual(returned["npcs"]["eleanor"]["concerns"], expected_npc)
        self.assertEqual(mythos.gm_context(returned)["referee"]["emotional_context"]["eleanor"]
                         ["last_episode"]["emotion"], "Relief")
        mythos.verify(returned)

    def test_atomic_narrative_batch_commits_or_rejects_whole_exchange(self):
        import copy
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "session.json"
            v = mythos.start("boothbay", p, 42)
            v = mythos.act(p, "move:Harbor Diner", v["revision"])
            original = p.read_bytes()
            state = mythos.read(p)
            next_id = mythos.gm_context(state)["referee"]["next_dialogue_id"]
            cup = {"id": "inc:cup", "kind": "object", "label": "Cup",
                   "description": "Eleanor holds a ceramic cup.", "basis": "Mundane diner object",
                   "custodian": "eleanor"}
            ask = {"npc": "eleanor", "speaker": "pc", "claim": "May I examine your cup?",
                   "stance": "unstated", "intent": "unstated"}
            answer = {"npc": "eleanor", "speaker": "eleanor", "claim": "Certainly.",
                      "stance": "unstated", "intent": "unstated",
                      "reaction": {"emotion": "wistful", "significance": "The reporter asked before touching the cup."}}
            permission = {"operation": "create", "id": "agr:cup", "kind": "permission",
                          "npc": "eleanor", "issuer": "eleanor", "terms": "Examine the cup",
                          "condition": None, "claim_ids": [next_id, next_id + 1]}
            lock = {"id": "lock:cup", "permission": "agr:cup", "object": "inc:cup",
                    "basis": "Eleanor permits close examination of her cup"}
            operations = [{"establish": {"details": [cup]}}, {"dialogue": ask},
                          {"dialogue": answer}, {"establish": {"agreement": permission}},
                          {"establish": {"lock": lock}}]
            bad = copy.deepcopy(operations)
            bad[-1]["establish"]["lock"]["object"] = "inc:missing"
            with self.assertRaisesRegex(ValueError, "operation 5"):
                mythos.establish(p, {"operations": bad}, v["revision"])
            self.assertEqual(p.read_bytes(), original)
            for invalid in ([], [{"act": "observe"}], [{"establish": {"operations": operations}}]):
                with self.assertRaises(ValueError):
                    mythos.establish(p, {"operations": invalid}, v["revision"])
                self.assertEqual(p.read_bytes(), original)
            result = mythos.establish(p, {"operations": operations}, v["revision"])
            committed = mythos.read(p)
            self.assertIn("examine:lock:cup", {x["id"] for x in result["choices"]})
            for key in ("turn", "time", "flags", "inventory", "resources", "discoveries", "dxd", "npcs"):
                self.assertEqual(committed[key], state[key])
            self.assertEqual(len(committed["history"]), len(state["history"]) + len(operations))
            self.assertNotIn("npc_reaction", result["dialogue"][-1])
            self.assertEqual(committed["dialogue"][-1]["npc_reaction"], answer["reaction"])
            mythos.verify(committed)
            saved = p.read_bytes()
            with self.assertRaisesRegex(ValueError, "stale"):
                mythos.establish(p, {"operations": operations}, v["revision"])
            self.assertEqual(p.read_bytes(), saved)

    def test_dialogue_duplicate_check_handles_optional_metadata(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        request = {"npc": "eleanor", "speaker": "eleanor", "claim": "I remember.",
                   "stance": "unstated", "intent": "unstated"}
        s = mythos.dialogue_step(s, request)
        enriched = dict(request, reaction={"emotion": "sad"})
        after = mythos.dialogue_step(s, enriched)
        with self.assertRaises(ValueError):
            mythos.dialogue_step(after, enriched)
        mythos.verify(after)

    def test_independent_npc_initiative_remote_completion_and_cancellation(self):
        import copy
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.establish_step(s, {"details": [{"id": "inc:tin", "kind": "object",
            "label": "Tin", "description": "A small tin.", "basis": "Local mundane object",
            "custodian": "eleanor", "properties": {"condition": "Dusty"}}]})
        s = mythos.step(s, "move:Harbor Docks")
        req = {"operation": "schedule", "id": "evt:tidy", "npc": "eleanor",
               "object": "inc:tin", "delay_minutes": 10,
               "basis": "She chooses to tidy her own belongings."}
        before = copy.deepcopy(s)
        planned = mythos.establish_step(s, {"npc_initiative": req})
        self.assertEqual(s, before)
        self.assertEqual(planned["time"], s["time"])
        self.assertEqual(planned["detail_changes"], [])
        self.assertEqual(planned["agreement_history"], [])
        self.assertEqual(planned["timed_detail_events"][0]["status"], "scheduled")
        with self.assertRaises(ValueError):
            mythos.establish_step(planned, {"npc_initiative": dict(req, id="evt:again")})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"npc_initiative": dict(req, npc="elias")})
        self.assertNotIn("timed_detail_events", mythos.view(planned))
        elapsed = mythos.step(planned, "observe")
        self.assertEqual(elapsed["timed_detail_events"][0]["status"], "completed")
        self.assertEqual(elapsed["detail_changes"][0]["at"], planned["timed_detail_events"][0]["due"])
        returned = mythos.step(elapsed, "move:Harbor Diner")
        obj = next(e for e in mythos.view(returned)["established_details"] if e["id"] == "inc:tin")
        self.assertEqual(obj["properties"]["condition"], "Clean")
        self.assertEqual(len(returned["detail_changes"]), 1)
        mythos.verify(returned)
        cancelled = mythos.establish_step(planned, {"npc_initiative": {
            "operation": "cancel", "id": "evt:tidy", "npc": "eleanor",
            "basis": "She changes her mind."}})
        cancelled = mythos.step(cancelled, "observe")
        self.assertEqual(cancelled["timed_detail_events"][0]["status"], "cancelled")
        self.assertEqual(cancelled["detail_changes"], [])
        mythos.verify(cancelled)

    def test_timed_detail_event_resolves_once_at_native_boundary(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        cup = {"id": "inc:cup", "kind": "object", "label": "Cup",
               "description": "Eleanor holds a dusty ceramic cup.",
               "basis": "Mundane diner object", "custodian": "eleanor",
               "properties": {"condition": "Dusty"}}
        s = mythos.establish_step(s, {"details": [cup]})
        event = {"id": "evt:clean_cup", "object": "inc:cup", "permission": "agr:clean",
                 "delay_minutes": 10, "basis": "Eleanor agreed to clean the cup"}
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"event": event})

        def say(state, speaker, claim):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": speaker,
                                               "claim": claim, "stance": "unstated",
                                               "intent": "unstated"})

        s = say(s, "eleanor", "I'll clean it in ten minutes.")
        s = say(s, "pc", "Thank you.")
        s = mythos.establish_step(s, {"agreement": {
            "operation": "create", "id": "agr:clean", "kind": "commitment",
            "npc": "eleanor", "issuer": "eleanor", "terms": "Clean the cup in ten minutes",
            "condition": None, "claim_ids": [1, 2]}})
        before = mythos.digest(s)
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"event": dict(event, delay_minutes=11)})
        scheduled = mythos.establish_step(s, {"event": event})
        self.assertEqual(mythos.digest(s), before)
        self.assertEqual(scheduled["time"], s["time"])
        self.assertEqual(scheduled["detail_changes"], [])
        self.assertNotIn("timed_detail_events", mythos.view(scheduled))
        with self.assertRaises(ValueError):
            mythos.establish_step(scheduled, {"event": dict(event, id="evt:duplicate")})
        # A separate acknowledged commitment does not permit simultaneous
        # incompatible work by the same NPC.
        conflict = say(scheduled, "eleanor", "I'll also clean the tin.")
        conflict = say(conflict, "pc", "Thank you for that too.")
        conflict = mythos.establish_step(conflict, {"details": [{
            "id": "inc:tin", "kind": "object", "label": "Tin",
            "description": "A dusty tin.", "basis": "Mundane diner object",
            "custodian": "eleanor", "properties": {"condition": "Dusty"}}]})
        conflict = mythos.establish_step(conflict, {"agreement": {
            "operation": "create", "id": "agr:tin", "kind": "commitment",
            "npc": "eleanor", "issuer": "eleanor", "terms": "Clean the tin",
            "condition": None, "claim_ids": [3, 4]}})
        with self.assertRaisesRegex(ValueError, "conflicting pending NPC event"):
            mythos.establish_step(conflict, {"event": dict(
                event, id="evt:tin", object="inc:tin", permission="agr:tin")})
        mythos.verify(conflict)
        # Move away before the event is due, then cross its boundary remotely.
        moved = mythos.step(scheduled, "move:Harbor Docks")
        self.assertEqual(moved["timed_detail_events"][0]["status"], "scheduled")
        elapsed = mythos.step(moved, "observe")
        self.assertEqual(elapsed["timed_detail_events"][0]["status"], "completed")
        self.assertEqual(elapsed["detail_changes"][0]["at"], scheduled["timed_detail_events"][0]["due"])
        self.assertEqual(elapsed["detail_changes"][0]["after"], "Clean")
        returned = mythos.step(elapsed, "move:Harbor Diner")
        self.assertEqual(len(returned["detail_changes"]), 1)
        self.assertEqual(mythos.view(returned)["established_details"][0]["properties"]["condition"], "Clean")
        self.assertEqual(mythos.view(returned)["narrative_agreements"][0]["status"], "active")
        mythos.verify(returned)
        released = say(scheduled, "pc", "You need not clean it after all.")
        released = mythos.establish_step(released, {"agreement": {
            "operation": "resolve", "id": "agr:clean", "status": "released", "claim_ids": [3]}})
        released = mythos.step(released, "observe")
        self.assertEqual(released["timed_detail_events"][0]["status"], "prerequisite_unmet")
        self.assertEqual(released["detail_changes"], [])
        mythos.verify(released)

    def test_permission_key_controls_incidental_examination(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        cup = {"id": "inc:cup", "kind": "object", "label": "Cup",
               "description": "Eleanor holds a ceramic cup.",
               "basis": "Mundane diner object", "custodian": "eleanor"}
        s = mythos.establish_step(s, {"details": [cup]})
        lock = {"id": "lock:cup", "permission": "agr:cup", "object": "inc:cup",
                "basis": "Eleanor permits close examination of her cup"}
        action = "examine:lock:cup"

        def say(state, speaker, claim):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": speaker,
                                               "claim": claim, "stance": "unstated",
                                               "intent": "unstated"})

        def choices(state):
            return {x["id"] for x in mythos.view(state)["choices"]}

        self.assertNotIn(action, choices(s))
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"lock": lock})
        s = say(s, "pc", "May I examine the cup?")
        s = say(s, "eleanor", "Certainly, look as closely as you like.")
        grant = {"operation": "create", "id": "agr:cup", "kind": "permission",
                 "npc": "eleanor", "issuer": "eleanor", "terms": "Examine the cup",
                 "condition": None, "claim_ids": [1, 2]}
        conditional = mythos.establish_step(s, {"agreement": dict(grant, condition="Only later")})
        with self.assertRaises(ValueError):
            mythos.establish_step(conditional, {"lock": lock})
        s = mythos.establish_step(s, {"agreement": grant})
        s = mythos.establish_step(s, {"lock": lock})
        self.assertIn(action, choices(s))
        self.assertNotIn("basis", str(mythos.view(s)["choices"]))
        self.assertEqual(mythos.gm_context(s)["referee"]["narrative_locks"][0]["status"], "ready")
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"lock": dict(lock, id="lock:duplicate")})
        moved = mythos.step(s, "move:Harbor Docks")
        self.assertNotIn(action, choices(moved))
        with self.assertRaises(ValueError):
            mythos.step(moved, action)
        returned = mythos.step(moved, "move:Harbor Diner")
        self.assertIn(action, choices(returned))
        played = mythos.step(returned, action)
        self.assertEqual(played["last_result"]["action"], action)
        self.assertEqual(len(played["dxd"]["tests"]), len(returned["dxd"]["tests"]) + 1)
        self.assertEqual(played["discoveries"], returned["discoveries"])
        self.assertNotIn(action, choices(played))
        mythos.verify(played)
        revoked = say(returned, "eleanor", "I have changed my mind. Leave the cup alone.")
        revoked = mythos.establish_step(revoked, {"agreement": {
            "operation": "resolve", "id": "agr:cup", "status": "revoked", "claim_ids": [3]}})
        self.assertNotIn(action, choices(revoked))
        with self.assertRaises(ValueError):
            mythos.step(revoked, action)
        mythos.verify(revoked)
        renewed = say(revoked, "pc", "May I look at it now?")
        renewed = say(renewed, "eleanor", "Yes, you may.")
        renewed = mythos.establish_step(renewed, {"agreement": dict(
            grant, id="agr:renewed", claim_ids=[4, 5])})
        renewed = mythos.establish_step(renewed, {"lock": dict(
            lock, id="lock:renewed", permission="agr:renewed")})
        self.assertIn("examine:lock:renewed", choices(renewed))
        self.assertNotIn(action, choices(renewed))
        mythos.verify(renewed)
        # Revocation and renewal cannot reopen an already spent examination.
        spent = say(played, "eleanor", "Please stop looking at the cup.")
        spent = mythos.establish_step(spent, {"agreement": {
            "operation": "resolve", "id": "agr:cup", "status": "revoked", "claim_ids": [3]}})
        spent = say(spent, "pc", "May I look again?")
        spent = say(spent, "eleanor", "Yes.")
        spent = mythos.establish_step(spent, {"agreement": dict(
            grant, id="agr:renewed", claim_ids=[4, 5])})
        with self.assertRaises(ValueError):
            mythos.establish_step(spent, {"lock": dict(
                lock, id="lock:renewed", permission="agr:renewed")})
        mythos.verify(spent)

    def test_narrative_agreement_lifecycle_and_claim_provenance(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")

        def say(state, speaker, claim):
            return mythos.dialogue_step(state, {"npc": "eleanor", "speaker": speaker,
                                               "claim": claim, "stance": "unstated",
                                               "intent": "unstated"})

        permission = {"operation": "create", "id": "agr:cup_view", "kind": "permission",
                      "npc": "eleanor", "issuer": "eleanor", "terms": "Examine the cup",
                      "condition": "Keep it on the counter", "claim_ids": [1, 2]}
        s = say(s, "pc", "May I examine the cup without taking it away?")
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"agreement": permission})
        s = say(s, "eleanor", "Yes, provided you keep it on the counter.")
        before = mythos.digest(s)
        after = mythos.establish_step(s, {"agreement": permission})
        self.assertEqual(mythos.digest(s), before)
        for key in ("time", "turn", "flags", "discoveries", "inventory", "resources",
                    "relationships", "dxd", "npcs", "dialogue"):
            self.assertEqual(after[key], s[key])
        self.assertEqual(mythos.view(after)["narrative_agreements"][0]["status"], "active")
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"agreement": dict(permission, id="agr:duplicate")})
        remote = mythos.step(after, "move:Harbor Docks")
        self.assertEqual(mythos.gm_context(remote)["player_surface"]["narrative_agreements"][0]["condition"],
                         permission["condition"])
        revoke = {"operation": "resolve", "id": permission["id"], "status": "revoked",
                  "claim_ids": [3]}
        with self.assertRaises(ValueError):
            mythos.establish_step(remote, {"agreement": revoke})
        returned = mythos.step(remote, "move:Harbor Diner")
        returned = say(returned, "pc", "Are you withdrawing your permission?")
        with self.assertRaises(ValueError):
            mythos.establish_step(returned, {"agreement": revoke})
        returned = say(returned, "eleanor", "Yes. Please leave it alone.")
        returned = mythos.establish_step(returned, {"agreement": dict(revoke, claim_ids=[4])})
        self.assertEqual(mythos.view(returned)["narrative_agreements"][0]["status"], "revoked")
        returned = say(returned, "pc", "I promise to listen to you now.")
        returned = say(returned, "eleanor", "Thank you. That is all I ask.")
        promise = {"operation": "create", "id": "agr:listen", "kind": "commitment",
                   "npc": "eleanor", "issuer": "pc", "terms": "Listen to Eleanor",
                   "condition": None, "claim_ids": [5, 6]}
        returned = mythos.establish_step(returned, {"agreement": promise})
        returned = say(returned, "pc", "I have listened to your account.")
        fulfill = {"operation": "resolve", "id": promise["id"], "status": "fulfilled",
                   "claim_ids": [7]}
        with self.assertRaises(ValueError):
            mythos.establish_step(returned, {"agreement": fulfill})
        returned = say(returned, "eleanor", "You have heard me out.")
        returned = mythos.establish_step(returned, {"agreement": dict(fulfill, claim_ids=[7, 8])})
        self.assertEqual(mythos.view(returned)["narrative_agreements"][1]["status"], "fulfilled")
        mythos.verify(returned)
        import copy
        tampered = copy.deepcopy(returned)
        tampered["agreement_history"][0]["terms"] = "Altered permission"
        with self.assertRaises(ValueError):
            mythos.verify(tampered)

    def test_incidental_custody_travels_and_preserves_provenance(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        cup = {"id": "inc:cup", "kind": "object", "label": "Cup",
               "description": "Eleanor holds a ceramic cup.", "basis": "Ordinary diner object",
               "custodian": "eleanor", "properties": {"condition": "Chipped"}}
        bell = {"id": "inc:bell", "kind": "fixture", "label": "Bell",
                "description": "A bell hangs above the door.", "basis": "Ordinary fixture"}
        s = mythos.establish_step(s, {"details": [cup, bell]})
        give = {"id": "inc:cup", "from": "eleanor", "to": "pc",
                "pc_authorization": "I accept the cup.", "npc_consent": "Please keep it for me.",
                "basis": "Eleanor voluntarily entrusts the cup to the reporter."}
        before = mythos.digest(s)
        for bad in (dict(give, npc_consent=""), dict(give, pc_authorization=""),
                    dict(give, id="inc:bell"), dict(give, **{"from": "elias"}),
                    dict(give, to="elias"), dict(give, grant=["badge"])):
            with self.assertRaises(ValueError):
                mythos.establish_step(s, {"transfers": [bad]})
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"transfers": [give, give]})
        self.assertEqual(mythos.digest(s), before)
        after = mythos.establish_step(s, {"transfers": [give]})
        for key in ("time", "turn", "flags", "discoveries", "inventory", "resources",
                    "relationships", "dxd", "npcs", "established_details"):
            self.assertEqual(after[key], s[key])
        moved = mythos.step(after, "move:Harbor Docks")
        visible = mythos.view(moved)["established_details"]
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["custodian"], "pc")
        self.assertEqual(visible[0]["location"], "Harbor Docks")
        self.assertNotIn("custody_history", visible[0])
        back = dict(give, **{"from": "pc", "to": "eleanor",
                            "pc_authorization": "I return it.", "npc_consent": "Thank you."})
        with self.assertRaises(ValueError):
            mythos.establish_step(moved, {"transfers": [back]})
        returned = mythos.step(moved, "move:Harbor Diner")
        returned = mythos.establish_step(returned, {"transfers": [back]})
        private = next(x for x in mythos.gm_context(returned)["referee"]["established_details"]
                       if x["id"] == "inc:cup")
        self.assertEqual(private["custodian"], "eleanor")
        self.assertEqual(len(private["custody_history"]), 2)
        mythos.verify(returned)
        import copy
        tampered = copy.deepcopy(returned)
        tampered["custody_transfers"][0]["to"] = "elias"
        with self.assertRaises(ValueError):
            mythos.verify(tampered)

    def test_incidental_properties_preserve_history_and_require_current_value(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        cup = {"id": "inc:cup", "kind": "object", "label": "Cup",
               "description": "A ceramic cup stands on the shelf.",
               "basis": "Ordinary diner furnishing",
               "properties": {"condition": "Dusty", "placement": "Shelf"}}
        s = mythos.establish_step(s, {"details": [cup]})
        change = {"id": "inc:cup", "property": "condition", "before": "Dusty",
                  "after": "Clean", "basis": "Eleanor wipes the cup with her cloth"}
        placement = {"id": "inc:cup", "property": "placement", "before": "Shelf",
                     "after": "Counter", "basis": "Eleanor sets the cup on the counter"}
        before = mythos.digest(s)
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"changes": [change, dict(placement, before="Floor")]})
        self.assertEqual(mythos.digest(s), before)
        after = mythos.establish_step(s, {"changes": [change, placement]})
        self.assertEqual(mythos.digest(s), before)
        for key in ("time", "turn", "flags", "discoveries", "inventory", "resources",
                    "relationships", "dxd", "npcs", "established_details"):
            self.assertEqual(after[key], s[key])
        visible = mythos.view(after)["established_details"][0]
        self.assertEqual(visible["properties"], {"condition": "Clean", "placement": "Counter"})
        self.assertEqual(visible["description"], cup["description"])
        self.assertNotIn("property_history", visible)
        private = mythos.gm_context(after)["referee"]["established_details"][0]
        self.assertEqual(private["property_history"][0]["before"], "Dusty")
        self.assertEqual(private["property_history"][0]["basis"], change["basis"])
        for bad in (change, dict(change, before="Clean", after="Clean"),
                    dict(change, property="owner"), dict(change, id="badge"),
                    dict(change, grant=["badge"])):
            with self.assertRaises(ValueError):
                mythos.establish_step(after, {"changes": [bad]})
        moved = mythos.step(after, "move:Harbor Docks")
        with self.assertRaises(ValueError):
            mythos.establish_step(moved, {"changes": [dict(change, before="Clean")]})
        returned = mythos.step(moved, "move:Harbor Diner")
        returned = mythos.establish_step(returned, {"changes": [dict(change, before="Clean", after="Chipped",
                                               basis="Eleanor accidentally chips the rim on the counter")]})
        self.assertEqual(mythos.view(returned)["established_details"][0]["properties"]["condition"], "Chipped")
        self.assertEqual(len(returned["detail_changes"]), 3)
        mythos.verify(returned)
        import copy
        tampered = copy.deepcopy(returned)
        tampered["detail_changes"][0]["after"] = "Broken"
        with self.assertRaises(ValueError):
            mythos.verify(tampered)

    def test_mundane_establishment_is_atomic_local_and_replayable(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        bell = {"id": "inc:diner_bell", "kind": "fixture", "label": "Brass bell",
                "description": "A brass bell hangs above the entrance.",
                "basis": "Ordinary period-appropriate diner fixture"}
        cup = {"id": "inc:diner_cup", "kind": "object", "label": "Ceramic cup",
               "description": "A chipped ceramic cup stands on the shelf.",
               "basis": "Mundane diner furnishing"}
        before = mythos.digest(s)
        with self.assertRaises(ValueError):
            mythos.establish_step(s, {"details": [bell, dict(cup, grant=["badge"])]})
        self.assertEqual(mythos.digest(s), before)
        after = mythos.establish_step(s, {"details": [bell, cup]})
        self.assertEqual(mythos.digest(s), before)
        for key in ("time", "turn", "flags", "discoveries", "inventory", "resources", "relationships", "dxd", "npcs"):
            self.assertEqual(after[key], s[key])
        visible = mythos.view(after)["established_details"]
        self.assertEqual([x["id"] for x in visible], [bell["id"], cup["id"]])
        self.assertNotIn("basis", visible[0])
        self.assertEqual(mythos.gm_context(after)["referee"]["established_details"][0]["basis"], bell["basis"])
        for bad in (bell, dict(bell, id="inc:other", label=" BRASS  BELL "),
                    dict(cup, id="badge"), dict(cup, id="inc:secret", kind="clue"),
                    dict(cup, id="inc:other", location="Harbor Docks")):
            with self.assertRaises(ValueError):
                mythos.establish_step(after, {"details": [bad]})
        moved = mythos.step(after, "move:Harbor Docks")
        self.assertEqual(mythos.view(moved)["established_details"], [])
        self.assertEqual(mythos.gm_context(moved)["referee"]["established_details"], [])
        returned = mythos.step(moved, "move:Harbor Diner")
        self.assertEqual(mythos.view(returned)["established_details"], visible)
        mythos.verify(returned)
        import copy
        tampered = copy.deepcopy(returned)
        tampered["established_details"][0]["description"] = "An altered detail"
        with self.assertRaises(ValueError):
            mythos.verify(tampered)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "session.json"
            v = mythos.start("boothbay", p, 42)
            old = v["revision"]
            v = mythos.establish(p, {"details": [bell]}, old)
            self.assertEqual(mythos.inspect(p), v)
            with self.assertRaisesRegex(ValueError, "stale"):
                mythos.establish(p, {"details": [cup]}, old)

    def test_npc_relational_continuity_is_private_and_replayable(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        request = {"npc": "eleanor", "speaker": "pc", "claim": "I will listen before drawing conclusions.",
                   "stance": "unstated", "intent": "unstated",
                   "reaction": {"emotion": "Cautiously relieved", "intention": "Hear the reporter out",
                                "attachment": "Her brother", "tension": "Answers versus privacy",
                                "significance": "The reporter offered to listen without rushing to judgment."}}
        before = mythos.digest(s)
        after = mythos.dialogue_step(s, request)
        self.assertEqual(mythos.digest(s), before)
        for key in ("time", "turn", "flags", "discoveries", "relationships", "dxd", "npcs"):
            self.assertEqual(after[key], s[key])
        private = mythos.gm_context(after)["referee"]["relational_context"]["eleanor"]
        self.assertEqual(private["current"]["emotion"]["text"], "Cautiously relieved")
        self.assertEqual(private["experiences"][0]["claim_id"], 1)
        self.assertNotIn("npc_reaction", mythos.view(after)["dialogue"][0])
        self.assertNotIn("relational_context", mythos.view(after))
        for bad in ({"pc_emotion": "afraid"}, {"grant": "local_warning"}, {"emotion": ""},
                    {"intention": "x" * 241}, []):
            with self.assertRaises(ValueError):
                mythos.dialogue_step(after, dict(request, reaction=bad))
        remote = mythos.step(after, "move:Creek Inlet South")
        self.assertNotIn("eleanor", mythos.gm_context(remote)["referee"]["relational_context"])
        returned = mythos.step(remote, "move:Harbor Diner")
        reply = {"npc": "eleanor", "speaker": "eleanor", "claim": "Please do not make promises lightly.",
                 "stance": "unstated", "intent": "unstated",
                 "reaction": {"emotion": "Wary again", "significance": "She challenged the reporter's assurance."}}
        returned = mythos.dialogue_step(returned, reply)
        private = mythos.gm_context(returned)["referee"]["relational_context"]["eleanor"]
        self.assertEqual(private["current"]["emotion"]["claim_id"], 2)
        self.assertEqual(private["current"]["intention"]["claim_id"], 1)
        self.assertEqual([e["claim_id"] for e in private["experiences"]], [1, 2])
        self.assertEqual(returned["dialogue"][0]["npc_reaction"]["emotion"], "Cautiously relieved")
        mythos.verify(returned)
        import copy
        tampered = copy.deepcopy(returned)
        tampered["dialogue"][0]["npc_reaction"]["emotion"] = "Invented"
        with self.assertRaises(ValueError):
            mythos.verify(tampered)

    def test_proposition_access_and_belief_revision(self):
        s = mythos.initial("boothbay", 42)
        self.assertNotIn("propositions", mythos.view(s))
        s = mythos.step(s, "move:Harbor Diner")
        request = {"npc": "eleanor", "speaker": "eleanor", "claim": "I never reported my brother missing.",
                   "stance": "disbelieves", "intent": "deceive",
                   "proposition": "eleanor_disappearance", "asserts": False}
        with self.assertRaises(ValueError):
            mythos.dialogue_step(s, request)
        for seed in range(50):
            s = mythos.step(mythos.initial("boothbay", seed), "inspect_docks")
            if "badge" in s["flags"]:
                break
        else:
            self.fail("No earned badge")
        s = mythos.step(s, "move:Harbor Diner")
        tell = {"npc": "eleanor", "speaker": "pc", "claim": "I found a census badge.",
                "stance": "unstated", "intent": "unstated", "proposition": "badge_found",
                "asserts": True, "listener_stance": "doubts"}
        s = mythos.dialogue_step(s, tell)
        p = next(x for x in mythos.gm_context(s)["referee"]["propositions"] if x["id"] == "badge_found")
        self.assertTrue(p["established"])
        self.assertEqual(p["actors"]["eleanor"]["access"], [{"kind": "received_claim", "id": 1, "asserts": True}])
        self.assertEqual(p["actors"]["eleanor"]["latest_stance"]["stance"], "doubts")
        response = {"npc": "eleanor", "speaker": "eleanor", "claim": "I believe you found it.",
                    "stance": "believes", "intent": "sincere", "proposition": "badge_found", "asserts": True}
        s = mythos.dialogue_step(s, response)
        p = next(x for x in mythos.gm_context(s)["referee"]["propositions"] if x["id"] == "badge_found")
        self.assertEqual(p["actors"]["eleanor"]["latest_stance"]["stance"], "believes")
        self.assertIsNone(p["actors"]["pc"]["latest_stance"])
        self.assertNotIn("proposition", mythos.view(s)["dialogue"][-1])
        with self.assertRaises(ValueError):
            mythos.dialogue_step(s, dict(response, listener_stance="believes"))
        s = mythos.step(s, "move:Creek Inlet South")
        p = next(x for x in mythos.gm_context(s)["referee"]["propositions"] if x["id"] == "badge_found")
        self.assertNotIn("elias", p["actors"])
        self.assertNotIn("eleanor", p["actors"])
        mythos.verify(s)

    def test_epistemic_dialogue_replay_and_visibility(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        request = {"npc": "eleanor", "speaker": "eleanor", "claim": "I have never seen unusual growth.",
                   "stance": "disbelieves", "intent": "deceive"}
        before = mythos.digest(s)
        after = mythos.dialogue_step(s, request)
        self.assertEqual(mythos.digest(s), before)
        for key in ("time", "turn", "flags", "discoveries", "relationships", "dxd", "npcs"):
            self.assertEqual(after[key], s[key])
        public = mythos.view(after)["dialogue"][0]
        self.assertEqual(public["claim"], request["claim"])
        self.assertNotIn("speaker_intent", public)
        self.assertNotIn("speaker_stance", public)
        private = mythos.gm_context(after)["referee"]["dialogue_context"][0]
        self.assertEqual(private["speaker_intent"], "deceive")
        self.assertEqual(private["speaker_stance"], "disbelieves")
        for bad in (request, dict(request, speaker="pc"), dict(request, npc="elias"),
                    dict(request, grant=["water_warning"])):
            with self.assertRaises(ValueError):
                mythos.dialogue_step(after, bad)
        moved = mythos.step(after, "move:Harbor Docks")
        self.assertEqual(mythos.gm_context(moved)["referee"]["dialogue_context"], [])
        self.assertEqual(mythos.view(moved)["dialogue"], [public])
        returned = mythos.step(moved, "move:Harbor Diner")
        reply = {"npc": "eleanor", "speaker": "pc", "claim": "I will keep looking.",
                 "stance": "unstated", "intent": "unstated"}
        returned = mythos.dialogue_step(returned, reply)
        mythos.verify(returned)
        self.assertEqual(len(returned["dialogue"]), 2)
        import copy
        tampered = copy.deepcopy(returned)
        tampered["dialogue"][0]["claim"] = "Changed testimony."
        with self.assertRaises(ValueError):
            mythos.verify(tampered)

    def test_dialogue_context_survives_spent_topics_and_respects_availability(self):
        s = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        s = mythos.step(s, "talk_eleanor")
        packet = mythos.gm_context(s)
        eleanor = next(x for x in packet["referee"]["participants"] if x["id"] == "eleanor")
        self.assertTrue(eleanor["conversation_available"])
        self.assertEqual(eleanor["encounters"], 1)
        self.assertEqual(eleanor["last_contact"], s["time"])
        self.assertEqual(eleanor["demeanor"], s["relationships"]["eleanor"])
        self.assertNotIn("talk_eleanor", eleanor["local_actions"])
        self.assertNotIn("source_traits", str(mythos.view(s)["contacts"]))
        # Isolate exhaustion of every authored Eleanor action in projection.
        # This synthetic copy is not a played or replayable checkpoint.
        import copy
        exhausted = copy.deepcopy(s)
        _, rules = mythos.load("boothbay")
        exhausted["used"].extend(a["id"] for a in rules["actions"] if a.get("npc") == "eleanor")
        eleanor = next(x for x in mythos.gm_context(exhausted)["referee"]["participants"] if x["id"] == "eleanor")
        self.assertTrue(eleanor["conversation_available"])
        self.assertEqual(eleanor["local_actions"], [])
        remote = mythos.step(s, "move:Harbor Docks")
        self.assertNotIn("eleanor", [x["id"] for x in mythos.gm_context(remote)["referee"]["participants"]])
        inlet = mythos.step(remote, "move:Creek Inlet South")
        isolated = copy.deepcopy(inlet)
        isolated["flags"].append("elias_isolated")
        self.assertNotIn("elias", [x["id"] for x in mythos.gm_context(isolated)["referee"]["participants"]])
        ended = mythos.step(s, "depart")
        self.assertEqual(mythos.gm_context(ended)["referee"]["participants"], [])
        mythos.verify(ended)

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

    def test_native_interaction_modes(self):
        s = mythos.step(mythos.initial("boothbay", 42), "talk_eleanor")
        test = s["dxd"]["tests"][0]
        self.assertEqual(test["inputs"]["tn"], 7)
        self.assertNotIn("narrative", test["inputs"])
        self.assertIn("margin", test["result"])
        for action in ("visit_elias", "inspect_room"):
            s = mythos.step(s, action)
        s = mythos.step(s, "speak_burroughs")
        test = s["dxd"]["tests"][-1]
        self.assertEqual(test["inputs"]["active_raw"], s["dxd"]["attributes"]["PRE"])
        self.assertEqual(test["inputs"]["target_raw"], s["npcs"]["burroughs"]["dxd_attributes"]["INT"])
        self.assertIsNotNone(test["result"]["opponent"])
        mythos.verify(s)

    def test_eleanor_commitments_have_consequential_outcomes(self):
        # Isolate the authored stakes from the evidence-route RNG. Exercise
        # real Tests and state effects for each outcome, not mocked dice.
        _, rules = mythos.load("boothbay")
        for action_id, success_flag, refusal_flag, prerequisites in (
            ("warn_eleanor", "local_warning", "warning_declined",
             ["water_warning", "tide_clue"]),
            ("warn_from_ecology", "local_warning", "warning_declined",
             ["water_risk_known", "ecological_tide_pattern"]),
            ("leave_copy", "account_entrusted", "account_custody_declined",
             ["written_account", "eleanor_account"]),
        ):
            seen = set()
            for seed in range(200):
                s = mythos.initial("boothbay", seed)
                s["flags"].extend(prerequisites)
                after = mythos.step(s, action_id)
                passed = after["last_result"]["success"]
                seen.add(passed)
                self.assertEqual(success_flag in after["flags"], passed)
                self.assertEqual(refusal_flag in after["flags"], not passed)
                if action_id == "leave_copy":
                    self.assertEqual(after["ending"] is not None, passed)
                    if not passed:
                        self.assertIn("written_account", after["flags"])
                        self.assertIn("depart", [a["id"] for a in mythos.options(after, rules)])
                else:
                    self.assertEqual(after["containment"], 2 if passed else 0)
                    self.assertNotIn("warning_distributed", after["flags"])
                self.assertNotIn(action_id, [a["id"] for a in mythos.options(after, rules)])
                if len(seen) == 2:
                    break
            self.assertEqual(seen, {True, False}, action_id)

    def test_warning_reconsideration_requires_new_evidence(self):
        from age_runtime.mythos import continuity
        _, rules = mythos.load("boothbay")
        first = next(a for a in rules["actions"] if a["id"] == "warn_eleanor")
        alternate = next(a for a in rules["actions"] if a["id"] == "warn_from_ecology")
        for seed in range(200):
            s = mythos.initial("boothbay", seed)
            s["flags"].extend(["water_warning", "tide_clue"])
            after = mythos.step(s, first["id"])
            if not after["last_result"]["success"]:
                break
        else:
            self.fail("No warning refusal")
        self.assertFalse(continuity.reconsideration_allowed(after, alternate))
        self.assertNotIn(alternate["id"], [a["id"] for a in mythos.options(after, rules)])
        after["flags"].append("unrelated_evidence")
        self.assertFalse(continuity.reconsideration_allowed(after, alternate))
        after["flags"].append("water_risk_known")
        self.assertTrue(continuity.reconsideration_allowed(after, alternate))
        self.assertIn(alternate["id"], [a["id"] for a in mythos.options(after, rules)])
        self.assertNotIn(first["id"], [a["id"] for a in mythos.options(after, rules)])
        snapshot = next(x["refusal_context"] for x in after["dxd"]["tests"] if "refusal_context" in x)
        snapshot["evidence"].append("water_risk_known")
        self.assertFalse(continuity.reconsideration_allowed(after, alternate))

    def test_earned_warning_agreement_and_confirmation_replay(self):
        # The friendly testimony route is not a credible forced-refusal fixture.
        _, rules = mythos.load("boothbay")
        def legal(s, action):
            return any(a["id"] == action for a in mythos.options(s, rules))
        for seed in range(100):
            s = mythos.initial("boothbay", seed)
            for action, flag in (
                ("talk_eleanor", "eleanor_account"),
                ("follow_eleanor", "water_warning"),
                ("visit_elias", "journal"),
                ("read_journal", "tide_clue"),
                ("warn_eleanor", "local_warning"),
            ):
                if not legal(s, action):
                    break
                s = mythos.step(s, action)
                if flag not in s["flags"]:
                    break
            else:
                self.assertEqual(s["containment"], 2)
                self.assertNotIn("warning_distributed", s["flags"])
                for _ in range(6):
                    s = mythos.step(s, "observe")
                self.assertIn("warning_distributed", s["flags"])
                self.assertTrue(legal(s, "confirm_precaution"))
                s = mythos.step(s, "confirm_precaution")
                self.assertIn("warning_confirmed", s["flags"])
                self.assertEqual(s["containment"], 3)
                s = mythos.step(s, "depart")
                mythos.verify(s)
                break
        else:
            self.fail("No earned warning agreement")

    def test_earned_ecological_route_after_elias_withdraws(self):
        # No testimony, journal, badge, or paperwork is required. Use real
        # time, encounters, travel, Tests, and the original deadline.
        _, rules = mythos.load("boothbay")
        def legal(s, action):
            return any(a["id"] == action for a in mythos.options(s, rules))
        for seed in range(100):
            s = mythos.step(mythos.initial("boothbay", seed), "clear_dock_obstruction")
            if "dock_access" not in s["flags"]:
                continue
            s = mythos.step(s, "compare_almanac")
            s = mythos.step(s, "move:Creek Inlet South")
            for _ in range(36):
                if legal(s, "trace_filaments"):
                    break
                s = mythos.step(s, "observe")
            if not legal(s, "trace_filaments"):
                continue
            s = mythos.step(s, "trace_filaments")
            # Sleep in a normal paid room and let the calendar advance.
            s = mythos.step(s, "move:Sailor's Rest Boarding House")
            for _ in range(3):
                if "elias_isolated" in s["flags"]:
                    break
                s = mythos.step(s, "sleep_room")
            if "elias_isolated" not in s["flags"] or not legal(s, "inspect_inlet_pattern"):
                continue
            self.assertFalse(legal(s, "visit_elias"))
            s = mythos.step(s, "inspect_inlet_pattern")
            if "ecological_tide_pattern" not in s["flags"]:
                continue
            self.assertFalse(set(s["flags"]) & {"journal", "tide_clue", "water_warning", "badge", "paperwork"})
            tide = next(x for x in mythos.gm_context(s)["referee"]["narrative_functions"] if x["id"] == "tide_evidence")
            self.assertTrue(tide["established"])
            self.assertEqual(tide["carriers"][0]["status"], "blocked")
            self.assertTrue(legal(s, "warn_from_ecology"))
            self.assertTrue(legal(s, "report"))
            s = mythos.step(s, "report")
            self.assertIn("written_account", s["flags"])
            s = mythos.step(s, "depart")
            self.assertIsNotNone(s["ending"])
            mythos.verify(s)
            break
        else:
            self.fail("No independent ecological evidence route after withdrawal")

    def test_earned_report_preparation_and_departure_replay(self):
        _, rules = mythos.load("boothbay")
        def legal(s, action):
            return any(a["id"] == action for a in mythos.options(s, rules))
        for seed in range(100):
            s = mythos.step(mythos.initial("boothbay", seed), "talk_eleanor")
            s = mythos.step(s, "inspect_docks")
            if not legal(s, "report"):
                continue
            s = mythos.step(s, "move:Creek Inlet South")
            s = mythos.step(s, "move:Lighthouse (Western Point)")
            request = {"action": "local:compose_notes:Lighthouse (Western Point)",
                       "approach": "compose_notes",
                       "intent": "Organize the evidence for my written account."}
            before = list(s["discoveries"])
            s = mythos.step(s, request["action"], request)
            self.assertEqual(s["discoveries"], before)
            if not s["local_records"][-1]["passed"]:
                continue
            choice = next(a for a in mythos.view(s)["choices"] if a["id"] == "report")
            self.assertEqual(choice["seconds"], 2400)
            s = mythos.step(s, "report")
            self.assertIn("written_account", s["flags"])
            self.assertEqual(s["last_result"]["preparation_saved_seconds"], 1200)
            s = mythos.step(s, "leave_copy")
            if not s["last_result"]["success"]:
                self.assertIsNone(s["ending"])
                self.assertIn("written_account", s["flags"])
                s = mythos.step(s, "depart")
            self.assertIsNotNone(s["ending"])
            mythos.verify(s)
            break
        else:
            self.fail("No earned prepared report route")

    def test_warning_confirmation_has_bounded_followthrough(self):
        # Provisional scenario payoff: confirmation follows an independently
        # resolved distribution clock, not the player's initial promise.
        import copy
        _, rules = mythos.load("boothbay")
        action = next(a for a in rules["actions"] if a["id"] == "confirm_precaution")
        self.assertEqual(action["requires_flags"], ["local_warning", "warning_distributed"])
        self.assertEqual(action["success"], {"containment": 1})
        s = mythos.initial("boothbay", 42)
        s["flags"].extend(["local_warning", "warning_distributed"])
        before = s["containment"]
        after = mythos.step(s, "confirm_precaution")
        self.assertEqual(after["containment"], before + 1)
        self.assertIn("warning_confirmed", after["flags"])
        self.assertNotIn("people_safe", after["flags"])
        self.assertNotIn("confirm_precaution", [a["id"] for a in mythos.options(after, rules)])

    def test_local_proposal_creates_record_not_clue(self):
        s = mythos.initial("boothbay", 42)
        request = {"action": "local:survey:Harbor Docks", "approach": "survey",
                   "intent": "Survey the waterfront from a safe distance."}
        self.assertNotIn(request["action"], [a["id"] for a in mythos.view(s)["choices"]])
        self.assertIn(request["action"], [a["action"] for a in mythos.gm_context(s)["referee"]["local_capabilities"]])
        after = mythos.step(s, request["action"], request)
        self.assertEqual(after["time"], "1927-10-13T08:10:00")
        self.assertEqual(after["discoveries"], s["discoveries"])
        self.assertEqual(after["local_records"][0]["kind"], "survey")
        mythos.verify(after)
        with self.assertRaises(ValueError):
            mythos.step(after, request["action"], request)
        with self.assertRaises(ValueError):
            mythos.step(s, "local:survey:Harbor Diner", dict(request, action="local:survey:Harbor Diner"))

    def test_local_survey_saves_time_without_granting_evidence(self):
        request = {"action": "local:survey:Harbor Docks", "approach": "survey",
                   "intent": "Survey the waterfront before examining it."}
        for seed in range(100):
            s = mythos.initial("boothbay", seed)
            after = mythos.step(s, request["action"], request)
            if after["local_records"][-1]["passed"]:
                break
        else:
            self.fail("No successful survey")
        self.assertEqual(after["discoveries"], s["discoveries"])
        choice = next(a for a in mythos.view(after)["choices"] if a["id"] == "inspect_docks")
        self.assertEqual(choice["seconds"], 2400)
        self.assertEqual(choice["preparation_saved_seconds"], 1200)
        finished = mythos.step(after, "inspect_docks")
        self.assertEqual(finished["time"], "1927-10-13T08:50:00")
        self.assertEqual(finished["last_result"]["preparation_saved_seconds"], 1200)
        mythos.verify(finished)

    def test_preparation_is_scoped_to_success_location_and_evidence(self):
        from age_runtime.mythos import proposals
        _, rules = mythos.load("boothbay")
        report = next(a for a in rules["actions"] if a["id"] == "report")
        s = mythos.initial("boothbay", 42)
        s["local_records"] = [{"kind": "compose_notes", "target": report["location"],
                               "passed": True, "evidence_count": 1}]
        self.assertEqual(proposals.prepared_duration(s, report, 3600), (3600, 0))
        s["local_records"][0]["evidence_count"] = 2
        self.assertEqual(proposals.prepared_duration(s, report, 3600), (2400, 1200))
        s["local_records"][0]["passed"] = False
        self.assertEqual(proposals.prepared_duration(s, report, 3600), (3600, 0))
        s["local_records"][0].update(passed=True, target="Harbor Docks")
        self.assertEqual(proposals.prepared_duration(s, report, 3600), (3600, 0))

    def test_local_rapport_requires_contact(self):
        s = mythos.initial("boothbay", 42)
        request = {"action": "local:build_rapport:eleanor", "approach": "build_rapport",
                   "intent": "Introduce myself and establish rapport."}
        with self.assertRaises(ValueError):
            mythos.step(s, request["action"], request)
        s = mythos.step(s, "talk_eleanor")
        s = mythos.step(s, request["action"], request)
        self.assertEqual(s["local_records"][-1]["target"], "eleanor")
        mythos.verify(s)

    def test_danger_beat_is_local_and_replayable(self):
        from age_runtime.mythos import beats
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        req = {"action": "beat:inlet_withdrawal", "approach": "careful_footing",
               "intent": "Retreat along the dry margin."}
        with self.assertRaises(ValueError):
            mythos.step(s, req["action"], req)
        # Obtain the existing ecological encounter by ordinary exposed activity.
        for seed in range(100):
            s = mythos.step(mythos.initial("boothbay", seed), "move:Creek Inlet South")
            for _ in range(18):
                if "filament_anomaly" in s["flags"]:
                    break
                s = mythos.step(s, "observe")
            if "filament_anomaly" in s["flags"]:
                break
        else:
            self.fail("No filament encounter")
        self.assertTrue(beats.available(s, rules))
        prior = s["pacing"]["narrative_beats"]
        after = mythos.step(s, req["action"], req)
        self.assertEqual(after["pacing"]["narrative_beats"], prior + 1)
        self.assertIn("inlet_withdrawal", after["flags"])
        self.assertEqual(after["location"], s["location"])
        self.assertEqual(after["discoveries"], s["discoveries"])
        with self.assertRaises(ValueError):
            mythos.step(after, req["action"], req)
        mythos.verify(after)

    def test_continuity_carrier_loss_and_independent_route(self):
        from age_runtime.mythos import continuity
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        self.assertNotIn("narrative_functions", mythos.view(s))
        self.assertTrue(any(a["id"] == "visit_elias" for a in mythos.options(s, rules)))
        # Advance normally, without obtaining journal access.
        mythos.verify(s)
        from datetime import datetime
        s["time"] = "1927-10-14T06:00:00"
        mythos.advance_events(s, rules, datetime.fromisoformat(s["time"]))
        self.assertIn("elias_isolated", s["flags"])
        self.assertFalse(any(a["id"] == "visit_elias" for a in mythos.options(s, rules)))
        packet = mythos.gm_context(s)
        tide = next(x for x in packet["referee"]["narrative_functions"] if x["id"] == "tide_evidence")
        self.assertFalse(tide["established"])
        self.assertEqual(tide["carriers"][0]["status"], "blocked")
        self.assertEqual(tide["carriers"][1]["status"], "conditional")
        with self.assertRaises(ValueError):
            mythos.step(s, "visit_elias")
        # Model a previously granted access and independent evidence as
        # isolated projection tests; do not mistake synthetic state for replay.
        s["flags"].append("journal")
        tide = continuity.projection(s, rules, mythos.options(s, rules))[0]
        self.assertNotEqual(tide["carriers"][0]["status"], "blocked")
        s["flags"].extend(["water_risk_known", "tide_window_known"])
        self.assertTrue(any(a["id"] == "inspect_inlet_pattern" for a in mythos.options(s, rules)))

    def test_continuity_preserves_established_evidence(self):
        from age_runtime.mythos import continuity
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        s["flags"].extend(["journal", "tide_clue", "elias_isolated"])
        tide = continuity.projection(s, rules, mythos.options(s, rules))[0]
        self.assertTrue(tide["established"])
        self.assertFalse(tide["no_immediate_route"])

    def test_emotional_commitment_authorized_and_replayable(self):
        s = mythos.step(mythos.initial("boothbay", 42), "talk_eleanor")
        request = {"action": "local:build_rapport:eleanor", "approach": "build_rapport",
                   "intent": "Build rapport with Eleanor."}
        commitment = {"context": "eleanor", "level": 1,
                      "vignette": "I feel a surge of concern and my hands tremble."}
        before = s["dxd"]["concerns"].copy()
        after = mythos.step(s, request["action"], request, commitment)
        pc = after["dxd"]
        entry = pc["commitments"][0]
        self.assertEqual(entry["context"], "eleanor")
        self.assertEqual(pc["tests"][-1]["components"]["emotional_commitment"], 1)
        self.assertEqual(pc["concerns"]["min_stress"], before.get("min_stress", 0) + 1)
        self.assertGreaterEqual(pc["concerns"]["fatigue"], before["fatigue"] + 1)
        self.assertGreaterEqual(pc["concerns"]["weariness"], before["weariness"] + 1)
        self.assertIn(entry["stress_cost"], range(1, 7))
        self.assertEqual(after, mythos.step(s, request["action"], request, commitment))
        mythos.verify(after)
        with self.assertRaises(ValueError):
            mythos.step(s, request["action"], request, dict(commitment, level=2))
        with self.assertRaises(ValueError):
            mythos.step(s, request["action"], request, dict(commitment, context="elias"))
        from age_runtime.core import dxd_commitment
        self.assertEqual(dxd_commitment.modifier(pc, {"npc": "eleanor"}), -1)
        self.assertEqual(dxd_commitment.modifier(pc, {"npc": "elias"}), 0)
        self.assertFalse(dxd_commitment.eligible(after, {"emotional_commitment": True},
                         {"npc": "eleanor", "location": after["location"], "test": {"interaction": "ordinary"}}))
        after["dxd"]["commitments"][0]["stress_cost"] += 1
        with self.assertRaises(ValueError):
            mythos.verify(after)

    def test_emotional_commitment_no_unestablished_context(self):
        s = mythos.initial("boothbay", 42)
        with self.assertRaises(ValueError):
            mythos.step(s, "talk_eleanor", commitment={"context": "eleanor", "level": 1,
                         "vignette": "I feel concern and my hands tremble."})
        self.assertEqual(s["dxd"]["commitments"], [])
        mythos.verify(s)

    def test_fear_native_character_profiles(self):
        s = mythos.initial("boothbay", 42)
        pc = s["dxd"]
        self.assertEqual(len(s["character_profiles"]), 6)
        self.assertEqual(pc["skills"]["Investigate"], 2)
        self.assertEqual(pc["skills"]["Persuade"], 2)
        self.assertIn("[Addict > Drunkard]", pc["traits"])
        self.assertEqual(pc["concerns"]["capacity"]["resilience"],
                         3 + 2 * pc["attributes"]["POW"] // 3 + pc["skills"]["Grit"])
        self.assertEqual(s["npcs"]["elias"]["skills"]["Fishing"], 2)
        self.assertNotIn("character_profiles", mythos.view(s))
        mythos.verify(s)

    def test_contextual_emotional_and_narrative_modifiers(self):
        from age_runtime.core import dxd_context
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        a = {"id": "context_test", "npc": "eleanor",
             "test": {"attribute": "PRE", "skill": "Persuade", "interaction": "ordinary",
                      "tn": 7, "significance": "minor", "context_tags": ["event:war"]}}
        self.assertEqual(dxd_context.effects(s, a, a["test"])[0][0]["penalty"], 1)
        self.assertEqual(dxd_context.effects(s, a, dict(a["test"], context_tags=[]))[0], [])
        mythos.resolve_dxd(s, rules, a)
        self.assertEqual(s["dxd"]["tests"][-1]["contextual"][0]["penalty"], 1)
        self.assertEqual(dxd_context.effects(s, a, a["test"])[0], [])
        # Isolated resolver check: narrative fixed penalties and dice convert to TN.
        s["dxd"]["concerns"]["fatigue"] = s["dxd"]["concerns"]["capacity"]["endurance"]
        mythos.resolve_dxd(s, rules, {"id": "danger_test", "test": {
            "attribute": "REF", "tn": 7, "significance": "minor", "narrative": True, "fixed_dm": -2}})
        self.assertEqual(s["dxd"]["tests"][-1]["result"]["tn"], 12)

    def test_native_opposition_and_acquired_disability(self):
        from age_runtime.core import dxd_context
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        a = next(a for a in rules["actions"] if a["id"] == "speak_burroughs")
        mythos.resolve_dxd(s, rules, a)
        t = s["dxd"]["tests"][-1]
        self.assertEqual(t["inputs"]["target_dm"], 2)
        self.assertEqual(t["npc_gathered"]["skill"][0]["name"], "Investigate")
        dxd_context.acquire_commitment_disability(s["dxd"], {"context": "eleanor", "emotional_disability": True})
        name = "[Emotional > Commitment: eleanor]"
        self.assertIn(name, s["dxd"]["traits"])
        social = {"npc": "eleanor", "test": {"interaction": "ordinary"}}
        self.assertEqual(dxd_context.effects(s, social, dict(social["test"], attribute="PRE"))[0][0]["name"], name)

    def test_contextual_nomination_replay_and_rejection(self):
        s = mythos.initial("boothbay", 42)
        request = {"action": "inspect_docks", "approach": "systematic_search",
                   "intent": "Search the docks.", "nomination": {"skills": ["Grit"], "traits": [], "basis": "Persistence."}}
        before = mythos.digest(s)
        with self.assertRaises(ValueError):
            mythos.step(s, request["action"], request)
        self.assertEqual(mythos.digest(s), before)
        from age_runtime.mythos import nominations
        _, rules = mythos.load("boothbay")
        a = {"id": "read_journal", "test": {"attribute": "KNO", "skill": "Investigate"}}
        n = {"skills": ["Reasoning"], "traits": [], "basis": "Interpret the recorded evidence."}
        with self.assertRaises(ValueError):
            nominations.apply(s, rules, a, n)
        s["flags"].append("journal")
        compiled = nominations.apply(s, rules, a, n)
        self.assertEqual(compiled["test"]["additional_skills"], ["Reasoning"])
        self.assertNotIn("additional_skills", a["test"])
        for bad in (["Reasoning", "Reasoning"], ["Grit"], ["Invented"]):
            with self.assertRaises(ValueError):
                nominations.apply(s, rules, a, dict(n, skills=bad))
        with self.assertRaises(ValueError):
            nominations.apply(s, rules, a, dict(n, dm=100))

    def test_nomination_committed_history(self):
        for seed in range(20):
            s = mythos.step(mythos.initial("boothbay", seed), "visit_elias")
            if "journal" in s["flags"]:
                break
        else:
            self.fail("No journal access")
        req = {"action": "read_journal", "approach": "cross_reference",
               "intent": "Interpret the recorded evidence.",
               "nomination": {"skills": ["Reasoning"], "traits": [],
                              "basis": "Independently interpret the documented pattern."}}
        after = mythos.step(s, req["action"], req)
        self.assertEqual(after["history"][-1]["proposal"], req)
        self.assertEqual(after["dxd"]["tests"][-1]["gathered"]["skill"][-1]["name"], "Reasoning")
        mythos.verify(after)

    def test_fear_professional_progression(self):
        from age_runtime.core import dxd_progression as p
        s = mythos.initial("boothbay", 42)
        for profile in s["character_profiles"].values():
            q = profile["proficiencies"]["qualification"]
            self.assertTrue(q["qualified"], q)
            self.assertTrue(all(c["qualified"] for c in q["prior_careers"]))
        self.assertEqual(s["character_profiles"]["pc"]["proficiencies"]["qualification"]["bonus_skillpoints"], 40)
        self.assertEqual(p.xp_to_skillpoints(250), (2, 50))
        self.assertEqual(p.cumulative_cost(3, 3), 18)
        self.assertEqual(p.attribute_quote("INT", 1, 2), {"skillpoints": 14, "months": 14})
        self.assertEqual(p.soft_limit(3, {"KNO": 7, "INT": 9}, 3, True), 5)
        with self.assertRaises(ValueError):
            p.attribute_quote("INT", 3, 4)
        mythos.verify(s)

    def test_native_disability_mission_check_and_recovery(self):
        from age_runtime.core import dxd_context, dxd_conditions
        from random import Random
        outcomes = set()
        for seed in range(20):
            s = mythos.initial("boothbay", seed)
            pc = s["dxd"]
            outcomes.add(pc["addicted"])
            self.assertEqual(pc["addicted"], not pc["addiction_check"]["result"]["passed"])
            self.assertEqual(pc["concerns"]["restorative_stress_penalty"], 1)
            self.assertEqual(pc["favor"], 3)
            mythos.verify(s)
        self.assertEqual(outcomes, {True, False})
        s = mythos.initial("boothbay", 42)
        s["dxd"]["addicted"] = True
        self.assertEqual(dxd_context.effects(s, {}, {"attribute": "POW", "morale_event": "shock"})[1], 1)
        self.assertEqual(dxd_context.effects(s, {}, {"attribute": "RCA", "test_kind": "combat_hit"})[0][0]["penalty"], 1)
        s["resources"]["flask_servings"] = 0
        self.assertEqual(dxd_context.effects(s, {}, {"attribute": "KNO", "context_tags": ["sad"]})[0][0]["penalty"], 1)
        self.assertEqual(dxd_context.effects(s, {}, {"attribute": "KNO"})[0], [])
        pc = s["dxd"]
        concerns = pc["concerns"]
        concerns["stress"] = 9
        dxd_conditions.advance_activity(concerns, pc["activity"], 3600, "restorative",
                                        seed="audit", attributes=pc["attributes"])
        self.assertEqual(concerns["stress"], 9 - max(0, Random("audit:restorative:0").randint(1, 6) - 1))

    def test_fast_track_audit_derived(self):
        s = mythos.initial("boothbay", 42)
        audit = s["character_profiles"]["pc"]["proficiencies"]["progression"]["fast_track_audit"]
        self.assertEqual(audit["skill_cost_total"], 32)
        self.assertEqual(audit["unallocated_budget"], 8)
        self.assertEqual(s["character_profiles"]["pc"]["proficiencies"]["progression"]["skillpoints"], 0)
        mythos.verify(s)

    def test_commitment_leverage_and_temporary_demeanor(self):
        from age_runtime.core import dxd_commitment as ec
        s = mythos.initial("boothbay", 42)
        s["turn"] = 2
        entry = {"context": "burroughs", "level": 1, "turn": 1,
                 "witnessed_by": ["burroughs"], "demeanor_at_commitment": -1}
        s["dxd"]["commitments"].append(entry)
        _, rules = mythos.load("boothbay")
        action = next(a for a in rules["actions"] if a["id"] == "speak_burroughs")
        self.assertEqual(ec.leverage(s, action), 1)
        mythos.resolve_dxd(s, rules, action)
        t = s["dxd"]["tests"][-1]
        self.assertEqual(t["inputs"]["target_dm"], 3)
        self.assertEqual(t["components"]["emotional_commitment"], -1)
        self.assertEqual(t["components"]["commitment_leverage"], 1)
        self.assertEqual(ec.leverage(s, dict(action, npc="eleanor")), 0)
        self.assertEqual(ec.leverage(s, dict(action, commitment={"level": 1})), 0)
        entry["witnessed_by"] = []
        self.assertEqual(ec.leverage(s, action), 0)
        entry["witnessed_by"] = ["burroughs"]
        self.assertEqual(ec.effective_demeanor(s, "burroughs"), -1)
        # Higher level only as isolated rule test; initial player use remains 1.
        entry["level"] = 2
        self.assertEqual(ec.effective_demeanor(s, "burroughs"), 0)
        self.assertEqual(s["relationships"]["burroughs"], -1)
        mythos.change_demeanor(s, "burroughs", -1)
        self.assertIsNone(entry["demeanor_at_commitment"])
        self.assertEqual(ec.effective_demeanor(s, "burroughs"), -2)

    def test_automatic_character_emphasis(self):
        from age_runtime.mythos import hooks
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        a = next(a for a in rules["actions"] if a["id"] == "speak_burroughs")
        self.assertIs(hooks.apply(s, rules, a), a)
        s["flags"].append("police_attention")
        compiled = hooks.apply(s, rules, a)
        self.assertEqual(compiled["character_hook"]["dm"], -1)
        self.assertNotIn("character_hook", a)
        mythos.resolve_dxd(s, rules, compiled)
        t = s["dxd"]["tests"][-1]
        self.assertEqual(hooks.record(s, compiled, t), 5)
        self.assertEqual(hooks.record(s, compiled, t), 0)
        self.assertEqual(s["dxd"]["xp"], 5)
        self.assertEqual(hooks.apply(s, rules, a)["character_hook"]["dm"], -1)
        self.assertEqual(hooks.award(s, "distinct", 2, source="test"), 10)
        self.assertEqual(hooks.award(s, "distinct2", 3, source="test"), 20)
        self.assertEqual(s["dxd"]["xp"], 35)
        with self.assertRaises(ValueError):
            hooks.split({"hook": {"id": "invented"}})

    def test_disability_emphasis_single_award(self):
        from age_runtime.mythos import hooks
        s = mythos.initial("boothbay", 42)
        test = {"contextual": [{"name": "[Emotional > Event: War]", "penalty": 1, "dm": 0},
                               {"name": "[Addict > Drunkard]", "penalty": 1, "dm": 0}]}
        self.assertEqual(hooks.record(s, {}, test), 20)
        self.assertEqual(hooks.record(s, {}, test), 0)
        self.assertEqual(s["dxd"]["xp"], 20)
        self.assertEqual(len(s["dxd"]["emphasis_awards"]), 1)

    def test_persistent_circumstance_replaces_hook(self):
        from age_runtime.mythos import hooks
        s = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        a = next(a for a in rules["actions"] if a["id"] == "speak_burroughs")
        s["flags"].append("police_attention")
        self.assertEqual(hooks.apply(s, rules, a)["character_hook"]["dm"], -1)
        s["narrative_events"]["clocks"]["official_attention"]["resolved"] = True
        compiled = hooks.apply(s, rules, a)
        self.assertEqual(compiled["character_hook"]["dm"], -3)
        self.assertEqual(compiled["character_hook"]["replaces"], "professional_scrutiny")
        self.assertEqual(hooks.record(s, compiled, {}), 20)
        self.assertEqual(hooks.record(s, compiled, {}), 0)
        self.assertEqual(hooks.record(s, {"character_hook": {"id": "professional_scrutiny", "dm": -1, "emphasis": True}}, {}), 0)
        self.assertNotIn("character_hook", a)
        s["flags"].append("police_clearance")
        self.assertEqual(hooks.circumstances(s, rules, a), [])
