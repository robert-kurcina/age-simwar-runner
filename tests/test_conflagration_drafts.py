"""Migrated v7 drafts: raw mechanics only; no private evidence or live LLM qualification."""
import copy
import unittest
from pathlib import Path

from age_runtime.core.source_compiler import parse_json
from age_runtime.core.private_play import inventory, select, supported, eligible_perspectives
from age_runtime.core.runner import (
    initialize, digest, verify_checkpoint, advance, faction_packet,
    accept_faction_choice, commit_decision, communicate, assess_proposition,
    record_diplomacy, schedule_development,
)
from age_runtime.core.observations import observe
from age_runtime.core.institutional_memory import recall

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration"
CATALOG = ROOT / "inventory.json"


def load(group):
    return parse_json((ROOT / group / "scenario-spec.json").read_bytes())


def choose(s, state, actor, action=None):
    packet = faction_packet(s, state, actor)
    return accept_faction_choice(s, state, actor, packet,
                                 {"packet_id": packet["packet_id"], "action": action})


def decide(s, state, actor, ident, action=None, command=None):
    return commit_decision(s, state, actor, digest(state), ident, ident,
                           action, negotiation_command=command)


def finish(s, state, chosen=(), actions=None):
    for actor in s["model_factions"]:
        if actor not in chosen:
            state = choose(s, state, actor, (actions or {}).get(actor))
    state = advance(s, state)
    verify_checkpoint(s, state)
    return state


