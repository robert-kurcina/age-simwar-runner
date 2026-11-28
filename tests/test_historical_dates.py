import unittest
from datetime import date, timedelta
from age_runtime.core.source_compiler import checked_date


class HistoricalDateTests(unittest.TestCase):
    def test_signed_order_and_round_trip(self):
        labels = ["-1555-01-01", "-1524-01-01", "-1523-12-31",
                  "-0001-12-31", "0000-01-01", "0001-01-01", "0286-01-01"]
        dates = [checked_date(label) for label in labels]
        self.assertEqual(sorted(dates), dates)
        self.assertEqual([d.isoformat() for d in dates], labels)

    def test_epoch_and_leap_days(self):
        for start, days, expected in (
            ("-0001-12-31", 1, "0000-01-01"),
            ("0000-12-31", 1, "0001-01-01"),
            ("0000-01-01", -1, "-0001-12-31"),
            ("-1524-02-28", 1, "-1524-02-29"),
            ("-1500-02-28", 1, "-1500-03-01"),
            ("-1524-01-01", 146097, "-1124-01-01"),
            ("-1124-01-01", -146097, "-1524-01-01")):
            with self.subTest(start=start, days=days):
                self.assertEqual(checked_date(start).add_days(days).isoformat(), expected)

    def test_ce_compatibility(self):
        for start in ("0001-01-01", "2000-02-28", "2003-04-01", "2044-12-31"):
            for days in (0, 1, 90, 365, 146098):
                self.assertEqual(checked_date(start).add_days(days).isoformat(),
                                 (date.fromisoformat(start) + timedelta(days=days)).isoformat())

    def test_invalid_dates(self):
        for value in ("-0000-01-01", "+1524-01-01", "-1524-02-30",
                      "-1523-02-29", "-1524-13-01", "1524", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checked_date(value)
