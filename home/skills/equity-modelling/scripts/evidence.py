#!/usr/bin/env python3
"""Generic reader over the pull-financial-data store, driven by a per-company fact_map.json.

No per-ticker knowledge lives here (V2_PLAN.md §5). Every company noun — concept ids, dimension
members, row-label patterns, snapshot ids — comes from `fact_map.json` and `model_spec.json`.
See references/interfaces.md for the schemas and locator grammar this module implements.

Runs under plain `python3` (does not require activating the financial_data_pull venv): it locates
that checkout from `model_spec.json`'s `source_boundary.root` and adds its `src/` and venv
site-packages to `sys.path` at import time, because parquet reads need pyarrow, which only that
venv has installed.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# financial_data_pull import shim
# ---------------------------------------------------------------------------

def _pull_checkout_root(store_root: Path) -> Path:
    """`store_root` is .../financial_data_pull/data — the checkout is its parent."""
    return store_root.parent


def _ensure_pull_importable(store_root: Path) -> None:
    checkout = _pull_checkout_root(store_root)
    src = checkout / "src"
    venv_site = next((checkout / ".venv" / "lib").glob("python3.*/site-packages"), None)
    for p in (str(src), str(venv_site) if venv_site else None):
        if p and p not in sys.path:
            sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FactMapping:
    metric: str
    dimension: Optional[str]
    basis: str
    units: str
    locator: str
    period_kind: str
    transform: str
    missing_treatment: str
    scale: int = 0  # power-of-ten exponent applied when transform == "unit_scale"
    periods: Optional[list[str]] = None  # disjoint period predicate (interfaces.md §2); None = all periods
    period_hashes: Optional[dict[str, str]] = None  # reviewed 8-K exception hashes, keyed by period
    missing_reason: Optional[str] = None  # required for an `unavailable` mapping; else a fallback note


@dataclass
class ResolvedFact:
    metric: str
    period: str
    value: Optional[float]
    units: str
    basis: str
    dimension: Optional[str]
    transform: str
    locator: str
    lineage_scheme: str
    lineage_path: str
    lineage_key: str
    provenance_status: str
    notes: str = ""


TRANSFORM_REGISTRY = {
    "direct", "unit_scale", "sign_flip", "ytd_deaccumulate", "q4_from_fy_minus_9m",
    "sum_quarters", "period_end_stock", "recompute_ratio", "recompute_per_share",
    "segment_axis_filter",
}

# A mapping with this locator is an explicit, intentional gap: it never reads the store, so it can
# never invent a value. It must carry a non-empty `missing_reason` (enforced in load_fact_map).
UNAVAILABLE_LOCATOR = "unavailable"


# ---------------------------------------------------------------------------
# Fact map loading
# ---------------------------------------------------------------------------

def load_fact_map(path: Path) -> list[FactMapping]:
    raw = json.loads(path.read_text())
    out = []
    covered: dict[str, Optional[set[str]]] = {}
    for f in raw["facts"]:
        metric = f["metric"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", metric):
            raise ValueError(f"invalid metric identifier {metric!r}")
        periods = f.get("periods")
        prior = covered.get(metric, set())
        if periods is None:
            if metric in covered:
                raise ValueError(f"{metric}: unrestricted mapping overlaps another mapping")
            covered[metric] = None
        else:
            period_set = set(periods)
            if prior is None or set(prior).intersection(period_set):
                raise ValueError(f"{metric}: mapping periods overlap another mapping")
            covered[metric] = set(prior).union(period_set)
        if f["transform"] not in TRANSFORM_REGISTRY:
            raise ValueError(f"{f['metric']}: transform {f['transform']!r} is not in the closed registry")
        missing_reason = f.get("missing_reason")
        if missing_reason is not None and not isinstance(missing_reason, str):
            raise ValueError(f"{f['metric']}: missing_reason must be a string")
        if f["locator"] == UNAVAILABLE_LOCATOR and not (missing_reason or "").strip():
            raise ValueError(
                f"{f['metric']}: an intentionally unavailable mapping requires a non-empty missing_reason"
            )
        out.append(FactMapping(
            metric=f["metric"], dimension=f.get("dimension"), basis=f["basis"],
            units=f["units"], locator=f["locator"], period_kind=f.get("period_kind", "fiscal_quarter"),
            transform=f["transform"], missing_treatment=f.get("missing_treatment", "unavailable"),
            scale=f.get("scale", 0), periods=periods, period_hashes=f.get("period_hashes"),
            missing_reason=missing_reason,
        ))
    return out


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

_QUARTER_END = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}
_PERIOD_KEY = re.compile(r"\d{4}Q[1-4]")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def period_end_dates(spec: dict) -> dict[str, str]:
    """Validated `model_spec.periods.period_end_dates`, or `{}` when the spec lacks it.

    A spec that declares this mapping opts into an explicit fiscal calendar: keys are canonical
    `YYYYQn` period ids and values are their ISO period-end dates (e.g. a non-calendar 52/53-week
    issuer with `{"2026Q3": "2026-08-02"}`). Specs without the key keep the calendar-year
    fallback in `period_end_date`. A malformed mapping raises rather than guessing a date.
    """
    raw = (spec.get("periods") or {}).get("period_end_dates")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("model_spec.periods.period_end_dates must be an object of period -> ISO date")
    mapping: dict[str, str] = {}
    for period, value in raw.items():
        if not (isinstance(period, str) and _PERIOD_KEY.fullmatch(period)):
            raise ValueError(f"period_end_dates key {period!r} is not a canonical period (YYYYQn)")
        if not (isinstance(value, str) and _ISO_DATE.fullmatch(value)):
            raise ValueError(f"period_end_dates[{period!r}] must be an ISO date (YYYY-MM-DD), got {value!r}")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"period_end_dates[{period!r}] is not a real date: {value!r}") from exc
        mapping[period] = value
    return mapping


def period_end_date(period: str, explicit: Optional[dict[str, str]] = None) -> str:
    """Period-end ISO date for `period`, e.g. '2026Q2' -> '2026-06-30'.

    Uses the spec's explicit `period_end_dates` when supplied. When such a mapping is present it is
    authoritative: a period absent from it is an error rather than a silent calendar guess. Without
    a mapping this falls back to the calendar-quarter end (Mar/Jun/Sep/Dec).
    """
    if explicit:
        try:
            return explicit[period]
        except KeyError:
            raise ValueError(
                f"{period}: model_spec.periods.period_end_dates is authoritative but omits this period"
            ) from None
    year, quarter = period[:4], period[4:]
    if quarter not in _QUARTER_END:
        raise ValueError(f"unrecognized canonical period {period!r}")
    return f"{year}-{_QUARTER_END[quarter]}"


def fiscal_year(period: str) -> str:
    return period[:4]


# ---------------------------------------------------------------------------
# sec_snapshot resolution
# ---------------------------------------------------------------------------

def _read_table(issuer: str, table: str, run_id: str):
    from financial_data_pull import read_table
    return read_table(issuer, table, run_id=run_id)


def _find_period_column(df, period: str, want_ytd: bool = False,
                       explicit: Optional[dict[str, str]] = None) -> Optional[str]:
    end_date = period_end_date(period, explicit)
    suffix = "(YTD)" if want_ytd else None
    for col in df.columns:
        if col.startswith(end_date + " ("):
            if suffix and suffix not in col:
                continue
            if not suffix and "YTD" in col:
                continue
            return col
        # Balance-sheet tables (stock, point-in-time) label columns as the bare
        # ISO date with no "(Q1)"/"(YTD)" suffix at all (e.g. "2026-06-30"),
        # unlike income/cashflow tables (flow, period-of-time). A bare-date
        # column is never a YTD column, so it only matches non-YTD lookups.
        if not suffix and col == end_date:
            return col
    return None


def _select_concept_row(df, concept: str, dimension_member: Optional[str]):
    rows = df[df["concept"] == concept]
    if dimension_member is None:
        rows = rows[rows["dimension_member"].isna()]
    else:
        rows = rows[rows["dimension_member"] == dimension_member]
        # segment_axis_filter: keep only the pure single-axis total, never a
        # cross-axis breakdown (e.g. segment x product/service, or segment x timing).
        rows = rows[rows["dimension_label"].fillna("").str.count("Axis:") == 1]
    if len(rows) == 0:
        return None
    return rows.iloc[0]


def _resolve_sec_snapshot(mapping: FactMapping, period: str, spec: dict, issuer: str,
                          explicit: Optional[dict[str, str]] = None):
    m = re.match(r"sec_snapshot:(\w+)#concept=([^&]+)(?:&dimension_member=([^&]+))?", mapping.locator)
    if not m:
        raise ValueError(f"bad sec_snapshot locator: {mapping.locator}")
    statement, concept, dim = m.group(1), m.group(2), m.group(3)
    run_id = spec["source_boundary"]["latest_sec_snapshot"]

    if mapping.transform == "q4_from_fy_minus_9m" and period.endswith("Q4"):
        fy_label = period_end_date(fiscal_year(period) + "Q4", explicit) + " (FY)"
        fy_table, fy_col, fy_val = _find_in_quarterly_or_annual(issuer, f"{statement}_annual", run_id, fy_label, concept, dim)
        q3_period = fiscal_year(period) + "Q3"
        ytd_table, ytd_col, ytd_val = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, q3_period, concept, dim, want_ytd=True, explicit=explicit)
        if fy_val is None or ytd_val is None:
            return None, None, None
        return fy_val - ytd_val, (fy_table, ytd_table), (fy_col, ytd_col)
    if mapping.transform in ("sum_quarters", "recompute_ratio", "recompute_per_share", "period_end_stock"):
        # These act on already-frozen quarterly actuals, not a single store read;
        # evidence.py resolves the direct quarterly facts, engine.py (Stage 3) applies the annual roll-up as an Excel formula.
        return None, None, None

    table, col, value = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, period, concept, dim, explicit=explicit)
    if value is None:
        table, col, value = _find_in_annual(issuer, f"{statement}_annual", run_id, period, concept, dim, explicit=explicit)
    return value, table, col


def _find_in_quarterly(issuer, table_prefix, run_id, period, concept, dim, want_ytd: bool = False,
                       explicit: Optional[dict[str, str]] = None):
    for n in range(8):
        try:
            df = _read_table(issuer, f"{table_prefix}_{n}", run_id)
        except Exception:
            continue
        col = _find_period_column(df, period, want_ytd=want_ytd, explicit=explicit)
        if col is None:
            continue
        row = _select_concept_row(df, concept, dim)
        if row is None:
            continue
        val = row[col]
        if val == val:  # not NaN
            return f"{table_prefix}_{n}", col, float(val)
    return None, None, None


def _find_in_quarterly_or_annual(issuer, table_prefix, run_id, col_label, concept, dim):
    for n in range(3):
        try:
            df = _read_table(issuer, f"{table_prefix}_{n}", run_id)
        except Exception:
            continue
        if col_label not in df.columns:
            continue
        row = _select_concept_row(df, concept, dim)
        if row is None:
            continue
        val = row[col_label]
        if val == val:
            return f"{table_prefix}_{n}", col_label, float(val)
    return None, None, None


def _find_in_annual(issuer, table_prefix, run_id, period, concept, dim,
                    explicit: Optional[dict[str, str]] = None):
    end_date = period_end_date(fiscal_year(period) + "Q4", explicit)
    col_label = f"{end_date} (FY)"
    return _find_in_quarterly_or_annual(issuer, table_prefix, run_id, col_label, concept, dim)


# ---------------------------------------------------------------------------
# sec_label resolution — a number embedded in a standard XBRL label.  This is
# deliberately narrower than free-text regex extraction: the only supported
# mode maps the comma-separated issued-and-outstanding share counts to their
# same-order dates under the label's explicit "respectively" construction.
# ---------------------------------------------------------------------------

_MONTHS = {name: index for index, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), start=1)}


def _issued_and_outstanding_shares(label: str, period: str,
                                   explicit: Optional[dict[str, str]] = None) -> Optional[float]:
    match = re.search(r"shares\s+authorized,\s*(?P<counts>.+?)\s+shares\s+issued\s+and\s+outstanding\s+at\s*(?P<dates>.+?),\s*respectively", label, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    counts = [int(token.replace(",", "").replace("\u00a0", ""))
              for token in re.findall(r"\d[\d,\u00a0]*", match["counts"])]
    dates = []
    for month, day, year in re.findall(r"(" + "|".join(_MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})", match["dates"], re.IGNORECASE):
        dates.append(f"{year}-{_MONTHS[month.title()]:02d}-{int(day):02d}")
    if not counts or len(counts) != len(dates):
        return None
    target = period_end_date(period, explicit)
    for count, end_date in zip(counts, dates):
        if end_date == target:
            return float(count)
    return None


def _resolve_sec_label(mapping: FactMapping, period: str, spec: dict, issuer: str,
                       explicit: Optional[dict[str, str]] = None):
    parsed = re.fullmatch(r"sec_label:(\w+)#concept=([^&]+)&mode=issued_and_outstanding_shares", mapping.locator)
    if not parsed:
        raise ValueError(f"bad sec_label locator: {mapping.locator}")
    statement, concept = parsed.groups()
    run_id = spec["source_boundary"]["latest_sec_snapshot"]
    for n in range(8):
        table = f"{statement}_quarterly_{n}"
        try:
            df = _read_table(issuer, table, run_id)
        except Exception:
            continue
        row = _select_concept_row(df, concept, None)
        if row is None:
            continue
        value = _issued_and_outstanding_shares(str(row["label"]), period, explicit)
        if value is not None:
            return value, table
    return None, None


# ---------------------------------------------------------------------------
# 8k_exhibit resolution — semantic match on row_label + column_label, never
# on a period-specific table/row/col hardcode (those vary release to release).
# ---------------------------------------------------------------------------

_cells_cache: dict[str, list[dict]] = {}


def _load_8k_cells(store_root: Path, issuer: str) -> list[dict]:
    key = str(store_root) + issuer
    if key not in _cells_cache:
        path = store_root / "derived" / issuer / "8k_cells.csv"
        with path.open(newline="") as f:
            _cells_cache[key] = list(csv.DictReader(f))
    return _cells_cache[key]


def _normal_text(value: str) -> str:
    return " ".join(value.replace("\u00a0", " ").split()).replace(" %", "%").casefold()


def _role_locator_parts(locator: str) -> dict[str, str]:
    if not locator.startswith("8k_exhibit_role:"):
        raise ValueError(f"bad 8k_exhibit_role locator: {locator}")
    parts: dict[str, str] = {}
    for item in locator.removeprefix("8k_exhibit_role:").split("|"):
        key, separator, value = item.partition("=")
        if not separator or key in parts:
            raise ValueError(f"bad 8k_exhibit_role locator: {locator}")
        parts[key] = value
    required = {"caption", "row_labels", "column_role", "period_scope", "exhibit_sha256"}
    if set(parts) != required:
        raise ValueError(f"8k_exhibit_role fields must be exactly {sorted(required)}")
    return parts


def _materialize_role_locator(mapping: FactMapping, period: str) -> FactMapping:
    if "{period_hash}" not in mapping.locator:
        return mapping
    expected = (mapping.period_hashes or {}).get(period)
    if not expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"{mapping.metric} {period}: missing immutable reviewed exhibit hash")
    return replace(mapping, locator=mapping.locator.replace("{period_hash}", expected))


def _resolve_8k_exhibit_role(mapping: FactMapping, period: str, spec: dict, store_root: Path, issuer: str,
                             explicit: Optional[dict[str, str]] = None):
    """Resolve the reviewed duplicate-label exception by table identity and column role."""
    parts = _role_locator_parts(mapping.locator)
    accession = spec["release_accessions"].get(period)
    if accession is None:
        return None, None, None
    cells = _load_8k_cells(store_root, issuer)
    selected = [row for row in cells if row["accession"] == accession
                and _normal_text(row["caption"]) == _normal_text(parts["caption"])]
    if not selected or {row["exhibit_sha256"] for row in selected} != {parts["exhibit_sha256"]}:
        return None, None, None
    labels = {_normal_text(label) for label in parts["row_labels"].split(",")}
    year, month, day = (int(value) for value in period_end_date(period, explicit).split("-"))
    scope = _normal_text(parts["period_scope"].format(
        month=date(year, month, day).strftime("%B"), day=day, year=year))
    role = _normal_text(parts["column_role"])
    # A semantic column role may be represented either as a header (the normal
    # exhibit layout) or as a data-like cell in the flattened cell dump. Its
    # period header is on an earlier header row; same-row headers are sibling
    # column roles, not period scopes. This avoids treating (for example) the
    # "Net income" header left of "Diluted EPS" as that column's period.
    role_cells = [row for row in selected if _normal_text(row["raw_text"]) == role]
    columns = set()
    for role_cell in role_cells:
        role_column = int(role_cell["col_index"])
        role_row = int(role_cell["row_index"])
        headers = [row for row in selected if row["row_kind"] == "header"
                   and int(row["row_index"]) < role_row
                   and int(row["col_index"]) <= role_column
                   and _normal_text(row["raw_text"])]
        if headers:
            nearest_level = max(int(row["row_index"]) for row in headers)
            period_header = max((row for row in headers if int(row["row_index"]) == nearest_level),
                                key=lambda row: int(row["col_index"]))
            if _normal_text(period_header["raw_text"]).startswith(scope):
                # Columns are only meaningful within their own table. Keep the
                # table identity so similarly shaped current/prior-year tables
                # cannot turn one semantic match into duplicate candidates.
                columns.add((role_cell["table_index"], role_column))
    candidates = [row for row in selected if row["row_kind"] == "data"
                  and (row["table_index"], int(row["col_index"])) in columns
                  and _normal_text(row["row_label"]) in labels
                  and row["value"] not in ("", None)]
    if len(candidates) != 1:
        return None, None, None
    row = candidates[0]
    return float(row["value"]), row["exhibit_sha256"], (row["accession"], row["table_index"], row["row_index"], row["col_index"])


def _resolve_8k_exhibit(mapping: FactMapping, period: str, spec: dict, store_root: Path, issuer: str,
                        explicit: Optional[dict[str, str]] = None):
    m = re.match(r"8k_exhibit:row_label=([^|]+)\|col_pattern=(.+)", mapping.locator)
    if not m:
        raise ValueError(f"bad 8k_exhibit locator: {mapping.locator}")
    row_label_pat, col_pat = m.group(1), m.group(2)
    accession = spec["release_accessions"].get(period)
    if accession is None:
        return None, None, None
    end_date = period_end_date(period, explicit)
    y, mth, d = (int(x) for x in end_date.split("-"))
    month_name = date(y, mth, d).strftime("%B")
    col_regex = col_pat.format(month=month_name, day=d, year=y)
    cells = _load_8k_cells(store_root, issuer)
    for row in cells:
        if row["accession"] != accession or row["row_kind"] != "data":
            continue
        if not re.search(row_label_pat, row["row_label"], re.IGNORECASE):
            continue
        if not re.search(col_regex, row["column_label"]):
            continue
        if row["value"] not in ("", None):
            return float(row["value"]), row["exhibit_sha256"], (row["accession"], row["table_index"], row["row_index"], row["col_index"])
    return None, None, None


# ---------------------------------------------------------------------------
# raw_payload resolution (dated price)
# ---------------------------------------------------------------------------

def _resolve_raw_payload(mapping: FactMapping, period: str, spec: dict, store_root: Path):
    m = re.fullmatch(r"raw_payload:([^/]+)/([^/]+)/([^#]+)#index=([^&]+)&field=([^&]+)", mapping.locator)
    if not m:
        raise ValueError(f"bad raw_payload locator: {mapping.locator}")
    provider, sha256, filename, index_template, field = m.groups()
    path = store_root / "raw" / spec["ticker"] / provider / sha256 / filename
    payload = json.loads(path.read_text())
    columns, index, data = payload["columns"], payload["index"], payload["data"]
    col_i = columns.index(field)
    target = index_template.format(date=period)
    for i, idx in enumerate(index):
        if idx == target or ("{date}" in index_template and idx.startswith(period)):
            return float(data[i][col_i]), str(path)
    return None, str(path)


# ---------------------------------------------------------------------------
# Top-level resolve / build
# ---------------------------------------------------------------------------

def resolve(mapping: FactMapping, period: str, spec: dict) -> ResolvedFact:
    store_root = Path(spec["source_boundary"]["root"])
    issuer = spec["ticker"]
    _ensure_pull_importable(store_root)
    run_id = spec["source_boundary"]["latest_sec_snapshot"]
    explicit = period_end_dates(spec)

    if mapping.locator == UNAVAILABLE_LOCATOR:
        # Intentional gap: declare unavailability rather than guess. Never reads the store.
        return ResolvedFact(mapping.metric, period, None, mapping.units, mapping.basis,
                            mapping.dimension, mapping.transform, mapping.locator,
                            "unavailable", "", "", "unavailable",
                            notes=mapping.missing_reason or "")

    if mapping.locator.startswith("sec_snapshot:"):
        value, table, col = _resolve_sec_snapshot(mapping, period, spec, issuer, explicit)
        if value is not None and mapping.scale:
            value = value * (10 ** mapping.scale)
        if isinstance(table, tuple):
            lineage_path = ";".join(f"data/tables/{issuer}/{run_id}/{name}.parquet" for name in table)
            lineage_key = ";".join(f"col={name}" for name in col)
        else:
            lineage_path = f"data/tables/{issuer}/{run_id}/{table}.parquet" if table else ""
            lineage_key = f"col={col}" if col else ""
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, mapping.locator,
                             "sec_snapshot", lineage_path, lineage_key, status)

    if mapping.locator.startswith("sec_label:"):
        value, table = _resolve_sec_label(mapping, period, spec, issuer, explicit)
        if value is not None and mapping.scale:
            value = value * (10 ** mapping.scale)
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                            mapping.dimension, mapping.transform, mapping.locator,
                            "sec_snapshot", f"data/tables/{issuer}/{run_id}/{table}.parquet" if table else "",
                            f"table={table};label=issued_and_outstanding_shares" if table else "", status)

    if mapping.locator.startswith("8k_exhibit_role:"):
        effective = _materialize_role_locator(mapping, period)
        value, exhibit_sha256, keys = _resolve_8k_exhibit_role(effective, period, spec, store_root, issuer, explicit)
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, effective.locator,
                             "8k_exhibit", f"data/raw/{issuer}/sec/{exhibit_sha256}/payload" if exhibit_sha256 else "",
                             f"keys={keys}" if keys else "", status)

    if mapping.locator.startswith("8k_exhibit:"):
        value, exhibit_sha256, keys = _resolve_8k_exhibit(mapping, period, spec, store_root, issuer, explicit)
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, mapping.locator,
                             "8k_exhibit", f"data/raw/{issuer}/sec/{exhibit_sha256}/payload",
                             f"keys={keys}", status)

    if mapping.locator.startswith("raw_payload:"):
        value, path = _resolve_raw_payload(mapping, period, spec, store_root)
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, mapping.locator,
                             "raw_payload", path or "", "", status)

    if mapping.locator.startswith("derived:"):
        raise ValueError("derived facts are resolved by build_actuals, not resolve()")

    raise ValueError(f"unknown locator scheme: {mapping.locator}")


def build_actuals(fact_map: list[FactMapping], spec: dict, periods: list[str]) -> list[ResolvedFact]:
    explicit = period_end_dates(spec)
    if explicit:
        uncovered = [p for p in periods if p not in explicit]
        if uncovered:
            raise ValueError(
                "model_spec.periods.period_end_dates is authoritative but omits requested period(s): "
                + ", ".join(uncovered)
            )
    direct = [m for m in fact_map if not m.locator.startswith("derived:")]
    derived = [m for m in fact_map if m.locator.startswith("derived:")]

    by_key: dict[tuple[str, str], ResolvedFact] = {}
    for m in direct:
        for p in periods:
            if m.periods is not None and p not in m.periods:
                # Disjoint period predicate (interfaces.md §2): this entry does not
                # cover this period — another fact_map entry for the same metric does.
                continue
            try:
                r = resolve(m, p, spec)
            except Exception as e:
                raise ValueError(f"{m.metric} {p}: evidence resolution failed") from e
            # A declared reason is the frozen row's visible, specific missing reason for any
            # non-error unavailable/unresolved result of this mapping (interfaces.md §2/§5).
            if r.value is None and r.provenance_status != "error" and not r.notes \
                    and (m.missing_reason or "").strip():
                r = replace(r, notes=m.missing_reason)
            by_key[(m.metric, p)] = r

    for m in derived:
        expr = m.locator[len("derived:"):]
        for p in periods:
            ops = re.findall(r"[a-z_][a-z0-9_]*", expr)
            values = {}
            missing = [op for op in ops if (op, p) not in by_key or by_key[(op, p)].value is None]
            if missing:
                by_key[(m.metric, p)] = ResolvedFact(m.metric, p, None, m.units, m.basis, m.dimension,
                                          m.transform, m.locator, "derived", "", "", "unresolved",
                                          notes=f"missing operand(s): {missing}")
                continue
            for op in ops:
                values[op] = by_key[(op, p)].value
            value = eval(expr, {"__builtins__": {}}, values)  # noqa: S307 — expr is our own closed-form arithmetic, not user input
            r = ResolvedFact(m.metric, p, value, m.units, m.basis, m.dimension, m.transform,
                              m.locator, "derived", "n/a — combines already-lineaged metrics",
                              f"operands={sorted(values)}", "verified")
            by_key[(m.metric, p)] = r

    required_missing = [
        f"{m.metric} {p}: {by_key.get((m.metric, p)).notes if (m.metric, p) in by_key else 'not resolved'}"
        for m in fact_map if m.missing_treatment == "required"
        for p in periods if m.periods is None or p in m.periods
        if (m.metric, p) not in by_key or by_key[(m.metric, p)].value is None
    ]
    if required_missing:
        raise ValueError("required fact unresolved: " + "; ".join(required_missing))
    return list(by_key.values())


def build_availability(actuals: list[ResolvedFact], metrics: list[str], periods: list[str]) -> str:
    lines = ["| metric | " + " | ".join(periods) + " |", "|---|" + "---|" * len(periods)]
    by_key = {(r.metric, r.period): r for r in actuals}
    for m in metrics:
        cells = []
        for p in periods:
            r = by_key.get((m, p))
            cells.append("✓" if r and r.value is not None else "unavailable")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def freeze(actuals: list[ResolvedFact], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "actuals.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "period", "value", "units", "basis", "dimension", "transform",
                    "locator", "lineage_scheme", "lineage_path", "lineage_key",
                    "provenance_status", "notes"])
        for r in actuals:
            w.writerow([r.metric, r.period, r.value, r.units, r.basis, r.dimension or "",
                        r.transform, r.locator, r.lineage_scheme, r.lineage_path,
                        r.lineage_key, r.provenance_status, r.notes])


if __name__ == "__main__":
    print(__doc__)
