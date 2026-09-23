"""Command entry points for a project using the v2 generic workbook core.

A project contains model_spec.json, evidence/actuals.csv, drivers.csv and exactly one
model_<TICKER>.py file exposing ``company_module``.  The module supplies company formulas;
``build``/``check`` only load frozen artifacts and invoke the shared engine, while ``rollover``
delegates to :mod:`rollover` to carry driver values forward without carrying an approval.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any, Literal

try:
    from .checks import CheckReport, check_fast, check_full
    from .engine import build_workbook
    from .evidence import load_fact_map, replay_frozen_evidence
    from .rollover import rollover
except ImportError:  # pragma: no cover - direct project invocation
    from checks import CheckReport, check_fast, check_full
    from engine import build_workbook
    from evidence import load_fact_map, replay_frozen_evidence
    from rollover import rollover


def _json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


# interfaces.md §5: frozen actuals must carry visible, immutable lineage for every value.
_ACTUALS_COLUMNS = (
    "metric", "period", "value", "units", "basis", "dimension", "transform", "locator",
    "lineage_scheme", "lineage_path", "lineage_key", "provenance_status", "notes",
)
_LINEAGE_COLUMNS = ("lineage_scheme", "lineage_path", "lineage_key")
_UNAVAILABLE_STATUSES = frozenset({"unresolved", "unavailable", "missing"})


def _row_problems(row: dict[str, Any], line: int) -> list[str]:
    label = f"actuals.csv line {line} ({row.get('metric', '?')} {row.get('period', '?')})"
    problems: list[str] = []
    for column in ("metric", "period", "provenance_status"):
        if not str(row.get(column) or "").strip():
            problems.append(f"{label}: blank {column}")
    value = str(row.get("value") or "").strip()
    status = str(row.get("provenance_status") or "").strip().lower()
    notes = str(row.get("notes") or "").strip()
    if value:
        blank = [c for c in _LINEAGE_COLUMNS if not str(row.get(c) or "").strip()]
        if blank:
            problems.append(f"{label}: populated value lacks lineage ({', '.join(blank)})")
        if "<resolved-table>" in str(row.get("lineage_path") or ""):
            problems.append(f"{label}: populated value has placeholder lineage path")
        if status in _UNAVAILABLE_STATUSES or status == "error":
            problems.append(f"{label}: populated value marked {status}")
    elif status == "error":
        problems.append(f"{label}: evidence resolver error is not an unavailable fact")
    elif not notes or notes.lower() in _UNAVAILABLE_STATUSES:
        # A specific reason, not a bare status token, must be visible on every blank fact.
        problems.append(f"{label}: unavailable value has no specific missing reason")
    return problems


def _coverage_problems(mappings, historical: list[str], rows: list[dict[str, Any]]) -> list[str]:
    """Every `(metric, historical period)` a fact-map entry covers needs a frozen actuals row.

    `mapping.periods` limits an entry's coverage; an absent predicate covers every historical
    quarter. Disjoint entries for one metric (interfaces.md §2) each contribute their own periods.
    """
    problems: list[str] = []
    present = {(str(row.get("metric") or "").strip(), str(row.get("period") or "").strip())
               for row in rows}
    for mapping in mappings:
        for period in (mapping.periods if mapping.periods is not None else historical):
            if period in historical and (mapping.metric, period) not in present:
                problems.append(
                    f"fact_map.json declares {mapping.metric} {period} but actuals.csv has no row")
    return problems


def _validate_evidence(project_dir: Path) -> None:
    """Fail closed before build when frozen evidence cannot be traced to immutable sources.

    Requires `model_spec.json` to declare its historical quarters and `fact_map.json` to be a
    parseable object. Every `(metric, historical period)` the map covers needs an actuals.csv row;
    rows are unique per `(metric, period, dimension)`; populated values need immutable lineage and
    a non-unavailable provenance status; blank values need a specific, non-empty missing reason
    (a bare status token is not enough).
    """
    problems: list[str] = []

    spec: dict[str, Any] | None = None
    spec_path = project_dir / "model_spec.json"
    if not spec_path.is_file():
        problems.append("missing model_spec.json")
    else:
        try:
            spec = _json(spec_path)
        except ValueError as exc:
            problems.append(f"model_spec.json: {exc}")

    historical: list[str] | None = None
    if spec is not None:
        periods = spec.get("periods")
        declared = periods.get("historical_quarters") if isinstance(periods, dict) else None
        if isinstance(declared, list) and declared and all(isinstance(p, str) for p in declared):
            historical = list(declared)
        else:
            problems.append("model_spec.json periods.historical_quarters is required")

    mappings = None
    fact_map_path = project_dir / "fact_map.json"
    if not fact_map_path.is_file():
        problems.append("missing fact_map.json")
    else:
        try:
            _json(fact_map_path)
        except ValueError as exc:
            problems.append(f"fact_map.json: {exc}")
        else:
            try:
                mappings = load_fact_map(fact_map_path)
            except ValueError as exc:
                problems.append(f"fact_map.json: {exc}")

    rows: list[dict[str, Any]] | None = None
    actuals_path = project_dir / "evidence" / "actuals.csv"
    if not actuals_path.is_file():
        problems.append("missing evidence/actuals.csv")
    else:
        with actuals_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing_columns = [c for c in _ACTUALS_COLUMNS if c not in (reader.fieldnames or [])]
            if missing_columns:
                problems.append(f"actuals.csv is missing columns: {', '.join(missing_columns)}")
            else:
                rows = list(reader)
        if rows is not None:
            seen: dict[tuple[str, str, str], int] = {}
            for line, row in enumerate(rows, start=2):
                problems.extend(_row_problems(row, line))
                key = (str(row.get("metric") or "").strip(),
                       str(row.get("period") or "").strip(),
                       str(row.get("dimension") or "").strip())
                if key in seen:
                    problems.append(
                        f"actuals.csv line {line} ({key[0]} {key[1]}): duplicate row "
                        f"(first at line {seen[key]})")
                else:
                    seen[key] = line

    if mappings is not None and historical is not None and rows is not None:
        problems.extend(_coverage_problems(mappings, historical, rows))

    if spec is not None and mappings is not None and rows is not None:
        benchmarks_path = project_dir / "evidence" / "benchmarks.csv"
        benchmarks = _rows(benchmarks_path) if benchmarks_path.is_file() else []
        try:
            replay_frozen_evidence(spec, rows, benchmarks, mappings)
        except (ValueError, OSError, KeyError) as exc:
            problems.append(f"evidence replay: {exc}")

    if problems:
        raise ValueError("invalid frozen evidence: " + "; ".join(problems))


def _module(project_dir: Path, ticker: str):
    path = project_dir / f"model_{ticker}.py"
    if not path.is_file():
        raise ValueError(f"missing company module {path.name}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    company_module = getattr(module, "company_module", None)
    if company_module is None:
        raise ValueError(f"{path.name} must expose company_module")
    return company_module


def _output(project_dir: Path, spec: dict[str, Any]) -> Path:
    workbook = spec.get("workbook")
    if not isinstance(workbook, dict) or not isinstance(workbook.get("filename"), str):
        raise ValueError("model_spec.json workbook.filename is required")
    return project_dir / workbook["filename"]


def build(project_dir: Path) -> Path:
    """Build once from frozen evidence and drivers; overwrite is deliberately not supported."""
    project_dir = Path(project_dir)
    _validate_evidence(project_dir)
    spec = _json(project_dir / "model_spec.json")
    actuals = _rows(project_dir / "evidence" / "actuals.csv")
    drivers = _rows(project_dir / "drivers.csv")
    approval_path = project_dir / "drivers.approval.json"
    approval = _json(approval_path) if approval_path.exists() else None
    workbook = build_workbook(spec, actuals, drivers, _module(project_dir, str(spec["ticker"])), approval).workbook
    output = _output(project_dir, spec)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing delivery: {output}")
    workbook.save(output)
    return output


def check(project_dir: Path, mode: Literal["fast", "full"] = "fast") -> CheckReport:
    return check_fast(project_dir) if mode == "fast" else check_full(project_dir)


def _print_rollover(report: dict[str, Any], report_path: Path | None) -> None:
    delivery = report.get("delivery") or {}
    print(f"rolled project: {report['output_project']}")
    print(f"carried drivers: {len(report['carried'])}; withheld: {len(report['withheld'])}; "
          f"removed: {len(report['removed_drivers'])}; retired periods: {report['retired_periods']}")
    if delivery:
        print(f"delivery: {delivery.get('workbook')} "
              f"(ok={delivery.get('ok')}, checks={delivery.get('checks')})")
    if report_path is not None:
        print(f"report: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path,
                        help="prepared project directory (the new project for rollover)")
    parser.add_argument("command", choices=("build", "check", "rollover"))
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--prior-project", type=Path,
                        help="rollover: prior prepared project to carry driver values from")
    parser.add_argument("--output-project", type=Path,
                        help="rollover: fresh directory to write the rolled project into")
    parser.add_argument("--report", type=Path,
                        help="rollover: optional path for the machine-readable rollover report")
    args = parser.parse_args()
    if args.command == "rollover":
        if args.prior_project is None or args.output_project is None:
            parser.error("rollover requires --prior-project and --output-project")
        report = rollover(args.prior_project, args.project_dir, args.output_project, args.report)
        _print_rollover(report, args.report)
        return
    if args.command == "build":
        print(build(args.project_dir))
        return
    report = check(args.project_dir, "full" if args.full else "fast")
    print(f"{report.workbook}: {report.checks} checks")
    for coverage in report.coverage:
        print(f"COVERAGE: {coverage}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    if report.failures:
        raise SystemExit("\n".join(report.failures))


if __name__ == "__main__":
    main()
