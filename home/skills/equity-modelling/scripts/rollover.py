"""Generic, project-level driver rollover for v2 prepared projects.

Rollover moves a prepared project one period forward without mutating either input project.  It
carries reusable driver *values* only, keyed by stable ``driver_id`` and by the forecast-period
column, from a prior project's ``drivers.csv`` into a copy of a new project's ``drivers.csv``.

Rollover never carries an approval.  Every output row is marked ``proposed``, approval fields are
cleared, and ``drivers.approval.json`` is not copied, so a rebuilt workbook keeps its forecast
formulas blank until a fresh approval exists.  A renamed or redefined driver, a removed driver,
and a retired period are reported rather than guessed; a deliberate blank stays blank.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

_PERIOD = re.compile(r"^(\d{4})Q([1-4])E?$")
_STATUS = "status"
_APPROVAL_FIELDS = ("approved_by", "approved_on", "approval_id")
_DEFINITION_FIELDS = ("driver_name", "unit")
_APPROVAL_MANIFEST = "drivers.approval.json"


class RolloverError(ValueError):
    """A project cannot be rolled over safely."""


@dataclass(frozen=True)
class _DriverTable:
    path: Path
    fieldnames: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    periods: Mapping[str, str]  # canonical period -> CSV header

    @property
    def by_id(self) -> dict[str, dict[str, str]]:
        return {str(row["driver_id"]).strip(): row for row in self.rows}


def _period_columns(path: Path, fieldnames: Iterable[str]) -> dict[str, str]:
    """Map each canonical forecast period to the CSV header that carries it."""
    columns: dict[str, str] = {}
    for name in fieldnames:
        match = _PERIOD.match(str(name or "").strip())
        if not match:
            continue
        canonical = f"{match.group(1)}Q{match.group(2)}"
        if canonical in columns:
            raise RolloverError(
                f"{path}: duplicate forecast-period columns {columns[canonical]!r} and {name!r}")
        columns[canonical] = name
    return columns


def _read_drivers(project_dir: Path) -> _DriverTable:
    project_dir = Path(project_dir)
    path = project_dir / "drivers.csv"
    if not path.is_file():
        raise RolloverError(f"missing drivers.csv: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        rows = tuple(reader)
    if not fieldnames:
        raise RolloverError(f"{path} has no header row")
    if len(fieldnames) != len(set(fieldnames)):
        raise RolloverError(f"{path} has duplicate header names")
    if "driver_id" not in fieldnames:
        raise RolloverError(f"{path} is missing the driver_id column")
    seen: set[str] = set()
    for line, row in enumerate(rows, start=2):
        driver_id = str(row.get("driver_id") or "").strip()
        if not driver_id:
            raise RolloverError(f"{path} line {line}: blank driver_id")
        if driver_id in seen:
            raise RolloverError(f"{path} line {line}: duplicate driver_id {driver_id!r}")
        seen.add(driver_id)
    return _DriverTable(path, fieldnames, rows, _period_columns(path, fieldnames))


def _definition_changed(prior: Mapping[str, str], new: Mapping[str, str]) -> bool:
    """Compare only definition columns present in both rows; absence carries no information."""
    for field in _DEFINITION_FIELDS:
        if field in prior and field in new:
            if str(prior.get(field) or "").strip() != str(new.get(field) or "").strip():
                return True
    return False


def _rolled_rows(prior: _DriverTable, new: _DriverTable) -> tuple[list[dict[str, str]], dict[str, Any]]:
    prior_by_id = prior.by_id
    new_ids = [str(row["driver_id"]).strip() for row in new.rows]
    overlapping = [period for period in new.periods if period in prior.periods]
    retired = [period for period in prior.periods if period not in new.periods]
    carried: list[dict[str, Any]] = []
    withheld: list[dict[str, str]] = []
    added: list[str] = []
    rows: list[dict[str, str]] = []
    for new_row in new.rows:
        row = dict(new_row)
        driver_id = str(row["driver_id"]).strip()
        prior_row = prior_by_id.get(driver_id)
        if prior_row is None:
            added.append(driver_id)
        elif _definition_changed(prior_row, new_row):
            withheld.append({"driver_id": driver_id, "reason": "driver definition changed"})
        else:
            values = {period: str(prior_row.get(prior.periods[period]) or "") for period in overlapping}
            for period, header in new.periods.items():
                if period in values:
                    row[header] = values[period]
            carried.append({"driver_id": driver_id, "periods": values})
        row[_STATUS] = "proposed"
        for field in _APPROVAL_FIELDS:
            if field in row:
                row[field] = ""
        rows.append(row)
    removed = [driver_id for driver_id in prior_by_id if driver_id not in set(new_ids)]
    report: dict[str, Any] = {
        "overlapping_periods": overlapping,
        "retired_periods": retired,
        "carried": carried,
        "withheld": withheld,
        "added_drivers": added,
        "removed_drivers": removed,
    }
    return rows, report


def _output_fieldnames(new: _DriverTable) -> list[str]:
    fieldnames = list(new.fieldnames)
    if _STATUS not in fieldnames:
        fieldnames.append(_STATUS)
    return fieldnames


def _delivery_filename(project_dir: Path) -> str | None:
    spec_path = project_dir / "model_spec.json"
    if not spec_path.is_file():
        return None
    try:
        spec = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise RolloverError(f"{spec_path} is not valid JSON: {exc}") from exc
    workbook = spec.get("workbook") if isinstance(spec, dict) else None
    filename = workbook.get("filename") if isinstance(workbook, dict) else None
    return filename if isinstance(filename, str) and filename else None


def _copy_project(source: Path, destination: Path, exclude: set[str]) -> None:
    """Copy the prepared project, skipping the delivery workbook and any approval manifest."""
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name == "__pycache__"}
        base = Path(directory)
        for name in names:
            relative = (base / name).relative_to(source).as_posix()
            if relative in exclude:
                ignored.add(name)
        return ignored

    shutil.copytree(source, destination, ignore=ignore)


def _build_and_check(project_dir: Path) -> dict[str, Any]:
    """Run the existing generic build/check and summarize the delivery outcome."""
    try:
        from .cli import build as build_project, check as check_project
    except ImportError:  # pragma: no cover - direct invocation from the scripts directory
        from cli import build as build_project, check as check_project
    workbook = build_project(project_dir)
    report = check_project(project_dir)
    return {
        "workbook": str(workbook),
        "ok": bool(report.ok),
        "checks": int(report.checks),
        "failures": list(report.failures),
        "warnings": list(report.warnings),
    }


def rollover(prior_project: Path, new_project: Path, output_project: Path,
             report_path: Path | None = None) -> dict[str, Any]:
    """Write a rolled project into ``output_project`` and return a machine-readable report.

    ``prior_project`` supplies carried driver values; ``new_project`` supplies the new grid and
    metadata.  Neither input is modified.  ``output_project`` must not already exist.  The rolled
    copy is rebuilt and checked with the generic runtime, and its delivery outcome is reported.
    """
    prior_project = Path(prior_project)
    new_project = Path(new_project)
    output_project = Path(output_project)

    if output_project.exists():
        raise RolloverError(f"refusing to overwrite existing output project: {output_project}")
    output_resolved = output_project.resolve()
    if output_resolved.is_relative_to(prior_project.resolve()) or output_resolved.is_relative_to(new_project.resolve()):
        raise RolloverError("output project must be outside both input projects")

    prior = _read_drivers(prior_project)
    new = _read_drivers(new_project)
    rows, report = _rolled_rows(prior, new)

    exclude = {_APPROVAL_MANIFEST}
    delivery_name = _delivery_filename(new_project)
    if delivery_name:
        exclude.add(delivery_name)
    _copy_project(new_project, output_project, exclude)
    if delivery_name and (output_project / delivery_name).exists():
        raise RolloverError(f"refusing to overwrite existing delivery: {output_project / delivery_name}")

    with (output_project / "drivers.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_output_fieldnames(new))
        writer.writeheader()
        writer.writerows(rows)

    report.update({
        "prior_project": str(prior_project),
        "new_project": str(new_project),
        "output_project": str(output_project),
        "approval": {"carried": False, "manifest_copied": False, "statuses": "proposed"},
    })
    report["delivery"] = _build_and_check(output_project)

    if report_path is not None:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
