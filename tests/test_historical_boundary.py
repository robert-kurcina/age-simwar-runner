"""Regressions for source-bounded Great War quarterly scenario preparation."""
import copy
import json
import unittest
from pathlib import Path

from age_runtime.core.historical_boundary import quarterly_window, validate_opening_boundary


BOUNDARY = Path(__file__).resolve().parents[1] / "scenarios" / "great-war-quarterly-boundary.json"


class HistoricalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))

    def test_eight_quarters_in_chronological_order(self):
        turns = validate_opening_boundary(self.boundary)
        self.assertEqual(len(turns), 8)
        self.assertEqual(turns[0], {"turn": 1, "year": -1524, "quarter": 1})
        self.assertEqual(turns[-1], {"turn": 8, "year": -1523, "quarter": 4})
        self.assertEqual(len({(t["year"], t["quarter"]) for t in turns}), 8)

    def test_source_file_is_not_playable_and_does_not_invent_roster(self):
        self.assertIs(self.boundary["playable"], False)
        self.assertNotIn("actors", self.boundary)
        self.assertNotIn("resources", self.boundary)

    def test_reject_calendar_and_clock_inference(self):
        for mutation in ({"clock": "time_event"}, {"start_year": -1555},
                         {"end_year": -1522}, {"map_reference_year": -1524},
                         {"start_status": "FIXED"}, {"playable": True}):
            with self.subTest(mutation=mutation):
                b = {**self.boundary, **mutation}
                with self.assertRaises(ValueError):
                    validate_opening_boundary(b)

    def test_reject_missing_sources_and_unknowns(self):
        for field, value in (("sources", []), ("sources", [self.boundary["sources"][0]] * 2),
                             ("unresolved", []), ("unresolved", ["deity_roster"])):
            with self.subTest(field=field, value=value):
                b = copy.deepcopy(self.boundary)
                b[field] = value
                with self.assertRaises(ValueError):
                    validate_opening_boundary(b)

    def test_reject_bool_and_reversed_calendar(self):
        for args in ((True, -1523), (-1523, -1524), (-1524, -1523, 12)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                quarterly_window(*args)

    def test_new_schedule_is_not_shared_state(self):
        first = validate_opening_boundary(self.boundary)
        first[0]["year"] = 286
        self.assertEqual(validate_opening_boundary(self.boundary)[0]["year"], -1524)


if __name__ == "__main__":
    unittest.main()
