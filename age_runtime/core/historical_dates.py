"""Signed historical-model dates, with the corpus's explicit year zero.

Negative years denote BCE labels (not ISO astronomical year numbering).
For elapsed-day arithmetic only, use a proleptic Gregorian cycle extended
through year zero. This is a computational convention, not historical canon.
Quarterly matrix clocks remain abstract and are not converted here.
"""
from datetime import date, timedelta
from dataclasses import dataclass
import re


@dataclass(frozen=True, order=True)
class HistoricalDate:
    year: int
    month: int
    day: int

    def __post_init__(self):
        if not -9999 <= self.year <= 9999:
            raise ValueError("historical year outside supported range")
        # Gregorian month lengths repeat every 400 years, including year zero.
        date(2000 + self.year % 400, self.month, self.day)

    def isoformat(self):
        year = f"-{abs(self.year):04d}" if self.year < 0 else f"{self.year:04d}"
        return f"{year}-{self.month:02d}-{self.day:02d}"

    def _ordinal(self):
        cycles, year = divmod(self.year, 400)
        return cycles * 146097 + date(2000 + year, self.month, self.day).toordinal()

    def __sub__(self, other):
        if not isinstance(other, HistoricalDate):
            return NotImplemented
        return timedelta(days=self._ordinal() - other._ordinal())

    def __add__(self, other):
        if not isinstance(other, timedelta):
            return NotImplemented
        return self.add_days(other.days)

    def add_days(self, days):
        # Map signed years into positive Gregorian cycles, perform ordinary
        # date arithmetic, then restore the signed model year. Reduce across
        # whole 400-year cycles to avoid datetime's bounded year range.
        cycles, rest = divmod(days, 146097)
        shifted = date(2000 + self.year % 400, self.month, self.day) + timedelta(days=rest)
        year = self.year - self.year % 400 + shifted.year - 2000 + cycles * 400
        return HistoricalDate(year, shifted.month, shifted.day)


def checked_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expected signed historical effective date")
    if value.startswith("-0000"):
        raise ValueError("negative zero is not a historical year")
    year, month, day = int(value[:-6]), int(value[-5:-3]), int(value[-2:])
    return HistoricalDate(year, month, day)