class ConflagrationDrafts(unittest.TestCase):
    def test_catalog_and_all_perspectives(self):
        catalog = inventory(CATALOG)
        self.assertEqual(len(catalog["groups"]), 8)
        groups = {g["id"]: g for g in catalog["groups"]}
        self.assertEqual(groups["hexaday"]["status"], "catalog-only")
        self.assertEqual(groups["hexaday"]["scenarios"], [])
        self.assertEqual(set(groups), {"hexaday", "disaster-response", "fallout",
                         "mainlander-ingress", "early-reconstruction", "purge",
                         "agreement", "reconstruction"})
        profiles = 0
        for group in catalog["groups"]:
            for entry in group["scenarios"]:
                with self.subTest(scenario=entry["id"]):
                    self.assertEqual(entry["status"], "draft-unreviewed")
                    # Refuse draft selection before attempting private source access.
                    with self.assertRaisesRegex(ValueError, "catalog-only"):
                        select(CATALOG, entry["id"], {})
                    spec = load(group["id"])
                    s = spec["scenario"]
                    self.assertEqual(entry["spec"], group["id"] + "/scenario-spec.json")
                    self.assertEqual(entry["id"], s["id"])
                    self.assertEqual(set(spec["faction_profiles"]), set(s["actors"]))
                    profiles += len(spec["faction_profiles"])
                    supported(s)
                    perspectives = eligible_perspectives(entry, s)
                    self.assertEqual(set(perspectives), set(s["actors"]))
                    # Raw mechanics are tested independently of canonical source resolution.
                    for human in perspectives:
                        with self.subTest(human=human):
                            variant = copy.deepcopy(s)
                            order = list(s["model_factions"]) + [
                                a for a in s["actors"] if a not in s["model_factions"]]
                            variant["model_factions"] = [a for a in order if a != human]
                            supported(variant)
                            state = initialize(variant)
                            self.assertEqual(state["values"], s["initial"])
                            while state["minute"] < variant["end_minute"]:
                                state = finish(variant, state)
                            verify_checkpoint(variant, state)
                            self.assertEqual(state["minute"], variant["end_minute"])
                            self.assertEqual(advance(variant, state), state)
        self.assertEqual(profiles, 25)
        candidate = parse_json((ROOT / "reconstruction/wpc-profile-draft.json").read_bytes())
        self.assertEqual(candidate["id"], "wpc")
        self.assertNotIn("wpc", load("reconstruction")["scenario"]["actors"])

    def test_fallout_four_routes(self):
        s = load("fallout")["scenario"]
        state = initialize(s)
        hidden = faction_packet(s, state, "vanuatu")
        state = communicate(s, state, "fiji", digest(state), {
            "id": "reception_status", "recipients": ["shanter", "vanuatu"],
            "claim": "Our reception service project is not complete; we request timely relief support.",
            "proposition": "reception_complete", "asserts": False})
        self.assertEqual(faction_packet(s, state, "vanuatu"), hidden)
        state = assess_proposition(s, state, "shanter", digest(state), {
            "proposition": "reception_complete", "stance": "disbelieves",
            "basis": ["reception_status"]})
        state = record_diplomacy(s, state, "fiji", digest(state), {
            "kind": "intention", "id": "seek_early_support", "counterpart": "shanter",
            "topic": "relief_timing", "text": "Seek early support to begin local investment.",
            "status": "active", "revises": None})
        self.assertNotIn("relief_timing", observe(s, state, "shanter")
                         ["diplomatic_history"].get("fiji", {}).get("private_intentions", {}))
        opening = choose(s, state, "fiji", {"kind": "propose", "id": "early_aid",
                         "recipient": "shanter", "transfers": ["shanter_support_fiji"],
                         "due_minute": 10080})
        frozen = digest(opening)
        expected = {"early": (3, 3, 3, 1, 1), "late": (3, 2, 3, 1, 1),
                    "substitute": (3, 3, 3, 2, 0), "refused": (3, 0, 3, 2, 1)}

        def route(name):
            if name == "early":
                response = {"kind": "accept", "id": "early_aid"}
            elif name == "late":
                response = {"kind": "counter", "id": "later_aid", "recipient": "fiji",
                            "transfers": ["shanter_support_fiji"], "parent": "early_aid",
                            "due_minute": 20160}
            else:
                response = {"kind": "reject", "id": "early_aid"}
            st = decide(s, opening, "shanter", "funding_response", command=response)
            st = decide(s, st, "shanter", "local_investment", action="shanter_invest")
            st = finish(s, st, ("fiji",), {"vanuatu": "vanuatu_support_fiji"
                                          if name == "substitute" else "vanuatu_invest"})
            self.assertEqual(recall(observe(s, st, "vanuatu"))["communications"][0]["id"],
                             "reception_status")
            self.assertEqual(observe(s, st, "vanuatu")["reports"]["fiji_progress"]["as_of_minute"], 0)
            self.assertEqual(st["values"]["fiji_credits"], int(name in ("early", "substitute")))
            if name == "early":
                self.assertEqual(st["negotiations"]["early_aid"]["status"], "fulfilled")
            if name == "late":
                self.assertEqual(st["negotiations"]["early_aid"]["status"], "countered")
                st = choose(s, st, "fiji", {"kind": "accept", "id": "later_aid"})
                st = finish(s, st, ("fiji",))
                self.assertEqual(st["negotiations"]["later_aid"]["status"], "fulfilled")
                self.assertEqual(st["values"]["fiji_credits"], 1)
                st = finish(s, st, actions={"fiji": "fiji_invest"})
            else:
                actions = {}
                if name in ("early", "substitute"):
                    actions["fiji"] = "fiji_invest"
                if name == "substitute":
                    actions["vanuatu"] = "vanuatu_invest"
                st = finish(s, st, actions=actions)
            while st["minute"] < s["end_minute"]:
                st = finish(s, st)
            vals = st["values"]
            self.assertEqual(tuple(vals[k] for k in ("shanter_progress", "fiji_progress",
                "vanuatu_progress", "shanter_credits", "vanuatu_credits")), expected[name])
            self.assertEqual(vals["fiji_credits"], 0)
            self.assertEqual(observe(s, st, "shanter")["values"]["fiji_progress"],
                             max(0, expected[name][1] - 1))
            return st

        for name in expected:
            with self.subTest(route=name):
                self.assertEqual(digest(route(name)), digest(route(name)))
                self.assertEqual(digest(opening), frozen)

    def test_rwf_three_routes(self):
        s = load("early-reconstruction")["scenario"]
        s["model_factions"] = ["shanter", "fiji", "vanuatu"]

        def route(recipient):
            st = initialize(s)
            target = recipient or "fiji"
            other = "vanuatu" if target == "fiji" else "fiji"
            term = target + "_independent_review"
            st = decide(s, st, "rwf", "request", command={"kind": "propose", "id": "permit",
                        "recipient": target, "permission": term, "due_minute": 50400})
            st = choose(s, st, target, {"kind": "accept" if recipient else "reject", "id": "permit"})
            cmd = {"template": term, "due_minute": 10080, "permission_id": "permit",
                   "rationale": "Illustrative review of program records."}
            if recipient:
                st = schedule_development(s, st, digest(st), cmd)
            else:
                old = digest(st)
                with self.assertRaises(ValueError):
                    schedule_development(s, st, digest(st), cmd)
                self.assertEqual(digest(st), old)
            st = finish(s, st, (target,))
            self.assertEqual(st["values"][target + "_review_completed"], int(bool(recipient)))
            self.assertEqual(st["values"]["rwf_credits"], 2)
            self.assertEqual(observe(s, st, target)["values"][target + "_review_completed"], 0)
            self.assertNotIn(target + "_review_completed", observe(s, st, other)["values"])
            if recipient:
                st = decide(s, st, "rwf", "grant", command={"kind": "propose", "id": "grant",
                            "recipient": recipient, "transfers": ["rwf_grant_" + recipient],
                            "due_minute": 20160})
                st = choose(s, st, recipient, {"kind": "accept", "id": "grant"})
                st = finish(s, st, (recipient,))
                self.assertEqual(st["negotiations"]["grant"]["status"], "fulfilled")
                self.assertEqual(st["values"]["rwf_credits"], 1)
                self.assertEqual(observe(s, st, recipient)["values"][recipient + "_review_completed"], 1)
                action = "invest_port_repairs" if recipient == "fiji" else "invest_water_services"
                st = finish(s, st, actions={recipient: action})
            else:
                st = finish(s, st)
            while st["minute"] < s["end_minute"]:
                st = finish(s, st)
            self.assertEqual(st["values"]["rwf_credits"], 1 if recipient else 2)
            self.assertEqual(st["values"]["port_repairs_progress"], 3 if recipient == "fiji" else 0)
            self.assertEqual(st["values"]["water_services_progress"], 3 if recipient == "vanuatu" else 0)
            return st

        for recipient in ("fiji", "vanuatu", None):
            with self.subTest(recipient=recipient):
                self.assertEqual(digest(route(recipient)), digest(route(recipient)))


if __name__ == "__main__":
    unittest.main()
