"""Extract and restore designated numeric assumption overrides in a model workbook.

An override is identified by ``(driver, fiscal period)`` — never by a cell
coordinate.  A cell coordinate is only where the value currently sits; the
identity survives inserted rows, inserted or reordered period columns, and a
rolled-forward grid.

Workbook contract (see the skill's ``references/model-rules.md``)
-----------------------------------------------------------------
The override sheet holds one three-row block per driver — default, override,
active, in that order, rows adjacent:

* ``<driver> | default``        — retained default, a blue hardcode
* ``<driver> | YOUR override``  — user override, blank until filled in
* ``<driver> | active input``   — formula selecting override when non-blank

Only the override row carries the identity; the driver name is its label with
the ``| YOUR override`` suffix removed.

Periods are labelled in a header row (default row 6), one label per column,
e.g. ``Q3 2026E``.  A blank override cell means "use the default".  Zero is a
valid override.

The active-input formula is the driver's *definition*.  It is recorded with
cell references normalised to ``{d}`` / ``{o}`` / ``{a}`` (default, override,
active row) and the driver's own column, so a block that merely moves rows or
columns keeps the same definition signature while a changed calculation is
detected and withheld from an automatic restore.

CLI
---
    python3 overrides.py check   WB.xlsx
    python3 overrides.py extract WB.xlsx --out overrides.json
    python3 overrides.py restore SRC.xlsx DST.xlsx --overrides overrides.json [--report report.json]
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, asdict
import hashlib
import json
from pathlib import Path
import re
import sys

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter as L

OVERRIDE_SUFFIX = "YOUR override"
DEFAULT_SUFFIX = "default"
ACTIVE_SUFFIX = "active input"

PERIOD_RE = re.compile(r"^(?:Q([1-4])\s*(\d{4})|(\d{4})\s*Q([1-4]))\s*([AE])$", re.IGNORECASE)
REF_RE = re.compile(r"([A-Za-z]{1,3})(\d+)")


class OverrideError(Exception):
    """Incompatible workbook metadata or an invalid override value."""


def canonical_period(label: str) -> str:
    """``"Q3 2026E"`` -> ``"2026Q3E"``.  Idempotent; raises on any other shape."""
    match = PERIOD_RE.match(str(label).strip())
    if not match:
        raise OverrideError(f"Unrecognised fiscal period label: {label!r}")
    quarter, year, year2, quarter2, flag = match.groups()
    return f"{year or year2}Q{quarter or quarter2}{flag.upper()}"


@dataclass(frozen=True)
class Driver:
    name: str
    default_row: int
    override_row: int
    active_row: int
    number_format: str


@dataclass(frozen=True)
class Override:
    driver: str
    period: str
    value: float
    cell: str
    number_format: str
    definition: str


@dataclass
class OverrideSet:
    sheet: str
    header_row: int
    label_col: int
    periods: dict[int, str] = field(default_factory=dict)
    drivers: dict[str, Driver] = field(default_factory=dict)
    overrides: dict[str, Override] = field(default_factory=dict)
    source: str = ""

    def key(self, driver: str, period: str) -> str:
        return f"{driver}\u0000{canonical_period(period)}"

    def get(self, driver: str, period: str) -> Override | None:
        """Look up by driver and period label, accepting the workbook's own label text."""
        return self.overrides.get(self.key(driver, period))

    def save(self, path: str | Path) -> Path:
        payload = {
            "sheet": self.sheet,
            "header_row": self.header_row,
            "label_col": self.label_col,
            "source": self.source,
            "periods": {str(col): period for col, period in self.periods.items()},
            "drivers": {name: asdict(driver) for name, driver in self.drivers.items()},
            "overrides": [asdict(item) for item in self.overrides.values()],
        }
        path = Path(path)
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "OverrideSet":
        payload = json.loads(Path(path).read_text())
        result = cls(
            sheet=payload["sheet"],
            header_row=payload["header_row"],
            label_col=payload["label_col"],
            source=payload.get("source", ""),
        )
        result.periods = {int(col): period for col, period in payload["periods"].items()}
        result.drivers = {name: Driver(**item) for name, item in payload["drivers"].items()}
        result.overrides = {
            result.key(item["driver"], item["period"]): Override(**item)
            for item in payload["overrides"]
        }
        return result


