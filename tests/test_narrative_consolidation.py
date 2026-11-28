"""Consolidation regressions: no new state format, mechanics or narrative ledger."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from age_runtime.mythos import mythos, player_recap, projections


class NarrativeConsolidationTests(unittest.TestCase):
    def test_short_local_work_prevents_premature_session_exhaustion(self):
        from datetime import datetime, timedelta
        from age_runtime.mythos import proposals
        state = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        state["discoveries"].append("Reviewed evidence")
        rules["end"] = (datetime.fromisoformat(state["time"]) + timedelta(seconds=180)).isoformat()
        rules["actions"] = []
        before = copy.deepcopy(state)
        self.assertEqual(mythos.options(state, rules), [])
        self.assertTrue(mythos.has_playable_action(state, rules))
        self.assertIn("review_notes", {c["approach"] for c in
            proposals.local_capabilities(state, rules, mythos.npc_available)})
        self.assertEqual(state, before)
        state["time"] = rules["end"]
        self.assertFalse(mythos.has_playable_action(state, rules))

    def test_objective_linked_travel_retains_actor_owned_purpose(self):
        from age_runtime.mythos import npc_agency
        state = mythos.initial("boothbay", 42)
        for action in ("talk_eleanor", "visit_elias", "inspect_room", "speak_burroughs"):
            state = mythos.step(state, action)
        goal = {"operation": "create", "id": "goal:visit_diner", "npc": "burroughs",
                "goal": "Visit the diner.", "priority": "normal",
                "intention": "Speak with Eleanor.", "basis": "His current intention.",
                "sources": []}
        state = mythos.establish_step(state, {"npc_objective": goal})
        request = {"npc": "burroughs", "destination": "Harbor Diner",
                   "basis": "He pursues his own objective.", "objective": goal["id"]}
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_travel": dict(request, objective="goal:unknown")})
        self.assertEqual(state, before)
        traveling = mythos.establish_step(state, {"npc_travel": request})
        self.assertEqual(traveling["npc_travel"][-1]["objective"], goal["id"])
        self.assertEqual(npc_agency.projection(traveling)["burroughs"]["journeys"][-1]["status"], "traveling")
        arrived = mythos.step(traveling, "observe")
        self.assertEqual(arrived["npc_travel"][-1]["status"], "completed")
        self.assertEqual(npc_agency.project(arrived)[goal["id"]]["status"], "active")
        self.assertNotIn("npc_agency", mythos.view(arrived))
        mythos.verify(arrived)

    def test_npc_travel_requires_explicit_end_of_committed_activity(self):
        from age_runtime.mythos import npc_time
        state = mythos.initial("boothbay", 42)
        for action in ("talk_eleanor", "visit_elias", "inspect_room", "speak_burroughs"):
            state = mythos.step(state, action)
        state = mythos.establish_step(state, {"npc_activity": {
            "npc": "burroughs", "mode": "low_energy", "safe": False,
            "minutes": 30, "basis": "He is reviewing paperwork."}})
        request = {"npc": "burroughs", "destination": "Harbor Diner",
                   "basis": "He intends to visit the diner."}
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_travel": request})
        self.assertEqual(state, before)
        self.assertIsNotNone(state["npcs"]["burroughs"]["activity_plan"])
        self.assertIsNone(npc_time.committed_event(state, "burroughs"))
        state = mythos.step(state, "wait:30")
        self.assertIsNone(state["npcs"]["burroughs"]["activity_plan"])
        traveling = mythos.establish_step(state, {"npc_travel": request})
        self.assertEqual(traveling["npc_travel"][-1]["status"], "traveling")
        mythos.verify(traveling)

    def test_spent_patrol_approach_does_not_preclude_withdrawal(self):
        from age_runtime.mythos import beats
        _, rules = mythos.load("boothbay")
        state = mythos.initial("boothbay", 42)
        state["location"] = "Lighthouse (Western Point)"
        state["flags"].extend(["patrol_risk", "written_account", "patrol_blocked"])
        state["used"].append("beat:patrol_approach")
        offers = beats.available(state, rules)
        self.assertNotIn("beat:patrol_approach", {a["action"] for a in offers})
        request = {"action": "beat:patrol_withdrawal", "approach": "withdraw",
                   "intent": "Leave the exposed approach."}
        self.assertIn(request["action"], {a["action"] for a in offers})
        compiled = beats.compile_beat(state, rules, request)
        self.assertEqual(compiled["grant"], ["patrol_withdrawn"])
        self.assertEqual(compiled["grant_failure"], ["patrol_withdrawn"])
        state["flags"].append("patrol_withdrawn")
        self.assertNotIn(request["action"], {a["action"] for a in beats.available(state, rules)})

    def test_intent_authority_is_read_only_and_terminal_aware(self):
        from age_runtime.mythos import proposals
        for sid in ("boothbay", "castine", "ram-island"):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                before = copy.deepcopy(state)
                packet = mythos.gm_context(state)
                authority = packet["referee"]["intent_authority"]
                self.assertEqual(authority["status"], "active")
                self.assertEqual(set(authority["classifications"]),
                                 {"certain", "uncertain", "conditional", "impossible", "unsupported"})
                self.assertNotIn("intent_authority", mythos.view(state))
                self.assertEqual(state, before)
                ended = copy.deepcopy(state)
                ended["ending"] = {"reason": "limit"}
                self.assertEqual(proposals.intent_authority(ended, {})["status"], "ended")
        state = mythos.initial("boothbay", 42)
        state["dxd"]["activity"]["status"] = "asleep"
        self.assertEqual(proposals.intent_authority(state, {})["status"], "asleep")

    def test_authored_approach_projection_matches_compiler_constraints(self):
        from age_runtime.mythos import proposals
        rules = {"gm_proposals": {"example": {"alternate": {"tn": 8}}}}
        action = {"id": "example", "test": {"tn": 7}}
        self.assertEqual(set(proposals.authored_approaches(action, rules)), {"alternate"})
        for blocked in (dict(action, terminal=True), dict(action, cost={"cash_cents": 1}),
                        dict(action, until="later"), {"id": "example"}):
            self.assertEqual(proposals.authored_approaches(blocked, rules), {})

    def test_public_projection_is_detached_for_every_trial(self):
        for sid in ("boothbay", "castine", "ram-island"):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                before = copy.deepcopy(state)
                public = mythos.view(state)
                public["discoveries"].append("not committed")
                public["observations"].append("not committed")
                public["resources"].clear()
                public["choices"].clear()
                if public.get("pacing", {}).get("current_spotlight"):
                    public["pacing"]["current_spotlight"]["activities"].clear()
                self.assertEqual(state, before)
                mythos.verify(state)

    def test_gm_projection_reuses_one_rules_load_and_action_computation(self):
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        state = mythos.narrative_step(state, {"kind": "open", "id": "inquiry",
                                               "label": "Ask about the missing man"})
        before = copy.deepcopy(state)
        with patch.object(mythos, "load", wraps=mythos.load) as load, \
                patch.object(mythos, "options", wraps=mythos.options) as options:
            packet = mythos.gm_context(state)
            self.assertEqual(load.call_count, 1)
            self.assertEqual(options.call_count, 1)
        self.assertEqual(packet["player_surface"]["revision"], mythos.digest(state))
        packet["player_surface"]["resources"].clear()
        packet["player_surface"]["pacing"]["current_spotlight"]["label"] = "changed"
        for participant in packet["referee"]["participants"]:
            participant["known_topics"].clear()
        self.assertEqual(state, before)

    def test_recall_full_history_preserves_bounded_normal_view(self):
        # Isolate the presentation window from local proposal eligibility.
        # These are synthetic player-origin records, not a replay fixture.
        state = mythos.initial("boothbay", 42)
        state["local_records"] = [
            {"kind": "survey", "target": "Harbor Docks",
             "turn": i, "at": state["time"], "passed": True, "effect": 1,
             "established": "survey_completed",
             "label": "old record" if i == 0 else "other record"}
            for i in range(12)]
        before = copy.deepcopy(state)
        ordinary = mythos.view(state)
        history = mythos.view(state, full_history=True)
        self.assertEqual(len(ordinary["local_records"]), 8)
        self.assertEqual(len(history["local_records"]), 12)
        self.assertEqual(player_recap.recall(ordinary, "old record")["total"], 0)
        found = player_recap.recall(history, "old record")
        self.assertEqual(found["matches"][0]["record"]["turn"], 0)
        self.assertEqual(ordinary["revision"], history["revision"])
        self.assertEqual(state, before)

    def test_compact_history_retains_older_agreement_and_current_reaction(self):
        # Synthetic projection isolates compaction, including a quieter NPC.
        claims = [{"id": i, "speaker": "pc", "listener": "eleanor"} for i in range(1, 21)]
        claims.append({"id": 21, "speaker": "pc", "listener": "elias"})
        current = {"emotion": {"text": "uneasy", "claim_id": 2}}
        packet = {
            "player_surface": {"narrative_agreements": [
                {"claim_ids": [1], "resolution_claim_ids": [3]}]},
            "referee": {"dialogue_context": claims,
                        "relational_context": {"eleanor": {
                            "current": copy.deepcopy(current),
                            "experiences": [{"claim_id": i} for i in range(1, 21)]}}}}
        projections.compact_history(packet)
        ids = [entry["id"] for entry in packet["referee"]["dialogue_context"]]
        self.assertEqual(ids, [1, 2, 3] + list(range(9, 22)))
        self.assertEqual(packet["referee"]["relational_context"]["eleanor"]["current"], current)
        self.assertEqual(packet["history_scope"]["omitted_counts"]["dialogue:eleanor/pc"], 5)
        self.assertEqual(len(packet["referee"]["relational_context"]["eleanor"]["experiences"]), 8)

    def test_single_copy_batch_matches_sequential_steps_and_replay(self):
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        before = copy.deepcopy(state)
        claim = {"npc": "eleanor", "speaker": "pc", "claim": "I have a question.",
                 "stance": "unstated", "intent": "unstated"}
        detail = {"details": [{"id": "inc:napkin", "kind": "object", "label": "Napkin",
                               "description": "A folded napkin.", "basis": "Ordinary diner object"}]}
        operations = [{"dialogue": claim}, {"establish": detail}]
        expected = mythos.establish_step(mythos.dialogue_step(state, claim), detail)
        with patch.object(mythos, "load", wraps=mythos.load) as load:
            actual = mythos.batch_step(state, {"operations": operations})
            self.assertEqual(load.call_count, 1)
        self.assertEqual(actual, expected)
        self.assertEqual(state, before)
        mythos.verify(actual)
        with self.assertRaises(ValueError):
            mythos.batch_step(state, {"operations": operations + [{"dialogue": claim}]})
        self.assertEqual(state, before)

    def test_transaction_does_not_save_if_public_projection_fails(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "session.json"
            opening = mythos.start("boothbay", path, 42)
            before = path.read_bytes()
            with patch.object(mythos, "view", side_effect=ValueError("projection failure")):
                with self.assertRaisesRegex(ValueError, "projection failure"):
                    mythos.act(path, "inspect_docks", opening["revision"])
            self.assertEqual(path.read_bytes(), before)
            after = mythos.act(path, "inspect_docks", opening["revision"])
            self.assertNotEqual(after["revision"], opening["revision"])
            self.assertEqual(mythos.inspect(path), after)


    def test_replay_loads_one_source_snapshot_and_preserves_input(self):
        state = mythos.initial("boothbay", 42)
        state = mythos.narrative_step(state, {"kind": "open", "id": "inquiry",
                                               "label": "Investigate the harbor"})
        state = mythos.step(state, "move:Harbor Diner")
        state = mythos.dialogue_step(state, {
            "npc": "eleanor", "speaker": "pc", "claim": "I have a question.",
            "stance": "unstated", "intent": "unstated"})
        state = mythos.establish_step(state, {"details": [{
            "id": "inc:napkin", "kind": "object", "label": "Napkin",
            "description": "A folded napkin.", "basis": "Ordinary diner object"}]})
        state = mythos.narrative_step(state, {"kind": "complete", "id": "inquiry"})
        before = copy.deepcopy(state)
        with patch.object(mythos, "load", wraps=mythos.load) as load:
            mythos.verify(state)
            self.assertEqual(load.call_count, 1)
        self.assertEqual(state, before)
        invalid = copy.deepcopy(state)
        invalid["resources"]["cash_cents"] += 1
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            mythos.verify(invalid)

    def test_resolution_compatibility_wrapper_preserves_test_ledger(self):
        from age_runtime.mythos import resolution
        state = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        action = next(a for a in rules["actions"] if a["id"] == "inspect_docks")
        direct = copy.deepcopy(state)
        delegated = copy.deepcopy(state)
        self.assertEqual(resolution.resolve(direct, rules, action, mythos.digest),
                         mythos.resolve_dxd(delegated, rules, action))
        self.assertEqual(direct, delegated)

    def test_establishment_dispatch_rejects_unknown_and_mixed_operations(self):
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        before = copy.deepcopy(state)
        for request in ({}, {"unknown": {}}, {"details": [], "agreement": {}},
                        ["details"], {"record": {}}):
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    mythos.establish_step(state, request)
                self.assertEqual(state, before)


    def test_authored_trial_gm_context_and_choice_timing(self):
        for sid, action in (("castine", "inspect_wharf"),
                            ("ram-island", "maintain_light")):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                before = copy.deepcopy(state)
                public = mythos.view(state)
                packet = mythos.gm_context(state)
                self.assertEqual(packet["audience"], "gm_only")
                self.assertEqual(packet["referee"]["mode"], "authored_actions_with_continuity")
                self.assertTrue(packet["referee"]["capabilities"]["persistent_dialogue"])
                self.assertFalse(packet["referee"]["capabilities"]["npc_agency"])
                self.assertFalse(packet["referee"]["capabilities"]["free_form_proposals"])
                self.assertEqual(packet["referee"]["allowed_actions"],
                                 [a["id"] for a in public["choices"]])
                self.assertEqual(packet["player_surface"]["revision"], public["revision"])
                choice = next(a for a in public["choices"] if a["id"] == action)
                self.assertGreater(choice["seconds"], 0)
                self.assertEqual(choice["minutes"] * 60, choice["seconds"])
                self.assertNotIn("travel_seconds", choice)
                self.assertEqual(player_recap.recap(public)["current_situation"]["description"],
                                 public["opening"])
                packet["player_surface"]["resources"].clear()
                self.assertEqual(state, before)
                after = mythos.step(state, action)
                mythos.verify(after)
                self.assertEqual(mythos.gm_context(after)["player_surface"]["revision"],
                                 mythos.digest(after))

    def test_terminal_checkpoint_blocks_further_gameplay(self):
        state = mythos.step(mythos.initial("boothbay", 42), "depart")
        before = copy.deepcopy(state)
        for operation in (
            lambda: mythos.step(state, "observe"),
            lambda: mythos.establish_step(state, {}),
            lambda: mythos.dialogue_step(state, {}),
            lambda: mythos.apply_memory(state, "observe", "A memory."),
            lambda: mythos.narrative_step(state, {"kind": "open", "id": "new", "label": "New focus"}),
        ):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(state, before)
        self.assertEqual(mythos.view(state)["choices"], [])
        mythos.verify(state)

    def test_death_projection_does_not_claim_self_preservation(self):
        from age_runtime.core import dxd_injury
        state = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        injury = state["dxd"]["injury"]
        dxd_injury.apply(injury, injury["capacity"] + 2 * injury["size"])
        state["flags"].append("written_account")
        ending = mythos.ending_projection(state, rules, "limit", "await_assistance")
        self.assertEqual(ending["reason"], "character_death")
        self.assertEqual(ending["scores"]["Self Preserved"], 0)
        self.assertTrue(ending["account_prepared"])
        self.assertFalse(ending["account_relayed"])
        self.assertIn("died", ending["epilogue"])

    def test_common_ending_projection_preserves_scenario_flags(self):
        for sid in ("boothbay", "castine", "ram-island"):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                _, rules = mythos.load(sid)
                result = mythos.ending_projection(state, rules, "limit", "observe")
                self.assertEqual(result["reason"], "limit")
                self.assertEqual(result["epilogue"], rules["ending_text"]["limit"])
                self.assertEqual(result["scores"], mythos.scores(state, "observe"))
                for field, flag in rules.get("ending_flags", {}).items():
                    self.assertEqual(result[field], flag in state["flags"])


    def test_cross_trial_continuity_and_encounter_guard(self):
        from age_runtime.mythos import epistemic
        for sid, npc in (("castine", "martha"), ("ram-island", "matteo")):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                _, rules = mythos.load(sid)
                claim = {"npc": npc, "speaker": "pc", "claim": "May we talk again?",
                         "stance": "unstated", "intent": "unstated"}
                with self.assertRaises(ValueError):
                    mythos.dialogue_step(state, claim)
                # Isolate encounter/window guard from authored Test outcomes.
                local = copy.deepcopy(state)
                local["location"] = local["npcs"][npc]["location"]
                with self.assertRaises(ValueError):
                    mythos.dialogue_step(local, claim)
                local["npcs"][npc]["encounters"] = 1
                if sid == "ram-island":
                    local["time"] = "1926-12-21T00:00:00"
                    self.assertFalse(epistemic.conversation_available(local, rules, npc, mythos.npc_available))
                    local["time"] = "1926-11-30T00:00:00"
                before = copy.deepcopy(local)
                answer = dict(claim, speaker=npc, claim="Certainly.",
                              reaction={"emotion": "wary", "significance": "Agreed to speak again."})
                agreement = {"operation": "create", "id": "agr:talk",
                             "kind": "commitment", "npc": npc, "issuer": npc,
                             "terms": "Speak again", "condition": None, "claim_ids": [1, 2]}
                after = mythos.batch_step(local, {"operations": [
                    {"dialogue": claim}, {"dialogue": answer},
                    {"establish": {"agreement": agreement}}]})
                self.assertEqual(local, before)
                for key in ("time", "turn", "flags", "discoveries", "dxd", "resources"):
                    self.assertEqual(after[key], before[key])
                public = mythos.view(after)
                self.assertNotIn("npc_reaction", public["dialogue"][-1])
                self.assertEqual(public["narrative_agreements"][0]["status"], "active")
                gm = mythos.gm_context(after)["referee"]
                self.assertEqual(gm["relational_context"][npc]["current"]["emotion"]["text"], "wary")
                self.assertTrue(gm["contextual_reminders"][npc]["active_agreements"])
                pid = "family_connection" if sid == "castine" else "delivery_account"
                linked = dict(answer, proposition=pid, asserts=True)
                with self.assertRaisesRegex(ValueError, "canonical disclosures"):
                    mythos.dialogue_step(after, linked)

    def test_cross_trial_mundane_establishment_replays(self):
        for sid in ("castine", "ram-island"):
            state = mythos.initial(sid, 42)
            after = mythos.establish_step(state, {"details": [
                {"id": "inc:bench", "kind": "fixture", "label": "Bench",
                 "description": "A plain bench.", "basis": "Mundane local furnishing"}]})
            mythos.verify(after)
            self.assertEqual(after["turn"], state["turn"])
            self.assertEqual(after["flags"], state["flags"])
            self.assertEqual(mythos.view(after)["established_details"][0]["id"], "inc:bench")


    def test_abstract_npc_recovery_actual_castine_replay(self):
        for seed in range(100):
            state = mythos.step(mythos.initial("castine", seed), "inspect_ledger")
            if "ledger" in state["flags"]:
                state = mythos.step(state, "talk_martha")
                break
        else:
            self.fail("No authored Martha encounter")
        state = mythos.dialogue_step(state, {"npc": "martha", "speaker": "pc",
            "claim": "I accuse you of concealing the evidence.", "stance": "unstated",
            "intent": "unstated"})
        episode = {"id": "emo:accusation", "npc": "martha", "claim_ids": [1],
            "emotion": "distress", "intensity": "acute", "expression": "She draws away.",
            "cause": "Actual accusation", "stress": {"martha": "severe"}}
        state = mythos.establish_step(state, {"emotion": episode})
        self.assertEqual(state["npcs"]["martha"]["concerns"]["stress"], 6)
        plan = {"npc": "martha", "mode": "rest", "safe": True,
                "minutes": 20, "basis": "GM establishes an undisturbed private rest interval"}
        planned = mythos.establish_step(state, {"npc_activity": plan})
        self.assertEqual(planned["time"], state["time"])
        self.assertEqual(planned["npcs"]["martha"]["concerns"], state["npcs"]["martha"]["concerns"])
        with self.assertRaises(ValueError):
            mythos.establish_step(planned, {"npc_activity": plan})
        after = mythos.step(planned, "observe")
        expected = copy.deepcopy(state["npcs"]["martha"]["concerns"])
        from age_runtime.core import dxd_conditions
        from datetime import datetime
        minutes = min(20, int((datetime.fromisoformat(after["time"]) -
                              datetime.fromisoformat(planned["time"])).total_seconds()) // 60)
        dxd_conditions.recover_rest_overlap(expected, 0, minutes * 60, safe=True)
        self.assertEqual(after["npcs"]["martha"]["concerns"], expected)
        self.assertEqual(mythos.step(state, "observe")["npcs"]["martha"]["concerns"],
                         state["npcs"]["martha"]["concerns"])
        mythos.verify(after)
        interrupted = mythos.dialogue_step(planned, {"npc": "martha", "speaker": "pc",
            "claim": "One more question.", "stance": "unstated", "intent": "unstated"})
        self.assertIsNone(interrupted["npcs"]["martha"]["activity_plan"])
        self.assertEqual(mythos.step(interrupted, "observe")["npcs"]["martha"]["concerns"],
                         state["npcs"]["martha"]["concerns"])
        mythos.verify(interrupted)

    def test_coarse_recovery_caps_long_interval_and_preserves_unsafe_stress(self):
        from age_runtime.mythos import npc_time
        from age_runtime.core import dxd_conditions
        from datetime import datetime, timedelta
        state = mythos.initial("ram-island", 42)
        _, rules = mythos.load("ram-island")
        npc = state["npcs"]["matteo"]
        dxd_conditions.add(npc["concerns"], fatigue=20, stress=12, weariness=12)
        start = datetime.fromisoformat(state["time"])
        npc["activity_plan"] = {"at": start.isoformat(),
            "until": (start + timedelta(minutes=10)).isoformat(),
            "location": npc["location"], "safe": False, "mode": "rest"}
        expected = copy.deepcopy(npc["concerns"])
        dxd_conditions.recover_rest_overlap(expected, 0, 600, safe=False)
        npc_time.advance_abstract(state, rules, start, start + timedelta(days=5))
        self.assertEqual(npc["concerns"], expected)
        self.assertEqual(npc["concerns"]["stress"], 12)
        self.assertIsNone(npc["activity_plan"])

    def test_authored_social_demeanor_replay_and_duplicate_guard(self):
        for seed in range(100):
            state = mythos.step(mythos.initial("castine", seed), "inspect_ledger")
            if "ledger" in state["flags"]:
                state = mythos.step(state, "talk_martha")
                break
        else:
            self.fail("No authored encounter")
        state = mythos.dialogue_step(state, {"npc": "martha", "speaker": "pc",
            "claim": "I consider you a dishonest witness.", "stance": "unstated",
            "intent": "unstated"})
        harm = {"npc": "martha", "claims": [1], "kind": "harm",
                "basis": "Actual personal insult"}
        before = copy.deepcopy(state)
        after = mythos.establish_step(state, {"social_demeanor": harm})
        self.assertLess(after["relationships"]["martha"], before["relationships"]["martha"])
        for key in ("time", "turn", "flags", "discoveries", "dxd", "resources"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["relationship_changes"][-1]["claims"], [1])
        self.assertEqual(mythos.gm_context(after)["referee"]["consequential_demeanor"]["martha"][-1]["kind"], "harm")
        self.assertIn("demeanor", mythos.view(after)["contacts"][0])
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"social_demeanor": harm})
        mythos.verify(after)

    def test_native_demeanor_rolling_limits_across_coarse_time(self):
        from datetime import datetime, timedelta
        state = mythos.initial("ram-island", 42)
        for _ in range(4):
            mythos.change_demeanor(state, "matteo", -1)
        self.assertEqual(state["relationships"]["matteo"], -3)
        for _ in range(4):
            mythos.change_demeanor(state, "matteo", 1)
        self.assertEqual(state["relationships"]["matteo"], -2)
        state["time"] = (datetime.fromisoformat(state["time"]) + timedelta(days=8)).isoformat()
        mythos.change_demeanor(state, "matteo", 1)
        self.assertEqual(state["relationships"]["matteo"], -1)
        state["time"] = (datetime.fromisoformat(state["time"]) + timedelta(days=31)).isoformat()
        mythos.change_demeanor(state, "matteo", 3)
        self.assertEqual(state["relationships"]["matteo"], 2)

    def test_scoped_objectives_and_beliefs_from_actual_castine_encounter(self):
        for seed in range(100):
            state = mythos.step(mythos.initial("castine", seed), "inspect_ledger")
            if "ledger" in state["flags"]:
                state = mythos.step(state, "talk_martha")
                break
        else:
            self.fail("No eligible authored encounter")
        request = {"npc": "martha", "speaker": "pc", "claim": "Perhaps Imogen left voluntarily.",
                   "stance": "unstated", "intent": "unstated"}
        state = mythos.dialogue_step(state, request)
        cid = state["dialogue"][-1]["id"]
        objective = {"operation": "create", "id": "goal:account", "npc": "martha",
                     "goal": "Understand the inquiry", "priority": "normal",
                     "intention": "Consider the suggestion", "basis": "Actual inquiry",
                     "sources": [{"kind": "claim", "id": cid}]}
        before = copy.deepcopy(state)
        state = mythos.batch_step(state, {"operations": [
            {"establish": {"npc_objective": objective}},
            {"establish": {"hypothesis": {"id": "hyp:departure", "npc": "martha",
                                           "text": "Imogen left voluntarily.", "source": cid}}},
            {"establish": {"belief_revision": {"npc": "martha", "proposition": "hyp:departure",
                "stance": "doubts", "asserts": True, "sources": [cid], "basis": "Uncertain account"}}}]})
        for key in ("time", "turn", "flags", "discoveries", "dxd", "relationships"):
            self.assertEqual(state[key], before[key])
        self.assertNotIn("favor", state["npcs"]["martha"])
        public = mythos.view(state)
        self.assertNotIn("npc_objectives", public)
        self.assertNotIn("dynamic_propositions", public)
        ref = mythos.gm_context(state)["referee"]
        self.assertEqual(ref["npc_agency"]["martha"]["objectives"][0]["id"], "goal:account")
        self.assertNotIn("zebediah", ref["npc_agency"])
        self.assertNotIn("favor", ref["npc_agency"]["martha"])
        self.assertEqual(ref["npc_agency"]["martha"]["social_tests"], [])
        self.assertNotIn("npc_social_tests", state)
        self.assertIn("emotional_context", ref)
        self.assertIn("npc_temporal", ref)
        self.assertIn("consequential_demeanor", ref)
        mythos.verify(state)
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_objective": dict(objective, id="goal:other",
                sources=[{"kind": "observation", "id": "missing"}])})
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_social_test": {
                "id": "social:test", "claim": cid, "basis": "Unsupported Test"}})

    def test_abstract_rest_partition_invariance_and_duplicate_credit(self):
        from age_runtime.mythos import npc_time
        from age_runtime.core import dxd_conditions
        from datetime import datetime, timedelta
        original = mythos.initial("ram-island", 42)
        _, rules = mythos.load("ram-island")
        npc = original["npcs"]["matteo"]
        dxd_conditions.add(npc["concerns"], fatigue=90, stress=60, weariness=40)
        start = datetime.fromisoformat(original["time"])
        finish = start + timedelta(minutes=65)
        npc["activity_plan"] = {"at": start.isoformat(), "until": finish.isoformat(),
                                "location": npc["location"], "safe": True, "mode": "rest"}
        whole = copy.deepcopy(original)
        split = copy.deepcopy(original)
        npc_time.advance_abstract(whole, rules, start, finish)
        middle = start + timedelta(minutes=7, seconds=30)
        npc_time.advance_abstract(split, rules, start, middle)
        snapshot = copy.deepcopy(split)
        npc_time.advance_abstract(split, rules, start, middle)
        self.assertEqual(split, snapshot)
        second = start + timedelta(minutes=59, seconds=45)
        npc_time.advance_abstract(split, rules, middle, second)
        npc_time.advance_abstract(split, rules, second, finish)
        self.assertEqual(split, whole)
        expected = copy.deepcopy(npc["concerns"])
        dxd_conditions.recover_rest_overlap(expected, 0, 65 * 60, safe=True)
        self.assertEqual(whole["npcs"]["matteo"]["concerns"], expected)
        self.assertIsNone(whole["npcs"]["matteo"]["activity_plan"])

    def test_narrative_routes_distinguish_closed_and_conditional(self):
        from age_runtime.mythos import continuity
        state = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        state["time"] = "1927-10-14T00:00:00"
        state["flags"].append("patrol_risk")
        functions = continuity.projection(state, rules, mythos.options(state, rules))
        relay = next(f for f in functions if f["id"] == "preserve_account")
        routes = {c["action"]: c["status"] for c in relay["carriers"]}
        self.assertEqual(routes["transmit_account"], "blocked")
        self.assertEqual(routes["relay_with_clearance"], "blocked")
        self.assertEqual(routes["leave_copy"], "conditional")
        self.assertEqual(routes["relay_after_patrol"], "conditional")
        self.assertFalse(relay["authored_routes_exhausted"])
        state["used"].extend(["leave_copy", "relay_after_patrol"])
        relay = next(f for f in continuity.projection(state, rules, [])
                     if f["id"] == "preserve_account")
        self.assertTrue(relay["authored_routes_exhausted"])
        state["flags"].append("account_entrusted")
        relay = next(f for f in continuity.projection(state, rules, [])
                     if f["id"] == "preserve_account")
        self.assertTrue(relay["established"])
        self.assertFalse(relay["authored_routes_exhausted"])

    def test_bounded_waiting_advances_world_and_preserves_location(self):
        from datetime import datetime, timedelta
        state = mythos.initial("boothbay", 42)
        before = copy.deepcopy(state)
        choice = next(c for c in mythos.view(state)["choices"] if c["id"] == "wait:120")
        self.assertEqual(choice["seconds"], 7200)
        after = mythos.step(state, "wait:120")
        self.assertEqual(after["time"], (datetime.fromisoformat(state["time"]) +
                                        timedelta(hours=2)).isoformat())
        self.assertEqual(after["location"], state["location"])
        self.assertEqual(after["resources"], state["resources"])
        self.assertEqual(after["discoveries"], state["discoveries"])
        self.assertEqual(after["dxd"]["tests"], state["dxd"]["tests"])
        self.assertEqual(after["dxd"]["activity"]["awake_seconds"], 7200)
        self.assertNotIn("wait:120", after["used"])
        self.assertEqual(state, before)
        mythos.verify(after)
        with self.assertRaises(ValueError):
            mythos.step(state, "wait:121")

    def test_bounded_waiting_stops_at_perceptible_interruption(self):
        from datetime import datetime, timedelta
        story, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        state = mythos._initial("boothbay", 42, story, rules)
        at = (datetime.fromisoformat(state["time"]) + timedelta(minutes=15)).isoformat()
        rules["events"] = [{"id": "wait_notice", "at": at, "observation": "A notice.",
                            "interrupt_activity": True}]
        after = mythos._step(copy.deepcopy(state), rules, "wait:120")
        self.assertEqual(after["time"], at)
        self.assertEqual(after["last_result"]["interrupted"], "event")
        self.assertEqual(after["dxd"]["activity"]["awake_seconds"], 900)
        self.assertEqual(after["narrative_events"]["encounter"]["seconds"], 900)

    def test_elapsed_exposure_is_independent_of_activity_partition(self):
        from age_runtime.mythos import events
        _, rules = mythos.load("boothbay")
        whole = mythos.initial("boothbay", 42)
        split = copy.deepcopy(whole)
        mythos.activity_segment(whole, rules, 1800, "active")
        for seconds in (10, 50, 600, 1140):
            mythos.activity_segment(split, rules, seconds, "active")
        self.assertEqual(whole["time"], split["time"])
        self.assertEqual(whole["narrative_events"]["encounter"],
                         split["narrative_events"]["encounter"])
        self.assertEqual(whole["narrative_events"]["encounter"]["dice"], 1)
        events.complete_action(whole, rules, {"id": "observe"}, True, 1800)
        self.assertEqual(whole["narrative_events"]["encounter"]["dice"], 1)

    def test_interrupted_exposure_credits_only_elapsed_time(self):
        from datetime import datetime, timedelta
        _, rules = mythos.load("boothbay")
        state = mythos.initial("boothbay", 42)
        at = datetime.fromisoformat(state["time"]) + timedelta(seconds=600)
        cfg = dict(rules, events=[{"id": "test_interrupt", "at": at.isoformat(),
                                  "observation": "An interruption.", "interrupt_activity": True}])
        reason = mythos.activity_segment(state, cfg, 3600, "low_energy", interruptible=True)
        self.assertEqual(reason, "event")
        self.assertEqual(state["time"], at.isoformat())
        self.assertEqual(state["narrative_events"]["encounter"]["seconds"], 600)
        mythos.activity_segment(state, cfg, 1200, "active")
        self.assertEqual(state["narrative_events"]["encounter"]["dice"], 1)

    def test_dated_event_validation_rejects_ambiguous_sources(self):
        from age_runtime.mythos import events
        _, rules = mythos.load("boothbay")
        event = {"id": "test", "at": rules["start"], "observation": "A notice."}
        events.validate_dated(dict(rules, events=[event]))
        for invalid in (
            [event, event],
            [dict(event, at="1920-01-01T00:00:00")],
            [dict(event, locations=["Not a location"])],
            [dict(event, visible_requires=["x"], visible_excludes=["x"])],
            [dict(event, visible_requires="x")],
            [dict(event, interrupt_activity="yes")],
        ):
            with self.subTest(events=invalid), self.assertRaises(ValueError):
                events.validate_dated(dict(rules, events=invalid))

    def test_dated_event_visibility_does_not_control_world_effect(self):
        from datetime import datetime
        _, rules = mythos.load("boothbay")
        for transit, location, known, visible in (
            (False, "Harbor Diner", True, True),
            (False, "Harbor Diner", False, False),
            (False, "Harbor Docks", True, False),
            (True, "Harbor Diner", True, False),
        ):
            with self.subTest(transit=transit, location=location, known=known):
                state = mythos.initial("boothbay", 42)
                state["location"] = location
                if known:
                    state["flags"].append("prior_notice")
                event = {"id": "test_closure", "at": state["time"],
                         "locations": ["Harbor Diner"], "visible_requires": ["prior_notice"],
                         "grant": ["door_closed"], "observation": "The door is closed.",
                         "interrupt_activity": True}
                cfg = dict(rules, events=[event])
                at = datetime.fromisoformat(state["time"])
                observed = mythos.advance_events(state, cfg, at, in_transit=transit)
                self.assertIn("door_closed", state["flags"])
                self.assertIn("test_closure", state["events_seen"])
                self.assertEqual(bool(observed), visible)
                self.assertEqual("The door is closed." in state["observations"], visible)
                self.assertEqual(mythos.advance_events(state, cfg, at), [])

    def test_dated_event_cannot_use_later_completion_discovery(self):
        # Synthetic timing fixture: the actual Castine action succeeds,
        # but an earlier event must not see the clue earned on completion.
        story, rules = mythos.load("castine")
        rules = copy.deepcopy(rules)
        rules["events"] = [{"id": "early", "at": "1927-11-02T08:30:00",
                            "visible_requires": ["tide_chart"], "observation": "Early clue-dependent event."}]
        for seed in range(100):
            state = mythos._initial("castine", seed, copy.deepcopy(story), copy.deepcopy(rules))
            after = mythos._step(state, rules, "inspect_wharf")
            if "tide_chart" in after["flags"]:
                self.assertIn("early", after["events_seen"])
                self.assertNotIn("Early clue-dependent event.", after["observations"])
                break
        else:
            self.fail("No successful chart inspection")

    def test_coarse_completion_revalidates_changed_flag(self):
        story, rules = mythos.load("castine")
        rules = copy.deepcopy(rules)
        action = next(a for a in rules["actions"] if a["id"] == "inspect_wharf")
        action["excludes_flags"] = ["access_closed"]
        rules["events"] = [{"id": "closure", "at": "1927-11-02T08:30:00",
                            "grant": ["access_closed"], "observation": "Access closes."}]
        state = mythos._initial("castine", 42, copy.deepcopy(story), copy.deepcopy(rules))
        before_tests = copy.deepcopy(state["dxd"]["tests"])
        after = mythos._step(state, rules, "inspect_wharf")
        self.assertEqual(after["last_result"]["interrupted"], "availability_changed")
        self.assertFalse(after["last_result"]["success"])
        self.assertNotIn("tide_chart", after["flags"])
        self.assertEqual(after["dxd"]["tests"], before_tests)
        self.assertEqual(after["time"], "1927-11-02T09:00:00")
        self.assertNotIn("inspect_wharf", after["used"])

    def test_source_mismatch_is_distinct_from_replay_mismatch(self):
        state = mythos.initial("castine", 42)
        bad_source = copy.deepcopy(state)
        bad_source["source"] = "old-revision"
        with self.assertRaisesRegex(ValueError, "source revision mismatch"):
            mythos.verify(bad_source)
        corrupt = copy.deepcopy(state)
        corrupt["resources"]["cash_cents"] += 1
        with self.assertRaisesRegex(ValueError, "session replay mismatch"):
            mythos.verify(corrupt)

    def test_remembered_details_do_not_reveal_current_offscene_state(self):
        state = mythos.initial("boothbay", 42)
        state = mythos.establish_step(state, {"details": [
            {"id": "inc:recall_bench", "kind": "fixture", "label": "Carved bench",
             "description": "A bench with a carved edge.", "basis": "Mundane furnishing"}]})
        original_location = state["location"]
        state = mythos.step(state, "move:Harbor Diner")
        self.assertNotEqual(state["location"], original_location)
        public = mythos.view(state)
        self.assertNotIn("remembered_details", public)
        self.assertEqual(player_recap.recall(public, "carved bench")["total"], 0)
        result = player_recap.recall(mythos.view(state, full_history=True), "carved bench")
        self.assertEqual(result["total"], 1)
        record = result["matches"][0]["record"]
        self.assertEqual(record["location"], original_location)
        self.assertNotIn("basis", record)
        self.assertNotIn("custodian", record)
        self.assertNotIn("properties", record)
        mythos.verify(state)

    def test_native_variable_local_duration_and_certain_resolution(self):
        from age_runtime.core import dxd
        from datetime import datetime
        from age_runtime.mythos import proposals
        for seed in range(100):
            state = mythos.step(mythos.initial("boothbay", seed), "inspect_docks")
            if state["discoveries"]:
                break
        else:
            self.fail("No earned discovery")
        request = {"action": "local:review_notes:Harbor Docks",
                   "approach": "review_notes", "intent": "Review the existing notes."}
        before = copy.deepcopy(state)
        cap = next(c for c in mythos.gm_context(state)["referee"]["local_capabilities"]
                   if c["action"] == request["action"])
        self.assertEqual(cap["duration_range_seconds"], [30, 180])
        self.assertNotIn("dice", cap)
        self.assertEqual(state, before)
        after = mythos.step(state, request["action"], request)
        roll = after["last_result"]["task_duration"]
        self.assertEqual(roll, dxd.task_duration(
            f"{state['seed']}:task-duration:{state['turn'] + 1}:{request['action']}", 10))
        self.assertEqual((datetime.fromisoformat(after["time"]) -
                          datetime.fromisoformat(state["time"])).total_seconds(), roll["seconds"])
        self.assertEqual(after["dxd"]["tests"], state["dxd"]["tests"])
        self.assertEqual(after["dxd"]["favor"], state["dxd"]["favor"])
        self.assertEqual(after["discoveries"], state["discoveries"])
        self.assertIsNone(after["local_records"][-1]["effect"])
        self.assertEqual(after["last_result"]["adjudication"],
                         {"passed": True, "resolution": "certain"})
        self.assertEqual(mythos.step(state, request["action"], request), after)
        mythos.verify(after)
        self.assertEqual(state, before)
        with self.assertRaises(ValueError):
            mythos.step(after, request["action"], request)
        with self.assertRaises(ValueError):
            mythos.step(mythos.initial("boothbay", 42), request["action"], request)
        _, rules = mythos.load("boothbay")
        invalid = copy.deepcopy(rules)
        invalid["local_proposals"]["review_notes"]["seconds"] = 60
        with self.assertRaises(ValueError):
            proposals.validate_local(invalid)

    def test_reviewed_note_task_resumes_without_duration_reroll(self):
        from datetime import datetime, timedelta
        from age_runtime.mythos import proposals
        story, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        state = mythos._initial("boothbay", 42, story, rules)
        start = datetime.fromisoformat(state["time"])
        rules["events"] = [{"id": "pause_notes", "at": (start + timedelta(seconds=60)).isoformat(),
                            "observation": "An interruption.", "interrupt_activity": True}]
        request = {"action": "local:compose_notes:Harbor Docks",
                   "approach": "compose_notes", "intent": "Organize my notes."}
        paused = mythos._step(copy.deepcopy(state), rules, request["action"], request)
        self.assertEqual(paused["last_result"]["interrupted"], "event")
        pending = paused["pending_work"][request["action"]]
        self.assertEqual(pending["worked_seconds"], 60)
        self.assertEqual(paused["dxd"]["tests"], state["dxd"]["tests"])
        self.assertEqual(paused["local_records"], [])
        self.assertNotIn(request["action"], paused["used"])
        roll = pending["task_duration"]
        cap = next(c for c in proposals.local_capabilities(paused, rules, mythos.npc_available)
                   if c["action"] == request["action"])
        self.assertTrue(cap["resuming"])
        self.assertEqual(cap["remaining_seconds"], roll["seconds"] - 60)
        finished = mythos._step(copy.deepcopy(paused), rules, request["action"], request)
        self.assertEqual(finished["last_result"]["task_duration"], roll)
        self.assertEqual((datetime.fromisoformat(finished["time"]) - start).total_seconds(), roll["seconds"])
        self.assertEqual(len(finished["dxd"]["tests"]), len(state["dxd"]["tests"]) + 1)
        self.assertNotIn(request["action"], finished["pending_work"])
        changed = copy.deepcopy(paused)
        changed["discoveries"].append("New evidence.")
        cap = next(c for c in proposals.local_capabilities(changed, rules, mythos.npc_available)
                   if c["action"] == request["action"])
        self.assertFalse(cap.get("resuming", False))

    def test_variable_task_deadline_preserves_elapsed_time_without_completion(self):
        from datetime import datetime, timedelta
        from age_runtime.core import dxd
        from age_runtime.mythos import proposals
        story, rules = mythos.load("boothbay")
        request = {"action": "local:compose_notes:Harbor Docks",
                   "approach": "compose_notes", "intent": "Organize my investigative notes."}
        for seed in range(100):
            state = mythos._initial("boothbay", seed, copy.deepcopy(story), copy.deepcopy(rules))
            roll = dxd.task_duration(f"{seed}:task-duration:1:{request['action']}", 60)
            if roll["seconds"] > 180:
                break
        else:
            self.fail("No duration exceeding minimum")
        cfg = copy.deepcopy(rules)
        cfg["end"] = (datetime.fromisoformat(state["time"]) + timedelta(seconds=180)).isoformat()
        offers = proposals.local_capabilities(state, cfg, mythos.npc_available)
        cap = next(c for c in offers if c["action"] == request["action"])
        self.assertTrue(cap["deadline_risk"])
        before = copy.deepcopy(state)
        after = mythos._step(copy.deepcopy(state), cfg, request["action"], request)
        self.assertEqual(after["time"], cfg["end"])
        self.assertEqual(after["last_result"]["interrupted"], "deadline")
        self.assertEqual(after["last_result"]["task_duration"], roll)
        self.assertFalse(after["last_result"]["success"])
        self.assertEqual(after["dxd"]["tests"], before["dxd"]["tests"])
        self.assertEqual(after["local_records"], before["local_records"])
        self.assertNotIn(request["action"], after["used"])
        self.assertEqual(after["ending"]["reason"], "limit")

    def test_variable_complex_task_rolls_before_completion_test(self):
        from datetime import datetime
        state = mythos.initial("boothbay", 42)
        request = {"action": "local:compose_notes:Harbor Docks",
                   "approach": "compose_notes", "intent": "Organize my investigative notes."}
        after = mythos.step(state, request["action"], request)
        roll = after["last_result"]["task_duration"]
        self.assertEqual(len(roll["dice"]), 3)
        self.assertTrue(all(1 <= die <= 6 for die in roll["dice"]))
        self.assertEqual(roll["seconds"], sum(roll["dice"]) * 60)
        self.assertEqual((datetime.fromisoformat(after["time"]) -
                          datetime.fromisoformat(state["time"])).total_seconds(), roll["seconds"])
        self.assertEqual(len(after["dxd"]["tests"]), len(state["dxd"]["tests"]) + 1)
        self.assertEqual(after["local_records"][-1]["task_duration"], roll)
        self.assertEqual(after["discoveries"], state["discoveries"])
        mythos.verify(after)

    def test_unheld_object_inspection_preserves_custody(self):
        from age_runtime.mythos import proposals, establishment
        state = mythos.initial("boothbay", 42)
        state = mythos.establish_step(state, {"details": [{
            "id": "inc:loose_note", "kind": "object", "label": "Loose note",
            "description": "An unattended scrap of paper.",
            "basis": "Mundane local object"}]})
        request = {"action": "local:inspect_object:inc:loose_note",
                   "approach": "inspect_object", "intent": "Examine the paper in place."}
        _, rules = mythos.load("boothbay")
        before = copy.deepcopy(state)
        self.assertIn(request["action"], {c["action"] for c in
            proposals.local_capabilities(state, rules, mythos.npc_available)})
        compiled = proposals.compile_local(state, rules, request, mythos.npc_available)
        self.assertIsNone(compiled["object_custodian_before"])
        held = mythos.establish_step(state, {"transfers": [{
            "id": "inc:loose_note", "from": None, "to": "pc",
            "pc_authorization": "I pick up the note.", "npc_consent": None,
            "basis": "Unheld local object"}]})
        self.assertFalse(proposals.completion_available(held, rules, compiled, mythos.npc_available))
        after = mythos.step(state, request["action"], request)
        self.assertEqual(state, before)
        self.assertIsNone(establishment.local_entities(after)["inc:loose_note"].get("custodian"))
        self.assertEqual(after["custody_transfers"], state["custody_transfers"])
        self.assertEqual(after["discoveries"], state["discoveries"])
        self.assertEqual(len(after["dxd"]["tests"]), len(state["dxd"]["tests"]) + 1)
        mythos.verify(after)

    def test_object_inspection_requires_custody_and_preserves_lifecycle(self):
        from age_runtime.mythos import proposals
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        state = mythos.establish_step(state, {"details": [{
            "id": "inc:cup", "kind": "object", "label": "Cup",
            "description": "A ceramic cup.", "basis": "Mundane diner furnishing",
            "custodian": "eleanor"}]})
        request = {"action": "local:inspect_object:inc:cup",
                   "approach": "inspect_object", "intent": "Examine the cup closely."}
        with self.assertRaises(ValueError):
            mythos.step(state, request["action"], request)
        state = mythos.establish_step(state, {"transfers": [{
            "id": "inc:cup", "from": "eleanor", "to": "pc",
            "pc_authorization": "I accept the cup.", "npc_consent": "Here you are.",
            "basis": "Voluntary transfer"}]})
        before = copy.deepcopy(state)
        offers = mythos.gm_context(state)["referee"]["local_capabilities"]
        self.assertIn(request["action"], {x["action"] for x in offers})
        self.assertFalse(any(x["approach"] in ("damage", "destroy") for x in offers))
        after = mythos.step(state, request["action"], request)
        self.assertEqual(state, before)
        self.assertEqual(after["object_actions"], state["object_actions"])
        self.assertEqual(after["discoveries"], state["discoveries"])
        self.assertEqual(after["local_records"][-1]["target"], "inc:cup")
        self.assertEqual(after["local_records"][-1]["location"], "Harbor Diner")
        self.assertEqual(len(after["dxd"]["tests"]), len(state["dxd"]["tests"]) + 1)
        mythos.verify(after)
        _, rules = mythos.load("boothbay")
        compiled = proposals.compile_local(state, rules, request, mythos.npc_available)
        damaged = mythos.establish_step(state, {"object_action": {
            "id": "act:chip", "object": "inc:cup", "before": "intact",
            "outcome": "damaged", "authorization": "I chip the cup.",
            "basis": "Certain incidental damage", "remnants": "Chipped rim"}})
        self.assertFalse(proposals.completion_available(damaged, rules, compiled, mythos.npc_available))
        with self.assertRaises(ValueError):
            mythos.step(after, request["action"], request)
        changed = mythos.establish_step(after, {"object_action": {
            "id": "act:chip_after", "object": "inc:cup", "before": "intact",
            "outcome": "damaged", "authorization": "I chip the cup.",
            "basis": "Certain incidental damage", "remnants": "Chipped rim"}})
        again = mythos.step(changed, request["action"], request)
        self.assertEqual(again["local_records"][-1]["object_condition"]["lifecycle"], "damaged")
        self.assertEqual(len(again["dxd"]["tests"]), len(after["dxd"]["tests"]) + 1)
        self.assertEqual(again["used"].count(request["action"]), 1)
        with self.assertRaises(ValueError):
            mythos.step(again, request["action"], request)
        mythos.verify(again)
        destroyed = mythos.establish_step(damaged, {"object_action": {
            "id": "act:break", "object": "inc:cup", "before": "damaged",
            "outcome": "destroyed", "authorization": "I drop the cup.",
            "basis": "Certain incidental breakage", "remnants": "Ceramic fragments"}})
        with self.assertRaises(ValueError):
            mythos.step(destroyed, request["action"], request)
        mythos.verify(destroyed)
        invalid = copy.deepcopy(rules)
        invalid["local_proposals"]["inspect_object"]["object_effect"] = "destroy"
        with self.assertRaises(ValueError):
            proposals.validate_local(invalid)

    def test_functional_consequence_without_physical_destruction(self):
        from age_runtime.mythos import establishment, proposals, behavior
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        state = mythos.establish_step(state, {"details": [{
            "id": "inc:watch", "kind": "object", "label": "Pocket watch",
            "description": "A working pocket watch.", "basis": "Mundane personal item",
            "custodian": "eleanor", "function": "operational"}]})
        state = mythos.establish_step(state, {"transfers": [{
            "id": "inc:watch", "from": "eleanor", "to": "pc",
            "pc_authorization": "I accept it.", "npc_consent": "Here you are.",
            "basis": "Voluntary transfer"}]})
        _, rules = mythos.load("boothbay")
        proposal = {"action": "local:inspect_object:inc:watch",
                    "approach": "inspect_object", "intent": "Examine the watch."}
        compiled = proposals.compile_local(state, rules, proposal, mythos.npc_available)
        request = {"id": "act:stop_watch", "object": "inc:watch",
                   "before": "intact", "outcome": "intact",
                   "function_before": "operational", "function_after": "nonfunctional",
                   "authorization": "I stop the watch permanently.",
                   "basis": "Reviewed certain incidental outcome",
                   "remnants": "The watch no longer works."}
        before = copy.deepcopy(state)
        after = mythos.establish_step(state, {"object_action": request})
        self.assertEqual(state, before)
        entity = establishment.local_entities(after)["inc:watch"]
        self.assertEqual(entity["lifecycle"], "intact")
        self.assertEqual(entity["function"], "nonfunctional")
        self.assertEqual(entity["custodian"], "pc")
        self.assertEqual(after["relationships"], state["relationships"])
        self.assertEqual(after["discoveries"], state["discoveries"])
        self.assertFalse(proposals.completion_available(after, rules, compiled, mythos.npc_available))
        self.assertIn(proposal["action"], {c["action"] for c in mythos.gm_context(after)["referee"]["local_capabilities"]})
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"object_action": dict(request, id="act:repeat")})
        witnessed = mythos.establish_step(after, {"action_observation": {
            "id": "obs:watch_stop", "npc": "eleanor", "action": "act:stop_watch",
            "kind": "witnessed", "basis": "Eleanor sees the action and its result."}})
        self.assertEqual(behavior.evidence(witnessed, "eleanor")["obs:watch_stop"]["function"], "nonfunctional")
        self.assertEqual(witnessed["relationships"], state["relationships"])
        discovered = mythos.establish_step(after, {"action_observation": {
            "id": "obs:watch_found", "npc": "eleanor", "action": "act:stop_watch",
            "kind": "discovered", "basis": "Eleanor examines the stopped watch."}})
        self.assertIsNone(discovered["action_observations"][-1]["actor"])
        self.assertEqual(discovered["action_observations"][-1]["function"], "nonfunctional")
        mythos.verify(witnessed)
        mythos.verify(discovered)
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"object_action": dict(request, id="act:restore_watch",
                function_before="nonfunctional", function_after="operational")})

    def test_objective_pursuit_deferral_resumption_and_reconsideration(self):
        from age_runtime.mythos import npc_agency
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        goal = {"operation": "create", "id": "goal:marks", "npc": "eleanor",
                "goal": "Understand the old markings.", "priority": "normal",
                "intention": "Examine my tin.", "basis": "Her own possession", "sources": []}
        state = mythos.establish_step(state, {"npc_objective": goal})
        state = mythos.establish_step(state, {"details": [{"id": "inc:tin", "kind": "object",
            "label": "Tin", "description": "An old tin.", "basis": "Her own possession",
            "custodian": "eleanor", "properties": {"appearance": "Faded initials"}}]})
        request = {"id": "evt:marks", "npc": "eleanor", "object": "inc:tin",
                   "objective": "goal:marks", "basis": "Examine the old markings."}
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_native_test": dict(request, objective="goal:unknown")})
        scheduled = mythos.establish_step(state, {"npc_native_test": request})
        review = {k: v for k, v in goal.items() if k != "goal"}
        review.update(operation="review", status="deferred", intention="Attend to immediate duties.")
        paused = mythos.establish_step(scheduled, {"npc_objective": review})
        event = paused["timed_detail_events"][-1]
        self.assertEqual(event["status"], "interrupted")
        self.assertEqual(event["work_seconds"], 0)
        self.assertEqual(event["interruption"], "objective_deferred")
        self.assertNotIn("test", event)
        resume = {"operation": "resume", "id": "evt:marks", "npc": "eleanor", "basis": "Return to the tin."}
        with self.assertRaises(ValueError):
            mythos.establish_step(paused, {"npc_task": resume})
        paused = mythos.step(paused, "observe")
        self.assertNotIn("test", paused["timed_detail_events"][-1])
        active = mythos.establish_step(paused, {"npc_objective": dict(review,
            status="active", intention="Return to the tin.", sources=[{"kind": "activity", "id": "evt:marks"}])})
        self.assertEqual(active["timed_detail_events"][-1]["status"], "interrupted")
        resumed = mythos.establish_step(active, {"npc_task": resume})
        finished = mythos.step(resumed, "observe")
        self.assertEqual(finished["timed_detail_events"][-1]["status"], "completed")
        self.assertEqual(finished["timed_detail_events"][-1]["work_seconds"], 600)
        self.assertTrue(npc_agency.active_objective(finished, "eleanor", "goal:marks"))
        self.assertFalse(npc_agency.owned_source(finished, "elias", {"kind": "activity", "id": "evt:marks"}))
        self.assertNotIn("npc_agency", mythos.view(finished))
        self.assertEqual(mythos.gm_context(finished)["referee"]["npc_agency"]["eleanor"]["pursuit"][-1]["status"], "completed")
        mythos.verify(finished)
        abandoned = mythos.establish_step(scheduled, {"npc_objective": dict(review,
            status="abandoned", intention="No longer pursue these markings.")})
        self.assertEqual(abandoned["timed_detail_events"][-1]["status"], "cancelled")
        with self.assertRaises(ValueError):
            mythos.establish_step(abandoned, {"npc_task": resume})
        mythos.verify(abandoned)

    def test_decision_context_retains_old_shared_consequences(self):
        from age_runtime.mythos import reminders, emotions, npc_agency
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        state = mythos.dialogue_step(state, {"npc": "eleanor", "speaker": "pc",
            "claim": "I am investigating your brother's disappearance.",
            "stance": "unstated", "intent": "unstated"})
        state = mythos.establish_step(state, {"npc_objective": {
            "operation": "create", "id": "goal:brother", "npc": "eleanor",
            "goal": "Learn what happened to my brother.", "priority": "urgent",
            "intention": "Ask about the inquiries.", "basis": "Her own motivation",
            "sources": [{"kind": "claim", "id": 1}]}})
        state = mythos.establish_step(state, {"details": [{"id": "inc:cup", "kind": "object",
            "label": "Cup", "description": "A ceramic cup.", "basis": "Mundane furnishing",
            "custodian": "eleanor"}]})
        state = mythos.establish_step(state, {"transfers": [{"id": "inc:cup",
            "from": "eleanor", "to": "pc", "pc_authorization": "I accept the cup.",
            "npc_consent": "Here you are.", "basis": "Voluntary transfer"}]})
        state = mythos.establish_step(state, {"object_action": {"id": "act:break",
            "object": "inc:cup", "before": "intact", "outcome": "destroyed",
            "authorization": "I drop the cup.", "basis": "Certain incidental breakage",
            "remnants": "Ceramic fragments"}})
        state = mythos.establish_step(state, {"action_observation": {
            "id": "obs:break", "npc": "eleanor", "action": "act:break",
            "kind": "witnessed", "basis": "She sees the cup break."}})
        state = mythos.establish_step(state, {"emotion": {"id": "emo:cup",
            "npc": "eleanor", "claim_ids": [], "observation": "obs:break",
            "emotion": "Anger", "intensity": "acute", "expression": "She frowns.",
            "cause": "Her cup was broken.", "stress": {}}})
        for i in range(14):
            state = mythos.dialogue_step(state, {"npc": "eleanor", "speaker": "pc",
                "claim": "Ordinary conversation topic " + str(i),
                "stance": "unstated", "intent": "unstated"})
            if i < 7:
                state = mythos.establish_step(state, {"emotion": {
                    "id": "emo:ordinary_" + str(i), "npc": "eleanor",
                    "claim_ids": [len(state["dialogue"])], "emotion": "Calm",
                    "intensity": "restrained", "expression": "She listens.",
                    "cause": "Ordinary conversation.", "stress": {}}})
        before = copy.deepcopy(state)
        packet = mythos.gm_context(state, compact=True)
        ref = packet["referee"]
        self.assertEqual(ref["contextual_reminders"]["eleanor"]["shared_actions"][0]["id"], "obs:break")
        self.assertIn("emo:cup", {e["id"] for e in ref["emotional_context"]["eleanor"]["salient_history"]})
        goal = ref["npc_agency"]["eleanor"]["objectives"][0]
        self.assertEqual(goal["decision_evidence"][0]["record"]["claim"],
                         "I am investigating your brother's disappearance.")
        self.assertIn(1, {e["id"] for e in ref["dialogue_context"]})
        self.assertFalse(npc_agency.owned_source(state, "elias", {"kind": "claim", "id": 1}))
        self.assertNotIn("npc_agency", mythos.view(state))
        self.assertEqual(state, before)
        mythos.verify(state)

    def test_discovered_object_consequence_is_not_shared_action_memory(self):
        from age_runtime.mythos import reminders
        state = mythos.initial("boothbay", 42)
        # Synthetic projection-only fixture: discovery does not identify an actor.
        state["action_observations"] = [{"id": "obs:found", "npc": "eleanor",
            "object": "inc:cup", "outcome": "destroyed", "condition": "Fragments",
            "kind": "discovered", "actor": None, "at": state["time"],
            "turn": state["turn"], "location": state["location"]}]
        self.assertNotIn("eleanor", reminders.projection(state, {"eleanor"}))

    def test_narrative_opportunity_latitude_is_mechanically_neutral(self):
        from age_runtime.core import opportunity_latitude as latitude
        for sid in ("boothbay", "castine", "ram-island"):
            base = mythos.initial(sid, 42)
            for level in latitude.LEVELS:
                state = mythos.initial(sid, 42, level)
                self.assertEqual(mythos.view(state)["opportunity_latitude"], level)
                self.assertEqual(mythos.gm_context(state, compact=True)["referee"]["opportunity_policy"]["level"], level)
                self.assertEqual(player_recap.recap(mythos.view(state))["opportunity_latitude"], level)
                self.assertEqual(mythos.view(state)["choices"], mythos.view(base)["choices"])
                self.assertEqual({k:v for k,v in state.items() if k not in ("opportunity_latitude", "settings_digest")},
                                 {k:v for k,v in base.items() if k not in ("opportunity_latitude", "settings_digest")})
                mythos.verify(state)
                action = mythos.view(state)["choices"][0]["id"]
                after = mythos.step(state, action)
                expected = mythos.step(base, action)
                self.assertEqual({k:v for k,v in after.items() if k not in ("opportunity_latitude", "settings_digest")},
                                 {k:v for k,v in expected.items() if k not in ("opportunity_latitude", "settings_digest")})
                mythos.verify(after)
            self.assertEqual(base["opportunity_latitude"], "balanced")
            legacy = copy.deepcopy(base)
            del legacy["opportunity_latitude"]
            del legacy["settings_digest"]
            mythos.verify(legacy)
            self.assertEqual(mythos.gm_context(legacy)["referee"]["opportunity_policy"]["level"], "balanced")
            corrupt = copy.deepcopy(base)
            corrupt["opportunity_latitude"] = "strict"
            with self.assertRaises(ValueError):
                mythos.verify(corrupt)
            with self.assertRaises(ValueError):
                mythos.initial(sid, 42, "unlimited")

    def test_narrative_opportunity_latitude_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            public = mythos.start("boothbay", path, 42, "permissive")
            self.assertEqual(public["opportunity_latitude"], "permissive")
            next_action = public["choices"][0]["id"]
            after = mythos.act(path, next_action, public["revision"])
            self.assertEqual(after["opportunity_latitude"], "permissive")
            self.assertEqual(mythos.inspect_gm(path)["referee"]["opportunity_policy"]["level"], "permissive")
