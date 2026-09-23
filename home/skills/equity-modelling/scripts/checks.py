"""Small, generic structural checks for workbooks built by :mod:`engine`.

Company accounting identities belong in the company project.  These checks enforce only the
shared workbook contract: readable workbook, no formula errors, valid defined names and no
unapproved values in the Drivers sheet.  ``check_full`` also inspects cached formula results:
cached Excel errors fail, while a formula-bearing workbook with no cached results only warns,
because openpyxl loads caches but never recalculates them.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook


@dataclass(frozen=True)
class CheckReport:
    workbook: Path
    checks: int
    failures: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures


def _spec(project_dir: Path) -> dict:
    import json
    spec = json.loads((project_dir / "model_spec.json").read_text())
    if not isinstance(spec, dict):
        raise ValueError("model_spec.json must contain an object")
    return spec


def _workbook_path(project_dir: Path, spec: dict | None = None) -> Path:
    spec = spec or _spec(project_dir)
    filename = spec.get("workbook", {}).get("filename")
    if not isinstance(filename, str) or not filename:
        raise ValueError("model_spec.json workbook.filename is required")
    return project_dir / filename


def _formula_errors(workbook) -> Iterable[str]:
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and "#REF!" in cell.value:
                    yield f"{sheet.title}!{cell.coordinate} contains #REF!"


def _is_formula(cell) -> bool:
    return isinstance(cell.value, str) and cell.value.startswith("=")


def _cached_error(value: object) -> str | None:
    """Excel stores a cached formula error, e.g. ``#NAME?`` or ``#DIV/0!``, as a string."""
    return value if isinstance(value, str) and value.startswith("#") else None


def _formula_cache_counts(formulas, values) -> tuple[int, int]:
    """Count formula cells and how many carry a cached calculation result.

    A ``data_only`` workbook exposes ``None`` for a formula whose result was never stored, so a
    zero cached count marks a workbook with no evaluated formula outputs at all.
    """
    total = cached = 0
    for formula_sheet, value_sheet in zip(formulas.worksheets, values.worksheets):
        for row in formula_sheet.iter_rows():
            for formula_cell in row:
                if not _is_formula(formula_cell):
                    continue
                total += 1
                if value_sheet[formula_cell.coordinate].value is not None:
                    cached += 1
    return total, cached


def _full_formula_checks(formulas, values) -> Iterable[str]:
    """Shared checks that need both formula text and cached recalculation results."""
    for formula_sheet, value_sheet in zip(formulas.worksheets, values.worksheets):
        for row in formula_sheet.iter_rows():
            for formula_cell in row:
                if not _is_formula(formula_cell):
                    continue
                location = f"{formula_sheet.title}!{formula_cell.coordinate}"
                if "!" in formula_cell.value:
                    yield f"{location} uses a positional cross-sheet reference"
                error = _cached_error(value_sheet[formula_cell.coordinate].value)
                if error is not None:
                    yield f"{location} recalculates to {error}"


