"""Small generic workbook spine for evidence-led equity models.

The engine owns period placement, approval activation and named references.  Company modules
own model-specific rows and formulas; they receive metric-keyed maps rather than cell addresses.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Protocol

from openpyxl import Workbook

try:  # Supports both `python scripts/engine.py` consumers and package imports.
    from .grid import KeyedReferences, PeriodGrid, labels
    from .style import FMT_M, base, header, label, put
except ImportError:  # pragma: no cover - exercised by company-project entry points.
    from grid import KeyedReferences, PeriodGrid, labels
    from style import FMT_M, base, header, label, put


class EngineError(ValueError):
    """A company project violates the generic workbook contract."""


class CompanyModule(Protocol):
    def workbook_rows(self, actuals: Mapping[str, Mapping[str, float | None]],
                      drivers: Mapping[str, Mapping[str, float | None]],
                      periods: PeriodGrid) -> Mapping[str, Mapping[str, Mapping[str, Any]]]: ...


@dataclass(frozen=True)
class BuildContext:
    workbook: Workbook
    periods: PeriodGrid
    references: KeyedReferences
    actuals: Mapping[str, Mapping[str, float | None]]
    active_drivers: Mapping[str, Mapping[str, float | None]]
    module_rows: Mapping[str, Mapping[str, Any]]


def _forecast_periods(spec: Mapping[str, Any]) -> tuple[str, ...]:
    raw = tuple(spec["periods"]["forecast_quarters"])
    result = tuple(period if period.endswith("E") else period + "E" for period in raw)
    if len(set(result)) != len(result):
        raise EngineError("duplicate forecast periods in model_spec.json")
    return result


def _source_period(period: str) -> str:
    return period[:-1] if period.endswith("E") else period


def _forecast_gate(spec: Mapping[str, Any]) -> bool | None:
    """Return the declared `forecast_gate.approved` state, or `None` when undeclared.

    A declared gate must be an explicit boolean so an ambiguous value can never silently
    activate a forecast.  An undeclared gate is treated as not approved: activation then
    fails closed rather than defaulting to active.
    """
    gate = spec.get("forecast_gate")
    if gate is None:
        return None
    if not isinstance(gate, Mapping):
        raise EngineError("model_spec.json forecast_gate must be an object")
    approved = gate.get("approved")
    if not isinstance(approved, bool):
        raise EngineError("model_spec.json forecast_gate.approved must be a boolean")
    return approved


def approval_digest(triples: Iterable[tuple[str, str, float | int]]) -> str:
    """Hash exact driver/period/value triples in a stable, reviewable representation."""
    normalized = sorted((driver, period, float(value)) for driver, period, value in triples)
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
    return sha256(payload.encode()).hexdigest()


def _approval_hashes(manifest: Mapping[str, Any]) -> Mapping[str, str]:
    approvals = manifest.get("approvals", manifest)
    if not isinstance(approvals, Mapping):
        raise EngineError("approval manifest must be an object keyed by approval_id")
    hashes: dict[str, str] = {}
    for approval_id, entry in approvals.items():
        if isinstance(entry, str):
            digest = entry
        elif isinstance(entry, Mapping):
            digest = entry.get("sha256", entry.get("hash"))
        else:
            raise EngineError(f"approval manifest entry {approval_id!r} is invalid")
        if not isinstance(digest, str) or len(digest) != 64:
            raise EngineError(f"approval manifest entry {approval_id!r} lacks a SHA-256 hash")
        hashes[str(approval_id)] = digest.lower()
    return hashes


def active_driver_values(drivers: Iterable[Mapping[str, Any]], forecast_periods: Iterable[str],
                         approval_manifest: Mapping[str, Any] | None,
                         *, forecast_gate_approved: bool | None = None) -> dict[str, dict[str, float | None]]:
    """Return driver values only for hash-approved complete rows whose forecast gate is open.

    Proposed rows intentionally return blanks.  Approved rows activate only when
    `forecast_gate_approved` is exactly `True`: an undeclared gate (`None`) or a closed gate
    (`False`) fails closed, so a manifest alone can never switch on an unapproved forecast.
    A partial or stale approval is an error rather than a silent partial forecast.
    """
    periods = tuple(forecast_periods)
    values: dict[str, dict[str, float | None]] = {}
    approved: list[Mapping[str, Any]] = []
    for driver in drivers:
        driver_id = str(driver.get("driver_id", ""))
        if not driver_id or driver_id in values:
            raise EngineError(f"driver_id must be unique and non-empty: {driver_id!r}")
        row: dict[str, float | None] = {}
        for period in periods:
            raw = driver.get(_source_period(period))
            if raw in (None, ""):
                row[period] = None
            else:
                try:
                    row[period] = float(raw)
                except (TypeError, ValueError) as exc:
                    raise EngineError(f"{driver_id} {_source_period(period)} is not numeric") from exc
        values[driver_id] = row
        if driver.get("status") == "approved":
            approved.append(driver)
        elif driver.get("status") != "proposed":
            raise EngineError(f"{driver_id} has invalid status {driver.get('status')!r}")

    if not approved:
        return {driver_id: {period: None for period in periods} for driver_id in values}
    if len(approved) != len(values):
        raise EngineError("partial forecast approval activates nothing")
    if forecast_gate_approved is None:
        raise EngineError(
            "model_spec.json must declare forecast_gate.approved before approved forecast inputs can activate")
    if not forecast_gate_approved:
        raise EngineError("forecast_gate.approved is false; approved forecast inputs stay inactive")
    if approval_manifest is None:
        raise EngineError("approved drivers require an approval manifest")

    approval_ids = {str(driver.get("approval_id", "")) for driver in approved}
    if len(approval_ids) != 1 or "" in approval_ids:
        raise EngineError("all approved drivers must share one approval_id")
    expected = _approval_hashes(approval_manifest).get(approval_ids.pop())
    if expected is None:
        raise EngineError("approved driver batch is absent from the approval manifest")
    triples = [(driver_id, _source_period(period), value)
               for driver_id, row in values.items() for period, value in row.items()
               if value is not None]
    if len(triples) != len(values) * len(periods):
        raise EngineError("an approved batch may not contain blank forecast values")
    if approval_digest(triples) != expected:
        raise EngineError("driver values do not match their approved manifest hash")
    return values


def _actual_map(actuals: Iterable[Mapping[str, Any]], historical_periods: Iterable[str]) -> dict[str, dict[str, float | None]]:
    periods = set(historical_periods)
    result: dict[str, dict[str, float | None]] = {}
    seen: set[tuple[str, str]] = set()
    for fact in actuals:
        metric, period = str(fact.get("metric", "")), str(fact.get("period", ""))
        if not metric or period not in periods:
            continue
        key = metric, period
        if key in seen:
            raise EngineError(f"duplicate actual fact {metric} {period}")
        seen.add(key)
        raw = fact.get("value")
        value = None if raw in (None, "") else float(raw)
        result.setdefault(metric, {})[period] = value
    return result


def _write_actuals(ws, data: Mapping[str, Mapping[str, float | None]], grid: PeriodGrid,
                   references: KeyedReferences, price: Mapping[str, Any] | None) -> None:
    price_column = grid.first_column + len(grid.actuals) if price else None
    base(ws, "Source actuals", "Frozen canonical facts; unavailable is blank, never zero.",
         last_col=price_column or 2 + len(grid.actuals), first_width=34, backlink_text=None)
    header(ws, 6, 2, "Metric")
    for period in grid.actuals:
        header(ws, 6, grid.columns[period], labels([period])[0])
    if price_column:
        header(ws, 6, price_column, "Dated benchmark")
    for row, metric in enumerate(sorted(data), start=7):
        label(ws, row, metric)
        for period in grid.actuals:
            value = data[metric].get(period)
            put(ws, row, grid.columns[period], value, "missing" if value is None else "hardcode", FMT_M)
            references.bind(f"actual.{metric}.{period}", ws.title, row, grid.columns[period])
    if price:
        try:
            value = float(price["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EngineError("model_spec.json price.value must be numeric") from exc
        row = 7 + len(data)
        label(ws, row, f"price_dated ({price.get('date', 'undated')})")
        put(ws, row, price_column, value, "hardcode", FMT_M)
        references.bind("benchmark.price_dated", ws.title, row, price_column)


def _write_drivers(ws, drivers: Iterable[Mapping[str, Any]], active: Mapping[str, Mapping[str, float | None]],
                   grid: PeriodGrid, references: KeyedReferences) -> None:
    base(ws, "Forecast drivers", "Proposed inputs do not activate; approved values are manifest-hash bound.",
         last_col=3 + len(grid.forecasts), first_width=32, backlink_text=None)
    header(ws, 6, 2, "Driver")
    header(ws, 6, 3, "Status")
    for period in grid.forecasts:
        header(ws, 6, grid.columns[period] + 1, labels([period])[0], forecast=True)
    for row, driver in enumerate(drivers, start=7):
        driver_id = str(driver["driver_id"])
        label(ws, row, str(driver.get("driver_name", driver_id)))
        put(ws, row, 3, driver.get("status"), "text", "@")
        for period in grid.forecasts:
            value = active[driver_id][period]
            put(ws, row, grid.columns[period] + 1, value, "missing" if value is None else "hardcode", FMT_M)
            references.bind(f"driver.{driver_id}.{period}", ws.title, row, grid.columns[period] + 1)


def _module_rows(module: CompanyModule, actuals, drivers, grid: PeriodGrid) -> Mapping[str, Mapping[str, Mapping[str, Any]]]:
    rows = module.workbook_rows(actuals, drivers, grid)
    if not isinstance(rows, Mapping):
        raise EngineError("company module must return a sheet-keyed mapping")
    return rows


def _write_module_rows(ws, rows: Mapping[str, Any], grid: PeriodGrid,
                       references: KeyedReferences, forecast_active: bool) -> None:
    """Render `{metric: {period: scalar-or-formula}}` without exposing coordinates to modules."""
    if not isinstance(rows, Mapping):
        raise EngineError(f"{ws.title} module output must be a metric-keyed mapping")
    base(ws, ws.title, "Company formulas use metric-keyed defined names only.",
         last_col=2 + len(grid.periods), first_width=34, backlink_text=None)
    header(ws, 6, 2, "Metric")
    for period in grid.periods:
        header(ws, 6, grid.columns[period], labels([period])[0], forecast=period.endswith("E"))
    for row, metric in enumerate(sorted(rows), start=7):
        values = rows[metric]
        if not isinstance(metric, str) or not isinstance(values, Mapping):
            raise EngineError(f"{ws.title} output rows must map metric ids to period-value maps")
        unknown = set(values) - set(grid.periods)
        if unknown:
            raise EngineError(f"{ws.title} {metric} has unknown periods {sorted(unknown)}")
        label(ws, row, metric)
        for period in grid.periods:
            proposed_value = values.get(period)
            if isinstance(proposed_value, str) and proposed_value.startswith("=") and "!" in proposed_value:
                raise EngineError(f"{ws.title} {metric} {period} uses a positional cross-sheet formula")
            value = proposed_value if (not period.endswith("E") or forecast_active) else None
            kind = "formula" if isinstance(value, str) and value.startswith("=") else \
                ("missing" if value is None else "hardcode")
            put(ws, row, grid.columns[period], value, kind, FMT_M)
            references.bind(f"model.{ws.title}.{metric}.{period}", ws.title, row, grid.columns[period])


def build_workbook(spec: Mapping[str, Any], actuals: Iterable[Mapping[str, Any]],
                   drivers: Iterable[Mapping[str, Any]], company_module: CompanyModule,
                   approval_manifest: Mapping[str, Any] | None = None) -> BuildContext:
    """Build the evidence/driver spine and render company-module outputs by metric key."""
    historical = tuple(spec["periods"]["historical_quarters"])
    grid = PeriodGrid(historical, _forecast_periods(spec))
    driver_rows = list(drivers)
    actual_map = _actual_map(actuals, historical)
    active = active_driver_values(driver_rows, grid.forecasts, approval_manifest,
                                  forecast_gate_approved=_forecast_gate(spec))
    workbook_spec = spec.get("workbook")
    sheets = tuple(workbook_spec.get("sheets", ())) if isinstance(workbook_spec, Mapping) else ()
    if not sheets or len(sheets) != len(set(sheets)):
        raise EngineError("model_spec.json workbook.sheets must be a non-empty unique list")
    if {"SourceData", "Drivers"} - set(sheets):
        raise EngineError("model_spec.json workbook.sheets must include SourceData and Drivers")
    workbook = Workbook()
    workbook.active.title = sheets[0]
    for sheet in sheets[1:]:
        workbook.create_sheet(sheet)
    references = KeyedReferences(workbook)
    _write_actuals(workbook["SourceData"], actual_map, grid, references, spec.get("price"))
    _write_drivers(workbook["Drivers"], driver_rows, active, grid, references)
    module_rows = _module_rows(company_module, actual_map, active, grid)
    company_sheets = set(sheets) - {"SourceData", "Drivers"}
    if set(module_rows) != company_sheets:
        raise EngineError("company module sheets must exactly match model_spec.json workbook.sheets")
    forecast_active = any(value is not None for row in active.values() for value in row.values())
    for sheet in sheets:
        if sheet in company_sheets:
            _write_module_rows(workbook[sheet], module_rows[sheet], grid, references, forecast_active)
    return BuildContext(workbook, grid, references, actual_map, active, module_rows)
