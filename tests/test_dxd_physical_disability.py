import unittest
from age_runtime.core import dxd_injury as injury
from age_runtime.core import dxd_physical_disability as disability


class PermanentLocationTests(unittest.TestCase):
    def test_persistence_and_context(self):
        state = injury.initial(12, 12, 4)
        injury.apply(state, 6)
        effect = {"location": "left_hand", "severity": "dismembered"}
        disability.record(state, effect)
        disability.record(state, effect)
        self.assertEqual(disability.penalties(state, {}), [])
        self.assertEqual(disability.penalties(state, {"participating_locations": ["right_hand"]}), [])
        self.assertEqual(disability.penalties(state, {"participating_locations": ["left_hand", "left_hand"]}),
                         [{"location": "left_hand", "penalty": 3}])
        self.assertEqual(disability.penalties(state, {"participating_locations": ["left_hand"],
                                                     "assisted_locations": ["left_hand"]}),
                         [{"location": "left_hand", "penalty": 2}])
        injury.recuperate(state, 60*injury.DAY, regime="general", eligible=True)
        self.assertEqual(state["injury"], 0)
        self.assertEqual(disability.projection(state), {"left_hand": "dismembered"})

    def test_validation_and_no_injury(self):
        state = injury.initial(12, 12, 4)
        with self.assertRaises(ValueError):
            disability.record(state, {"location": "left_hand", "severity": "dismembered"})
        with self.assertRaises(ValueError):
            disability.validate({"location": "left_hand", "severity": "impaired"})
        with self.assertRaises(ValueError):
            disability.penalties(state, {"participating_locations": [], "assisted_locations": ["left_hand"]})
