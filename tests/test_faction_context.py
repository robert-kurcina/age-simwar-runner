import copy
import unittest
from age_runtime.core.participants import bind_factions
from age_runtime.core.runner import initialize, advance, verify_checkpoint
from age_runtime.core.observations import observe

def scenario():
    return {"version": 1, "id": "relief", "turn_minutes": 60, "end_minute": 120,
            "initial": {"aid_packages": 3}, "events": [], "constraints": [],
            "actors": {"coordinator": {"label": "Relief coordinator", "visible_keys": ["aid_packages"]},
                       "partner": {"label": "Community partner", "visible_keys": []}}}

def profile():
    return {"version": 1, "world": "synthetic", "id": "coordinator", "kind": "organization",
            "effective_date": "2003-04-01", "label": "Relief coordinator", "rules_namespace": "sh44ser",
            "properties": {"motivations.relief": {"unit": "text", "value": "Maintain essential civilian services",
                "classification": "hypothetical", "reason": "Illustrative faction role"},
                "conditions.financing": {"unit": "unspecified", "value": None,
                "classification": "unresolved", "reason": "No dated evidence"}}}

class FactionContextTests(unittest.TestCase):
    def test_context_is_frozen_and_actor_local(self):
        s = scenario()
        p = profile()
        bind_factions(s, {"coordinator": p}, {}, "2003-04-01")
        a = initialize(s)
        self.assertEqual(a, initialize(s))
        v = observe(s, a, "coordinator")
        self.assertEqual(v["faction_context"]["properties"]["conditions.financing"]["value"], None)
        self.assertNotIn("faction_context", observe(s, a, "partner"))
        v["faction_context"]["label"] = "tampered"
        p["properties"]["motivations.relief"]["value"] = "tampered"
        self.assertEqual(observe(s, a, "coordinator")["faction_context"]["label"], "Relief coordinator")
        verify_checkpoint(s, advance(s, a))

    def test_invalid_identity_date_kind_and_digest(self):
        for field, value in (("kind","individual"), ("id","other"), ("effective_date","2044-01-01"), ("label","Other")):
            p = profile()
            p[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                bind_factions(scenario(), {"coordinator": p}, {}, "2003-04-01")
        s = scenario()
        bind_factions(s, {"coordinator": profile()}, {}, "2003-04-01")
        s["actors"]["coordinator"]["faction_context"]["profile"]["properties"]["motivations.relief"]["value"] = "changed"
        with self.assertRaises(ValueError):
            initialize(s)
