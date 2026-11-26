import unittest
from age_runtime.core import dxd_modifiers as m

class DXDModifiersTests(unittest.TestCase):
    def test_divide_levels_before_effect(self):
        a = {"INT": 12, "KNO": 10, "POW": 12}
        skills = {"History": 3, "Lore": {"level": 3, "dm_per_level": 2},
                  "Research": 2, "Support": {"level": 2, "dm_per_level": 1, "interdisciplinary": True}}
        traits = {"A": {"level": 4, "bonus_per_level": 1},
                  "B": {"level": 3, "penalty_per_level": 1},
                  "C": {"level": 2, "dm_per_level": -1, "explicit_only": True}}
        g = m.gather(a, skills, traits, {"attribute": "INT", "additional_attributes": ["KNO", "POW"],
                     "skill": "History", "additional_skills": ["Lore", "Research"],
                     "traits": ["A", "B"], "explicit_effects": [{"kind":"trait","name":"C"}],
                     "interdisciplinary": "Support"})
        self.assertEqual([v["effective_level"] for v in g["skill"]], [3,1,1])
        self.assertEqual(m.totals(g), {"dm": 11, "bonus": 4, "penalty": 1})

    def test_reject_duplicate_unknown_and_invalid_secondary(self):
        a = {"INT": 9, "KNO": 9}
        for spec in ({"attribute":"INT","additional_attributes":["KNO"]},
                     {"attribute":"INT","skill":"A","additional_skills":["A"]},
                     {"attribute":"INT","skill":"A","explicit_effects":[{"kind":"skill","name":"A"}]}):
            with self.assertRaises(ValueError):
                m.gather(a, {"A":2}, {}, spec)
        with self.assertRaises(KeyError):
            m.gather(a, {}, {}, {"attribute":"INT","skill":"invented"})
        self.assertEqual(m.effective_level(1,3),0)
        self.assertEqual(m.effective_level(2,3),1)
