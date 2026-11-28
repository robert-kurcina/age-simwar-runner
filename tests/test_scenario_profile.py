import unittest
from age_runtime.core.scenario_profile import profile

class ScenarioProfileTests(unittest.TestCase):
    def test_strategic(self):
        p = profile("civic-recovery", "service-restoration")
        self.assertEqual(p["duration"]["max_turns"], 2)
        self.assertEqual(p["perspectives"], ["coordinator"])
        self.assertEqual(p["scale"], "local")

    def test_mythos(self):
        p = profile("mythos", "boothbay")
        self.assertEqual(p["duration"]["target_spotlights"], 24)
        self.assertTrue(p["duration"]["spotlight_budget_advisory"])
        self.assertNotIn("max_turns", p["duration"])
        self.assertTrue(p["conclusion"]["early_termination"])
        self.assertNotIn("actions", p)
        self.assertNotIn("ending_text", p)

    def test_imported_and_unknown(self):
        self.assertEqual(profile("mythos", "ram-island")["duration"]["max_turns"], 20)
        with self.assertRaises(ValueError):
            profile("../mythos", "boothbay")
        with self.assertRaises(ValueError):
            profile("mythos", "../boothbay")

    def test_great_war_native_profile(self):
        p = profile("great-war", "manafount-rehearsal")
        self.assertEqual(p["duration"], {"clock": "event-driven-Time!", "endpoint_year": 5})
        self.assertEqual(p["perspectives"], ["amber", "azure"])
        self.assertFalse(p["conclusion"]["competitive_scoring"])
        with self.assertRaises(ValueError):
            profile("great-war", "../unknown")
