"""Keyed period grids and workbook references for v2 company modules.

The grid owns period placement. Company modules name facts and drivers; they never emit
cross-sheet A1 references themselves.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook
from openpyxl.workbook.defined_name import DefinedName


class GridError(ValueError):
    """The period grid or a requested key is invalid."""


_PERIOD = re.compile(r"^(?P<year>\d{4})Q(?P<quarter>[1-4])(?P<estimate>E)?$")


def _period_parts(period: str) -> tuple[int, int, bool]:
    match = _PERIOD.fullmatch(period)
    if not match:
        raise GridError(f"invalid canonical period {period!r}; expected YYYYQ[1-4][E]")
    return int(match["year"]), int(match["quarter"]), bool(match["estimate"])


@dataclass(frozen=True)
class PeriodGrid:
    """Ordered actual, forecast and complete-year columns for one model sheet."""

    actuals: tuple[str, ...]
    forecasts: tuple[str, ...]
    first_column: int = 3

    def __post_init__(self) -> None:
        periods = self.actuals + self.forecasts
        identities = [(_period_parts(period)[0], _period_parts(period)[1]) for period in periods]
        if len(identities) != len(set(identities)):
            raise GridError("a fiscal quarter may occur only once in a grid")
        for period in self.actuals:
            _year, _quarter, estimate = _period_parts(period)
            if estimate:
                raise GridError(f"actual period {period!r} must not end in E")
        for period in self.forecasts:
            _year, _quarter, estimate = _period_parts(period)
            if not estimate:
                raise GridError(f"forecast period {period!r} must end in E")

    @property
    def periods(self) -> tuple[str, ...]:
        return self.actuals + self.forecasts

    @property
    def columns(self) -> dict[str, int]:
        return {period: self.first_column + index for index, period in enumerate(self.periods)}

    @property
    def annual_periods(self) -> tuple[str, ...]:
        complete: list[str] = []
        for year in sorted({_period_parts(period)[0] for period in self.periods}):
            year_periods = [period for period in self.periods if _period_parts(period)[0] == year]
            if {_period_parts(period)[1] for period in year_periods} == {1, 2, 3, 4}:
                complete.append(f"FY{year}{'E' if any(_period_parts(p)[2] for p in year_periods) else 'A'}")
        return tuple(complete)

    def annual_members(self, annual_period: str) -> tuple[str, ...]:
        match = re.fullmatch(r"FY(\d{4})([AE])", annual_period)
        if not match:
            raise GridError(f"invalid annual period {annual_period!r}")
        year = int(match[1])
        members = tuple(period for period in self.periods if _period_parts(period)[0] == year)
        if len(members) != 4:
            raise GridError(f"{annual_period} has no four-quarter model group")
        return members


class KeyedReferences:
    """Bind a stable key to a workbook defined name and return formula-safe references."""

    def __init__(self, workbook: Workbook):
        self.workbook = workbook
        self._names: dict[str, str] = {}

    @staticmethod
    def name(key: str) -> str:
        """Return the stable Excel defined name for a documented metric key."""
        name = re.sub(r"[^A-Za-z0-9_]", "_", key)
        if not name or name[0].isdigit():
            name = "k_" + name
        return "em_" + name

    def bind(self, key: str, sheet: str, row: int, column: int) -> str:
        if key in self._names:
            raise GridError(f"duplicate reference key {key!r}")
        if sheet not in self.workbook.sheetnames:
            raise GridError(f"unknown workbook sheet {sheet!r}")
        name = self.name(key)
        if any(name.casefold() == existing.casefold() for existing in self._names.values()):
            raise GridError(f"keys collide after Excel-name normalisation: {key!r}")
        escaped_sheet = sheet.replace("'", "''")
        address = f"'{escaped_sheet}'!${get_column_letter(column)}${row}"
        self.workbook.defined_names.add(DefinedName(name, attr_text=address))
        self._names[key] = name
        return name

    def ref(self, key: str) -> str:
        try:
            return self._names[key]
        except KeyError as exc:
            raise GridError(f"unbound reference key {key!r}") from exc

    def formula(self, key: str) -> str:
        return "=" + self.ref(key)


def labels(periods: Iterable[str]) -> list[str]:
    """Render canonical periods as `Qn YYYY A/E` labels for workbook headings."""
    rendered = []
    for period in periods:
        year, quarter, estimate = _period_parts(period)
        rendered.append(f"Q{quarter} {year}{'E' if estimate else 'A'}")
    return rendered