def check_fast(project_dir: Path) -> CheckReport:
    """Validate only shared structural invariants; never claims company accounting parity."""
    project_dir = Path(project_dir)
    spec = _spec(project_dir)
    path = _workbook_path(project_dir, spec)
    failures: list[str] = []
    warnings: list[str] = []
    checks = 0
    if not path.is_file():
        return CheckReport(path, 1, ("workbook is missing",))
    formulas = load_workbook(path, data_only=False)
    values = load_workbook(path, data_only=True)
    expected = spec.get("workbook", {}).get("sheets")
    checks += 1
    if not isinstance(expected, list) or not expected:
        failures.append("model_spec.json workbook.sheets is required")
    elif formulas.sheetnames != expected:
        failures.append(f"workbook sheets differ from model_spec.json: {formulas.sheetnames!r}")
    checks += 1
    failures.extend(_formula_errors(formulas))
    for defined_name in formulas.defined_names.values():
        checks += 1
        if "#REF!" in str(defined_name.attr_text):
            failures.append(f"defined name {defined_name.name} contains #REF!")
    if "Drivers" in formulas.sheetnames:
        formulas_drivers, value_drivers = formulas["Drivers"], values["Drivers"]
        for row in range(7, formulas_drivers.max_row + 1):
            status = formulas_drivers.cell(row, 3).value
            if status != "proposed":
                continue
            for col in range(4, formulas_drivers.max_column + 1):
                checks += 1
                if value_drivers.cell(row, col).value not in (None, ""):
                    failures.append(f"Drivers!{value_drivers.cell(row, col).coordinate} activates a proposed input")
    if "Inputs" in formulas.sheetnames:
        # Proposed assumptions are reviewable on Inputs, but a closed gate must leave
        # every company-sheet forecast output blank even if someone edits the XLSX.
        gate = spec.get("forecast_gate", {})
        if not isinstance(gate, dict) or gate.get("approved") is not True:
            inputs = formulas["Inputs"]
            for row in range(7, inputs.max_row + 1):
                if inputs.cell(row, 3).value == "Approved":
                    failures.append(f"Inputs!C{row} marks an assumption approved while the forecast gate is closed")
            periods = spec.get("periods", {})
            first_forecast = 3 + len(periods.get("historical_quarters", []))
            forecast_count = len(periods.get("forecast_quarters", []))
            for sheet in formulas.worksheets:
                if sheet.title in {"Inputs", "SourceData"}:
                    continue
                for row in range(7, sheet.max_row + 1):
                    for col in range(first_forecast, first_forecast + forecast_count):
                        checks += 1
                        if sheet.cell(row, col).value not in (None, ""):
                            failures.append(f"{sheet.title}!{sheet.cell(row, col).coordinate} activates an unapproved forecast")
    if not formulas.defined_names:
        warnings.append("workbook has no defined names")
    return CheckReport(path, checks, tuple(failures), tuple(warnings))


def check_full(project_dir: Path) -> CheckReport:
    """Run shared structural and cached-formula checks; company checks remain additive.

    Cached Excel errors fail.  A formula-bearing workbook with no cached calculation results only
    warns: the checks cannot evaluate formulas openpyxl has not recalculated, and a stale or absent
    cache must not be mistaken for a clean evaluation.
    """
    project_dir = Path(project_dir)
    report = check_fast(project_dir)
    if not report.workbook.is_file():
        return report
    formulas = load_workbook(report.workbook, data_only=False)
    values = load_workbook(report.workbook, data_only=True)
    failures = list(report.failures)
    failures.extend(_full_formula_checks(formulas, values))
    warnings = list(report.warnings)
    coverage: list[str] = []
    actuals_path = Path(project_dir) / "evidence" / "actuals.csv"
    fact_map_path = Path(project_dir) / "fact_map.json"
    benchmarks_path = Path(project_dir) / "evidence" / "benchmarks.csv"
    missing_evidence = [str(path.relative_to(project_dir)) for path in (actuals_path, fact_map_path)
                        if not path.is_file()]
    failures.extend(f"mandatory frozen evidence is missing: {relative}" for relative in missing_evidence)
    if not missing_evidence:
        try:
            try:
                from .evidence import load_fact_map, replay_frozen_evidence
            except ImportError:  # direct script invocation
                from evidence import load_fact_map, replay_frozen_evidence
            spec = _spec(Path(project_dir))
            with actuals_path.open(newline="") as handle:
                actuals = list(csv.DictReader(handle))
            mappings = load_fact_map(fact_map_path)
            if benchmarks_path.is_file():
                with benchmarks_path.open(newline="") as handle:
                    benchmarks = list(csv.DictReader(handle))
            else:
                benchmarks = []
            result = replay_frozen_evidence(spec, actuals, benchmarks, mappings)
            coverage.append(f"source replay: {result['actuals_replayed']} actuals, "
                            f"{result['benchmarks_replayed']} benchmarks")
        except Exception as exc:
            failures.append(f"evidence replay failed: {exc}")
    formulas_seen, cached = _formula_cache_counts(formulas, values)
    checks = report.checks + formulas_seen
    if formulas_seen:
        checks += 1
        if cached == 0:
            warnings.append(
                f"workbook has {formulas_seen} formula(s) but no cached calculation results; "
                "recalculated outputs were not evaluated"
            )
    return CheckReport(report.workbook, checks, tuple(failures), tuple(warnings), tuple(coverage))
