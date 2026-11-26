import unittest
from age_runtime.core import dxd_character as c

class DXDCharacterTests(unittest.TestCase):
    def test_table_and_derived_values(self):
        raw = dict.fromkeys(c.ROLLED, 7)
        body = {"stature": 50, "build": 50, "trade": "Service",
                "affinity": "INT", "attribute_rolls": dict(raw, INT=10)}
        p = c.derive(raw, body)
        self.assertEqual((p["height_inches"], p["weight_pounds"], p["attributes"]["SIZ"]), (71, 166, 12))
        self.assertEqual((p["walk"], p["jog"], p["run"]), (6, 9, 10))
        self.assertEqual(p["attributes"]["ZED"], 10)
        self.assertEqual(p["resistance"], 19)
        self.assertEqual(c.HEIGHT_WEIGHT[52], (74, 191, 13))
        with self.assertRaises(ValueError):
            c.derive(dict(raw, MOV=7), body)
        with self.assertRaises(ValueError):
            c.derive(raw, dict(body, affinity="POW"))

    def test_physical_properties(self):
        raw = dict.fromkeys(c.ROLLED, 7)
        p = c.derive(raw, {"stature": 50, "build": 50, "trade": "Service",
                            "affinity": "INT", "attribute_rolls": raw})
        physical = p["physical"]
        self.assertEqual(physical["basic_burden"], {"lift": 6, "shoulder": 3, "carry": 0})
        self.assertEqual(physical["maximum_burden"], {"lift": 11, "shoulder": 8, "carry": 5})
        self.assertEqual(physical["gasp_limit_turns"], 40)
        self.assertEqual(physical["sleep_limit_hours"], 45)
        self.assertEqual(physical["base_hitpoints"], 12)
        self.assertIsNone(physical["bodypoints"])