@dataclass
class RestoreReport:
    restored: list[Override] = field(default_factory=list)
    retired_period: list[Override] = field(default_factory=list)
    removed_driver: list[Override] = field(default_factory=list)
    definition_changed: list[Override] = field(default_factory=list)
    original_unchanged: bool = False
    destination: str = ""

    @property
    def needs_review(self) -> list[Override]:
        return self.definition_changed

    def lines(self) -> list[str]:
        out = [
            f"{len(self.restored)} restored, {len(self.retired_period)} retired period(s), "
            f"{len(self.removed_driver)} removed driver(s), "
            f"{len(self.definition_changed)} changed definition(s)"
        ]
        for item in self.retired_period:
            out.append(f"  retired (period no longer in the forecast grid): {item.driver} {item.period} = {item.value}")
        for item in self.removed_driver:
            out.append(f"  removed driver (not restored): {item.driver} {item.period} = {item.value}")
        for item in self.definition_changed:
            out.append(f"  CHANGED DEFINITION, review required: {item.driver} {item.period} = {item.value}")
        out.append(f"  original workbook unchanged: {self.original_unchanged}")
        return out

    def to_json(self, path: str | Path) -> Path:
        payload = {
            "destination": self.destination,
            "original_unchanged": self.original_unchanged,
            "restored": [asdict(item) for item in self.restored],
            "retired_period": [asdict(item) for item in self.retired_period],
            "removed_driver": [asdict(item) for item in self.removed_driver],
            "definition_changed": [asdict(item) for item in self.definition_changed],
        }
        path = Path(path)
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _suffix_match(text: str, suffix: str) -> str | None:
    """Return the driver name if ``text`` ends with the suffix (case-insensitive)."""
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if stripped.casefold().endswith(suffix.strip().casefold()):
        return stripped[: len(stripped) - len(suffix.strip())].strip().rstrip("|").strip()
    return None


def _signature(formula, col_letter: str, rows: dict[int, str]) -> str:
    """Normalise a driver's active-input formula so row/column moves do not matter."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return str(formula)

    def replace(match: re.Match) -> str:
        col, row = match.group(1).upper(), int(match.group(2))
        if col == col_letter.upper() and row in rows:
            return "{%s}" % rows[row]
        return match.group(0)

    return REF_RE.sub(replace, formula)


def _numeric(cell, context: str) -> float:
    if isinstance(cell.value, bool):
        raise OverrideError(f"{context}: boolean is not a numeric override")
    if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
        raise OverrideError(f"{context}: formulas are not valid overrides")
    if not isinstance(cell.value, (int, float)):
        raise OverrideError(f"{context}: {cell.value!r} is not numeric")
    return float(cell.value)


def extract(path: str | Path, sheet: str = "Assumptions", header_row: int = 6,
            label_col: int = 2) -> OverrideSet:
    """Read every designated override without modifying the workbook."""
    path = Path(path)
    workbook = load_workbook(path, data_only=False)
    if sheet not in workbook.sheetnames:
        raise OverrideError(f"{path.name}: no sheet named {sheet!r} (found {workbook.sheetnames})")
    ws = workbook[sheet]

    periods: dict[int, str] = {}
    for col in range(label_col + 1, ws.max_column + 1):
        value = ws.cell(header_row, col).value
        if value is None or str(value).strip() == "":
            continue
        periods[col] = canonical_period(value)
    if not periods:
        raise OverrideError(f"{path.name}: no period labels in row {header_row} of {sheet}")
    if len(set(periods.values())) != len(periods):
        raise OverrideError(f"{path.name}: duplicate period labels in row {header_row}: {list(periods.values())}")

    drivers: dict[str, Driver] = {}
    for row in range(header_row + 1, ws.max_row + 1):
        name = _suffix_match(ws.cell(row, label_col).value, OVERRIDE_SUFFIX)
        if not name:
            continue
        if name in drivers:
            raise OverrideError(f"{path.name}: duplicate override row for driver {name!r}")
        default_row, active_row = row - 1, row + 1
        if not _suffix_match(ws.cell(default_row, label_col).value, DEFAULT_SUFFIX):
            raise OverrideError(f"{path.name}: row {default_row} above {name!r} is not a default row")
        if not _suffix_match(ws.cell(active_row, label_col).value, ACTIVE_SUFFIX):
            raise OverrideError(f"{path.name}: row {active_row} below {name!r} is not an active-input row")
        drivers[name] = Driver(name=name, default_row=default_row, override_row=row,
                               active_row=active_row,
                               number_format=ws.cell(row, min(periods)).number_format)
    if not drivers:
        raise OverrideError(f"{path.name}: no '{OVERRIDE_SUFFIX}' driver rows found on {sheet}")

    result = OverrideSet(sheet=sheet, header_row=header_row, label_col=label_col,
                         periods=periods, drivers=drivers, source=str(path))
    for name, driver in drivers.items():
        rows = {driver.default_row: "d", driver.override_row: "o", driver.active_row: "a"}
        for col, period in periods.items():
            letter = L(col)
            cell = ws.cell(driver.override_row, col)
            definition = _signature(ws.cell(driver.active_row, col).value, letter, rows)
            if cell.value is None:
                continue
            key = result.key(name, period)
            if key in result.overrides:
                raise OverrideError(f"{path.name}: duplicate override identity {name!r} / {period}")
            context = f"{path.name}: {sheet}!{cell.coordinate} ({name} / {period})"
            result.overrides[key] = Override(
                driver=name, period=period, value=_numeric(cell, context), cell=cell.coordinate,
                number_format=cell.number_format or driver.number_format, definition=definition)
    return result


def restore(template: str | Path, destination: str | Path, overrides: OverrideSet,
            allow_definition_change: bool = False) -> RestoreReport:
    """Write ``template`` to ``destination`` with the recorded overrides restored.

    ``template`` is the freshly rebuilt workbook (new grid, current defaults); the
    workbook the overrides were extracted from is never opened.  Placement comes from
    the template's own period header and driver rows, so a rolled-forward grid and
    moved blocks are handled by identity, not by coordinate.
    """
    template, destination = Path(template).resolve(), Path(destination).resolve()
    if template == destination:
        raise OverrideError("refusing to write over the template workbook; pass a separate destination")
    before = sha256(template)

    workbook = load_workbook(template, data_only=False)
    if overrides.sheet not in workbook.sheetnames:
        raise OverrideError(f"{template.name}: no sheet named {overrides.sheet!r}")
    ws = workbook[overrides.sheet]

    periods: dict[int, str] = {}
    for col in range(overrides.label_col + 1, ws.max_column + 1):
        value = ws.cell(overrides.header_row, col).value
        if value is None or str(value).strip() == "":
            continue
        periods[col] = canonical_period(value)
    by_period = {period: col for col, period in periods.items()}

    rows_by_driver: dict[str, int] = {}
    for row in range(overrides.header_row + 1, ws.max_row + 1):
        name = _suffix_match(ws.cell(row, overrides.label_col).value, OVERRIDE_SUFFIX)
        if not name:
            continue
        if name in rows_by_driver:
            raise OverrideError(f"{template.name}: duplicate override row for driver {name!r}")
        rows_by_driver[name] = row

    report = RestoreReport(destination=str(destination))
    for item in overrides.overrides.values():
        if item.period not in by_period:
            report.retired_period.append(item)
            continue
        row = rows_by_driver.get(item.driver)
        if row is None:
            report.removed_driver.append(item)
            continue
        col = by_period[item.period]
        driver = overrides.drivers[item.driver]
        # The block may have moved rows: rebuild the row map around its new location
        # so a moved block keeps its definition signature.
        shift = row - driver.override_row
        rows = {driver.default_row + shift: "d", row: "o", driver.active_row + shift: "a"}
        current = _signature(ws.cell(driver.active_row + shift, col).value, L(col), rows)
        if current != item.definition and not allow_definition_change:
            report.definition_changed.append(item)
            continue
        cell = ws.cell(row, col)
        cell.value = item.value
        cell.number_format = item.number_format
        report.restored.append(item)

    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    report.original_unchanged = sha256(template) == before
    if not report.original_unchanged:
        raise OverrideError(f"{template} changed during restore; the output may be unusable")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check", "extract", "restore"])
    parser.add_argument("workbook", nargs="?",
                        help="workbook to read; for restore, the freshly rebuilt template")
    parser.add_argument("destination", nargs="?", help="restore output path (template is never written)")
    parser.add_argument("--sheet", default="Assumptions")
    parser.add_argument("--header-row", type=int, default=6)
    parser.add_argument("--overrides", help="overrides JSON written by `extract`")
    parser.add_argument("--out", help="write the extracted overrides JSON here")
    parser.add_argument("--report", help="write the restore report JSON here")
    parser.add_argument("--allow-definition-change", action="store_true",
                        help="restore overrides whose driver definition changed (flags them anyway)")
    args = parser.parse_args(argv)

    if args.command == "check":
        found = extract(args.workbook, args.sheet, args.header_row)
        print(f"{len(found.drivers)} drivers, periods {sorted(set(found.periods.values()))}")
        print(f"{len(found.overrides)} override(s):")
        for item in found.overrides.values():
            print(f"  {item.driver} {item.period} = {item.value} @ {item.cell} [{item.number_format}]")
        return 0

    if args.command == "extract":
        found = extract(args.workbook, args.sheet, args.header_row)
        out = Path(args.out or "overrides.json")
        found.save(out)
        print(f"{len(found.overrides)} override(s) written to {out}")
        return 0

    if not args.overrides or not args.destination:
        parser.error("restore needs DESTINATION and --overrides")
    report = restore(args.workbook, args.destination, OverrideSet.load(args.overrides),
                     allow_definition_change=args.allow_definition_change)
    for line in report.lines():
        print(line)
    if args.report:
        report.to_json(args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
