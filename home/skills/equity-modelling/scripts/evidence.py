#!/usr/bin/env python3
"""Generic reader over the pull-financial-data store, driven by a per-company fact_map.json.

No per-ticker knowledge lives here (docs/archive/V2_PLAN.md §5). Every company noun — concept ids, dimension
members, row-label patterns, snapshot ids — comes from `fact_map.json` and `model_spec.json`.
See references/interfaces.md for the schemas and locator grammar this module implements.

Runs under plain `python3` (does not require activating the financial_data_pull venv): it locates
that checkout from `model_spec.json`'s `source_boundary.root` and adds its `src/` and venv
site-packages to `sys.path` at import time, because parquet reads need pyarrow, which only that
venv has installed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_boundary(spec: dict) -> dict:
    boundary = spec.get("source_boundary")
    required = {"mode", "root", "snapshots", "tables", "originals"}
    if not isinstance(boundary, dict) or not required.issubset(boundary):
        raise ValueError("model_spec.source_boundary must pin pull-data-only snapshots, tables and originals")
    if boundary.get("mode") != "pull-data-only":
        raise ValueError("model_spec.source_boundary.mode must be pull-data-only")
    if not isinstance(boundary.get("root"), str) or not boundary["root"]:
        raise ValueError("model_spec.source_boundary.root is required")
    for key in ("snapshots", "tables", "originals"):
        if not isinstance(boundary.get(key), list):
            raise ValueError(f"model_spec.source_boundary.{key} must be a list")
    return boundary


def _verify_boundary(spec: dict) -> tuple[Path, dict[tuple[str, str], dict], dict[tuple[str, str, str], dict]]:
    """Verify the minimal immutable pull boundary and return its selected source indexes."""
    def safe_name(value: object) -> bool:
        return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_.:+-]+", value)) and value not in {".", ".."}
    boundary = _source_boundary(spec)
    root = Path(boundary["root"]).resolve()
    snapshots: dict[tuple[str, str], dict] = {}
    for item in boundary["snapshots"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("ticker", "run_id", "sha256")):
            raise ValueError("source_boundary snapshot entries require ticker, run_id and sha256")
        if not safe_name(item["ticker"]) or not safe_name(item["run_id"]):
            raise ValueError("source_boundary snapshot contains an unsafe ticker or run_id")
        key = (item["ticker"], item["run_id"])
        if key in snapshots:
            raise ValueError(f"duplicate pinned snapshot {key}")
        path = root / "tables" / item["ticker"] / item["run_id"] / "snapshot.json"
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise ValueError(f"pinned snapshot hash mismatch or missing: {item['ticker']} {item['run_id']}")
        snapshots[key] = item
    tables: dict[tuple[str, str], dict] = {}
    for item in boundary["tables"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("ticker", "run_id", "name", "sha256")):
            raise ValueError("source_boundary table entries require ticker, run_id, name and sha256")
        if not all(safe_name(item[k]) for k in ("ticker", "run_id", "name")):
            raise ValueError("source_boundary table contains an unsafe path component")
        key = (item["run_id"], item["name"])
        if key in tables:
            raise ValueError(f"duplicate pinned table {key}")
        if (item["ticker"], item["run_id"]) not in snapshots:
            raise ValueError(f"table pin has no pinned snapshot: {item['ticker']} {item['run_id']}")
        snap_path = root / "tables" / item["ticker"] / item["run_id"] / "snapshot.json"
        manifest = json.loads(snap_path.read_text())
        path = snap_path.parent / f"{item['name']}.parquet"
        manifest_hash = (manifest.get("table_hashes") or {}).get(item["name"])
        if manifest_hash != item["sha256"] or not path.is_file() or _sha256(path) != item["sha256"]:
            raise ValueError(f"pinned table hash mismatch or missing: {item['ticker']} {item['run_id']} {item['name']}")
        tables[key] = item
    originals: dict[tuple[str, str, str], dict] = {}
    for item in boundary["originals"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("ticker", "provider", "run_id", "sha256", "filename")):
            raise ValueError("source_boundary original entries require ticker, provider, run_id, sha256 and filename")
        if (item["ticker"], item["run_id"]) not in snapshots:
            raise ValueError(f"original pin has no pinned snapshot: {item['ticker']} {item['run_id']}")
        if (not safe_name(item["ticker"]) or not safe_name(item["provider"])
                or not safe_name(item["run_id"]) or not safe_name(item["filename"])
                or not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"]))):
            raise ValueError("source_boundary original contains an unsafe path component or hash")
        key = (item["ticker"], item["provider"], item["sha256"])
        if key in originals:
            raise ValueError(f"duplicate pinned original {key}")
        path = root / "raw" / item["ticker"] / item["provider"] / item["sha256"] / item["filename"]
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise ValueError(f"pinned original hash mismatch or missing: {item['ticker']} {item['sha256']}")
        snap_path = root / "tables" / item["ticker"] / item["run_id"] / "snapshot.json"
        originals_in_snapshot = json.loads(snap_path.read_text()).get("originals") or {}
        if str(path.resolve()) not in {str(Path(value).resolve()) for value in originals_in_snapshot.values()}:
            raise ValueError(f"pinned original is not recorded by its snapshot: {item['ticker']} {item['sha256']}")
        originals[key] = item
    return root, tables, originals


# ---------------------------------------------------------------------------
# sec_snapshot resolution
# ---------------------------------------------------------------------------

def _read_table(issuer: str, table: str, run_id: str, store_root: Optional[Path] = None):
    if store_root is None:
        from financial_data_pull import read_table
        return read_table(issuer, table, run_id=run_id)
    snapshot = store_root / "tables" / issuer / run_id
    manifest = json.loads((snapshot / "snapshot.json").read_text())
    path = snapshot / f"{table}.parquet"
    expected = (manifest.get("table_hashes") or {}).get(table)
    if expected is None:
        raise KeyError(table)
    if not path.is_file() or _sha256(path) != expected:
        raise ValueError(f"snapshot table hash mismatch or missing: {issuer} {run_id} {table}")
    import pandas as pd
    return pd.read_parquet(path)


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
    if len(rows) > 1:
        raise ValueError(
            f"ambiguous SEC concept {concept!r} dimension={dimension_member!r}: "
            f"{len(rows)} eligible rows at indices {list(rows.index)}"
        )
    if len(rows) == 0:
        return None
    return rows.iloc[0]


def _resolve_sec_snapshot(mapping: FactMapping, period: str, spec: dict, issuer: str,
                          explicit: Optional[dict[str, str]] = None, store_root: Optional[Path] = None):
    m = re.match(r"sec_snapshot:(\w+)#concept=([^&]+)(?:&dimension_member=([^&]+))?", mapping.locator)
    if not m:
        raise ValueError(f"bad sec_snapshot locator: {mapping.locator}")
    statement, concept, dim = m.group(1), m.group(2), m.group(3)
    run_id = (spec["source_boundary"].get("selected_sec_snapshot")
              or spec["source_boundary"].get("latest_sec_snapshot"))
    if not run_id:
        issuer_runs = [item["run_id"] for item in spec["source_boundary"]["snapshots"]
                       if item.get("ticker") == issuer]
        if len(set(issuer_runs)) != 1:
            raise ValueError(f"{mapping.metric} {period}: source boundary needs selected_sec_snapshot")
        run_id = issuer_runs[0]

    if mapping.transform == "q4_from_fy_minus_9m":
        fy_label = period_end_date(fiscal_year(period) + "Q4", explicit) + " (FY)"
        fy_table, fy_col, fy_val = _find_in_quarterly_or_annual(issuer, f"{statement}_annual", run_id, fy_label, concept, dim, store_root)
        q3_period = fiscal_year(period) + "Q3"
        ytd_table, ytd_col, ytd_val = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, q3_period, concept, dim, want_ytd=True, explicit=explicit, store_root=store_root)
        if fy_val is None or ytd_val is None:
            return None, None, None
        return fy_val - ytd_val, (fy_table, ytd_table), (fy_col, ytd_col)
    if mapping.transform == "ytd_deaccumulate":
        quarter = int(period[-1])
        current = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, period, concept, dim,
                                     want_ytd=True, explicit=explicit, store_root=store_root)
        if current[2] is None and quarter == 1:
            current = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, period, concept, dim,
                                         explicit=explicit, store_root=store_root)
        if current[2] is None:
            return None, None, None
        if quarter == 1:
            return current[2], current[0], current[1]
        prior_period = f"{fiscal_year(period)}Q{quarter - 1}"
        prior = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, prior_period, concept, dim,
                                   want_ytd=True, explicit=explicit, store_root=store_root)
        if prior[2] is None:
            return None, None, None
        return current[2] - prior[2], (current[0], prior[0]), (current[1], prior[1])

    table, col, value = _find_in_quarterly(issuer, f"{statement}_quarterly", run_id, period, concept, dim, explicit=explicit, store_root=store_root)
    return value, table, col


def _find_in_quarterly(issuer, table_prefix, run_id, period, concept, dim, want_ytd: bool = False,
                       explicit: Optional[dict[str, str]] = None, store_root: Optional[Path] = None):
    matches = []
    for n in range(8):
        try:
            df = _read_table(issuer, f"{table_prefix}_{n}", run_id, store_root)
        except (FileNotFoundError, KeyError):
            continue
        col = _find_period_column(df, period, want_ytd=want_ytd, explicit=explicit)
        if col is None:
            continue
        row = _select_concept_row(df, concept, dim)
        if row is None:
            continue
        val = row[col]
        if val == val:  # not NaN
            matches.append((f"{table_prefix}_{n}", col, float(val)))
    if len(matches) > 1:
        raise ValueError(f"ambiguous SEC source tables for {concept!r} {period}: "
                         f"{[(name, col) for name, col, _ in matches]}")
    return matches[0] if matches else (None, None, None)


def _find_in_quarterly_or_annual(issuer, table_prefix, run_id, col_label, concept, dim,
                                  store_root: Optional[Path] = None):
    matches = []
    for n in range(8):
        try:
            df = _read_table(issuer, f"{table_prefix}_{n}", run_id, store_root)
        except (FileNotFoundError, KeyError):
            continue
        if col_label not in df.columns:
            continue
        row = _select_concept_row(df, concept, dim)
        if row is None:
            continue
        val = row[col_label]
        if val == val:
            matches.append((f"{table_prefix}_{n}", col_label, float(val)))
    if len(matches) > 1:
        raise ValueError(f"ambiguous SEC source tables for {concept!r} {col_label}: "
                         f"{[(name, col) for name, col, _ in matches]}")
    return matches[0] if matches else (None, None, None)


def _find_in_annual(issuer, table_prefix, run_id, period, concept, dim,
                    explicit: Optional[dict[str, str]] = None, store_root: Optional[Path] = None):
    end_date = period_end_date(fiscal_year(period) + "Q4", explicit)
    col_label = f"{end_date} (FY)"
    return _find_in_quarterly_or_annual(issuer, table_prefix, run_id, col_label, concept, dim, store_root)


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
                       explicit: Optional[dict[str, str]] = None, store_root: Optional[Path] = None):
    parsed = re.fullmatch(r"sec_label:(\w+)#concept=([^&]+)&mode=issued_and_outstanding_shares", mapping.locator)
    if not parsed:
        raise ValueError(f"bad sec_label locator: {mapping.locator}")
    statement, concept = parsed.groups()
    run_id = (spec["source_boundary"].get("selected_sec_snapshot")
              or spec["source_boundary"].get("latest_sec_snapshot"))
    if not run_id:
        issuer_runs = [item["run_id"] for item in spec["source_boundary"]["snapshots"]
                       if item.get("ticker") == issuer]
        if len(set(issuer_runs)) != 1:
            raise ValueError(f"{mapping.metric} {period}: source boundary needs selected_sec_snapshot")
        run_id = issuer_runs[0]
    matches = []
    for n in range(8):
        table = f"{statement}_quarterly_{n}"
        try:
            df = _read_table(issuer, table, run_id, store_root)
        except (FileNotFoundError, KeyError):
            continue
        row = _select_concept_row(df, concept, None)
        if row is None:
            continue
        value = _issued_and_outstanding_shares(str(row["label"]), period, explicit)
        if value is not None:
            matches.append((value, table))
    if len(matches) > 1:
        raise ValueError(f"ambiguous SEC label source for {concept!r} {period}: {matches}")
    return matches[0] if matches else (None, None)


# ---------------------------------------------------------------------------
# 8k_exhibit resolution — semantic match on row_label + column_label, never
# on a period-specific table/row/col hardcode (those vary release to release).
# ---------------------------------------------------------------------------

def _load_8k_original(spec: dict, issuer: str, accession: str, sha256: str) -> tuple[list[dict], str]:
    """Re-extract cells from the pinned immutable exhibit, never the rewritable CSV view."""
    root, _, originals = _verify_boundary(spec)
    item = originals.get((issuer, "sec", sha256))
    if item is None or item.get("accession") != accession:
        raise ValueError(f"8-K original is not pinned for accession {accession}: {issuer} {sha256}")
    path = root / "raw" / issuer / "sec" / sha256 / item["filename"]
    _ensure_pull_importable(root)
    from financial_data_pull.views import _exhibit_rows
    exhibit = {"accession": accession, "filing_date": ""}
    return _exhibit_rows(path.read_bytes(), exhibit, sha256), str(path)


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
    """Resolve the reviewed duplicate-label exception from its immutable exhibit."""
    parts = _role_locator_parts(mapping.locator)
    accession = spec["release_accessions"].get(period)
    if accession is None:
        return None, None, None
    cells, _ = _load_8k_original(spec, issuer, accession, parts["exhibit_sha256"])
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
        headers = [row for row in selected if row["table_index"] == role_cell["table_index"]
                   and row["row_kind"] == "header"
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
    if len(candidates) > 1:
        locations = [(row["table_index"], row["row_index"], row["col_index"]) for row in candidates]
        raise ValueError(f"{mapping.metric} {period}: ambiguous 8-K candidates {locations}")
    if not candidates:
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
    boundary = _source_boundary(spec)
    possible = [item for item in boundary["originals"]
                if item.get("ticker") == issuer and item.get("provider") == "sec"
                and item.get("accession") == accession]
    # The release accession is resolved from the raw original identity retained in the
    # frozen row's locator/lineage; if several originals are eligible, inspect each and
    # require the semantic selector to identify exactly one candidate overall.
    cells = []
    for item in possible:
        rows, _ = _load_8k_original(spec, issuer, accession, item["sha256"])
        cells.extend(rows)
    candidates = []
    for row in cells:
        if row["accession"] != accession or row["row_kind"] != "data":
            continue
        if not re.search(row_label_pat, row["row_label"], re.IGNORECASE):
            continue
        if not re.search(col_regex, row["column_label"]):
            continue
        if row["value"] not in ("", None):
            candidates.append(row)
    if len(candidates) > 1:
        details = [(r["exhibit_sha256"], r["table_index"], r["row_index"], r["col_index"])
                   for r in candidates]
        raise ValueError(f"{mapping.metric} {period}: ambiguous 8-K candidates {details}")
    if not candidates:
        return None, None, None
    row = candidates[0]
    return float(row["value"]), row["exhibit_sha256"], (row["accession"], row["table_index"], row["row_index"], row["col_index"])


# ---------------------------------------------------------------------------
# raw_payload resolution (dated price)
# ---------------------------------------------------------------------------

def _resolve_raw_payload(mapping: FactMapping, period: str, spec: dict, store_root: Path):
    m = re.fullmatch(r"raw_payload:([^/]+)/([^/]+)/([^#]+)#index=([^&]+)&field=([^&]+)", mapping.locator)
    if not m:
        raise ValueError(f"bad raw_payload locator: {mapping.locator}")
    provider, sha256, filename, index_template, field = m.groups()
    _, _, originals = _verify_boundary(spec)
    pinned = originals.get((spec["ticker"], provider, sha256))
    if pinned is None or pinned["filename"] != filename:
        raise ValueError(f"raw payload is not exactly pinned in source_boundary: {provider}/{sha256}/{filename}")
    path = store_root / "raw" / spec["ticker"] / provider / sha256 / filename
    payload = json.loads(path.read_text())
    columns, index, data = payload["columns"], payload["index"], payload["data"]
    col_i = columns.index(field)
    target = index_template.format(date=period)
    matches = [(i, idx) for i, idx in enumerate(index)
               if idx == target or ("{date}" in index_template and idx.startswith(period))]
    if len(matches) > 1:
        raise ValueError(f"ambiguous raw-payload index for {mapping.metric} {period}: "
                         f"{[idx for _, idx in matches]}")
    if not matches:
        return None, str(path), ""
    i, idx = matches[0]
    return float(data[i][col_i]), str(path), f"index={idx};field={field}"


# ---------------------------------------------------------------------------
# Top-level resolve / build
# ---------------------------------------------------------------------------

def _validate_mapping_transform(mapping: FactMapping, period: str) -> None:
    if mapping.transform in {"sum_quarters", "period_end_stock", "recompute_ratio", "recompute_per_share"}:
        raise ValueError(f"transform {mapping.transform} is not applied to populated quarterly facts")
    if mapping.transform == "q4_from_fy_minus_9m" and not period.endswith("Q4"):
        raise ValueError(f"q4_from_fy_minus_9m is only valid for Q4 periods, not {period}")
    if mapping.transform == "ytd_deaccumulate" and (not period.endswith(("Q1", "Q2", "Q3"))
                                                        or not mapping.locator.startswith("sec_snapshot:")):
        raise ValueError("ytd_deaccumulate requires a SEC snapshot mapping for Q1-Q3")
    if mapping.transform == "q4_from_fy_minus_9m" and not mapping.locator.startswith("sec_snapshot:"):
        raise ValueError("q4_from_fy_minus_9m requires a SEC snapshot mapping")
    if mapping.transform == "segment_axis_filter":
        if not mapping.locator.startswith("sec_snapshot:") or "&dimension_member=" not in mapping.locator:
            raise ValueError("segment_axis_filter requires a SEC snapshot dimension_member selector")
    if mapping.scale and mapping.transform != "unit_scale":
        raise ValueError("mapping.scale is only applied by unit_scale")


def _apply_arithmetic_transform(mapping: FactMapping, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if mapping.transform == "unit_scale":
        return value * (10 ** mapping.scale)
    if mapping.transform == "sign_flip":
        return -value
    return value


def resolve(mapping: FactMapping, period: str, spec: dict) -> ResolvedFact:
    _validate_mapping_transform(mapping, period)
    boundary = _source_boundary(spec)
    store_root = Path(boundary["root"])
    issuer = spec["ticker"]
    _ensure_pull_importable(store_root)
    run_id = boundary.get("selected_sec_snapshot") or boundary.get("latest_sec_snapshot")
    if not run_id:
        sec_runs = [item["run_id"] for item in boundary["snapshots"] if item.get("ticker") == issuer]
        if len(set(sec_runs)) != 1:
            raise ValueError(f"{mapping.metric} {period}: source boundary needs selected_sec_snapshot")
        run_id = sec_runs[0]
    explicit = period_end_dates(spec)

    if mapping.locator == UNAVAILABLE_LOCATOR:
        # Intentional gap: declare unavailability rather than guess. Never reads the store.
        return ResolvedFact(mapping.metric, period, None, mapping.units, mapping.basis,
                            mapping.dimension, mapping.transform, mapping.locator,
                            "unavailable", "", "", "unavailable",
                            notes=mapping.missing_reason or "")

    if mapping.locator.startswith("sec_snapshot:"):
        value, table, col = _resolve_sec_snapshot(mapping, period, spec, issuer, explicit, store_root)
        value = _apply_arithmetic_transform(mapping, value)
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
        value, table = _resolve_sec_label(mapping, period, spec, issuer, explicit, store_root)
        value = _apply_arithmetic_transform(mapping, value)
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                            mapping.dimension, mapping.transform, mapping.locator,
                            "sec_snapshot", f"data/tables/{issuer}/{run_id}/{table}.parquet" if table else "",
                            f"table={table};label=issued_and_outstanding_shares" if table else "", status)

    if mapping.locator.startswith("8k_exhibit_role:"):
        effective = _materialize_role_locator(mapping, period)
        value, exhibit_sha256, keys = _resolve_8k_exhibit_role(effective, period, spec, store_root, issuer, explicit)
        value = _apply_arithmetic_transform(mapping, value)
        status = "verified" if value is not None else "unresolved"
        original = next((item for item in boundary["originals"]
                         if item.get("ticker") == issuer and item.get("provider") == "sec"
                         and item.get("sha256") == exhibit_sha256), None)
        lineage_path = (f"data/raw/{issuer}/sec/{exhibit_sha256}/{original['filename']}"
                        if original else "")
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, effective.locator,
                             "8k_exhibit", lineage_path,
                             f"keys={keys}" if keys else "", status)

    if mapping.locator.startswith("8k_exhibit:"):
        value, exhibit_sha256, keys = _resolve_8k_exhibit(mapping, period, spec, store_root, issuer, explicit)
        value = _apply_arithmetic_transform(mapping, value)
        status = "verified" if value is not None else "unresolved"
        original = next((item for item in boundary["originals"]
                         if item.get("ticker") == issuer and item.get("provider") == "sec"
                         and item.get("sha256") == exhibit_sha256), None)
        lineage_path = (f"data/raw/{issuer}/sec/{exhibit_sha256}/{original['filename']}"
                        if original else "")
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, mapping.locator,
                             "8k_exhibit", lineage_path, f"keys={keys}", status)

    if mapping.locator.startswith("raw_payload:"):
        value, path, key = _resolve_raw_payload(mapping, period, spec, store_root)
        value = _apply_arithmetic_transform(mapping, value)
        status = "verified" if value is not None else "unresolved"
        return ResolvedFact(mapping.metric, period, value, mapping.units, mapping.basis,
                             mapping.dimension, mapping.transform, mapping.locator,
                             "raw_payload", path or "", key, status)

    if mapping.locator.startswith("derived:"):
        raise ValueError("derived facts are resolved by build_actuals, not resolve()")

    raise ValueError(f"unknown locator scheme: {mapping.locator}")


def build_actuals(fact_map: list[FactMapping], spec: dict, periods: list[str]) -> list[ResolvedFact]:
    _verify_boundary(spec)
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
                raise ValueError(f"{m.metric} {p}: evidence resolution failed: {e}") from e
            # A declared reason is the frozen row's visible, specific missing reason for any
            # non-error unavailable/unresolved result of this mapping (interfaces.md §2/§5).
            if r.value is None and r.provenance_status != "error" and not r.notes \
                    and (m.missing_reason or "").strip():
                r = replace(r, notes=m.missing_reason)
            by_key[(m.metric, p)] = r

    for m in derived:
        if m.transform != "direct" or m.scale:
            raise ValueError(f"{m.metric}: derived facts support only the direct transform")
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



_VALUE_TOLERANCE = 1e-8


def _same_value(actual: str, expected: Optional[float]) -> bool:
    try:
        observed = float(actual)
    except (TypeError, ValueError):
        return False
    return expected is not None and math.isclose(observed, expected, rel_tol=_VALUE_TOLERANCE, abs_tol=_VALUE_TOLERANCE)


def replay_frozen_evidence(spec: dict, actual_rows: list[dict[str, str]],
                           benchmark_rows: Optional[list[dict[str, str]]] = None,
                           fact_map: Optional[list[FactMapping]] = None) -> dict[str, int]:
    """Replay every populated actual and benchmark against the strictly pinned pull boundary."""
    try:
        root, tables, originals = _verify_boundary(spec)
    except ValueError as exc:
        message = str(exc)
        populated = [row for row in actual_rows + (benchmark_rows or [])
                     if str(row.get("value") or "").strip()]
        source_refs = []
        boundary = spec.get("source_boundary") or {}
        table_pins = boundary.get("tables", []) if isinstance(boundary.get("tables", []), list) else []
        original_pins = boundary.get("originals", []) if isinstance(boundary.get("originals", []), list) else []
        snapshot_pins = boundary.get("snapshots", []) if isinstance(boundary.get("snapshots", []), list) else []
        for row in populated:
            metric, period = row.get("metric", "?"), row.get("period", "?")
            lineage = " ".join(str(row.get(field) or "")
                                for field in ("locator", "lineage_path", "lineage_key"))
            source_hashes = [item.get("sha256", "") for item in table_pins + original_pins
                             if isinstance(item, dict) and item.get("sha256")
                             and item["sha256"] in message]
            related = any(digest in lineage for digest in source_hashes)
            if not related:
                for snapshot in snapshot_pins:
                    if not isinstance(snapshot, dict) or snapshot.get("run_id") not in message:
                        continue
                    related_hashes = [item.get("sha256", "")
                                      for item in table_pins + original_pins
                                      if isinstance(item, dict) and item.get("run_id") == snapshot.get("run_id")]
                    related = any(digest in lineage for digest in related_hashes if digest)
                    related = related or any(
                        item.get("run_id") == snapshot.get("run_id")
                        and item.get("name", "") in lineage
                        and item.get("name", "") in message
                        for item in table_pins if isinstance(item, dict))
                    related = related or snapshot.get("run_id", "") in lineage
            if related:
                source_refs.append(f"{metric} {period}")
        context = ", ".join(dict.fromkeys(source_refs))
        if context:
            raise ValueError(f"{context}: source boundary replay failed: {message}") from exc
        raise ValueError(f"source boundary replay failed: {message}") from exc
    ticker = spec.get("ticker")
    if not ticker:
        raise ValueError("model_spec.ticker is required for evidence replay")
    if fact_map is None:
        raise ValueError("fact_map is required for evidence replay")
    mapping_by_key: dict[tuple[str, str], FactMapping] = {}
    for mapping in fact_map:
        for period in (mapping.periods or []):
            mapping_by_key[(mapping.metric, period)] = mapping
    historical = (spec.get("periods") or {}).get("historical_quarters", [])
    for mapping in fact_map:
        for period in (mapping.periods if mapping.periods is not None else historical):
            mapping_by_key[(mapping.metric, period)] = mapping

    actual_by_key: dict[tuple[str, str], dict[str, str]] = {}
    seen: set[tuple[str, str, str]] = set()
    for line, row in enumerate(actual_rows, start=2):
        metric, period = str(row.get("metric") or ""), str(row.get("period") or "")
        key = (metric, period, str(row.get("dimension") or ""))
        if not metric or not period:
            raise ValueError(f"actuals.csv line {line}: metric and period are required")
        if key in seen:
            raise ValueError(f"{metric} {period}: duplicate frozen actual (dimension={key[2]!r})")
        seen.add(key)
        actual_by_key[(metric, period)] = row
        value = str(row.get("value") or "").strip()
        status = str(row.get("provenance_status") or "").strip().lower()
        if value:
            missing_lineage = [field for field in ("lineage_scheme", "lineage_path", "lineage_key")
                               if not str(row.get(field) or "").strip()]
            if missing_lineage or status != "verified":
                raise ValueError(f"{metric} {period}: populated fact lacks verified lineage metadata")
        elif status in {"", "error"} or not str(row.get("notes") or "").strip():
            raise ValueError(f"{metric} {period}: blank fact needs unavailable status and a specific reason")

    for mapping in fact_map:
        covered_periods = mapping.periods if mapping.periods is not None else historical
        for period in covered_periods:
            if (mapping.metric, period) not in actual_by_key:
                raise ValueError(f"fact_map.json declares {mapping.metric} {period} but actuals.csv has no row")

    replayed = 0
    for row in actual_rows:
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        metric, period = row.get("metric", ""), row.get("period", "")
        mapping = mapping_by_key.get((metric, period))
        if mapping is None:
            raise ValueError(f"{metric} {period}: populated actual has no fact-map mapping")
        expected_locator = (_materialize_role_locator(mapping, period).locator
                            if mapping.locator.startswith("8k_exhibit_role:") else mapping.locator)
        expected_metadata = {
            "units": mapping.units, "basis": mapping.basis,
            "dimension": mapping.dimension or "", "transform": mapping.transform,
            "locator": expected_locator,
        }
        mismatched = [name for name, expected in expected_metadata.items()
                      if str(row.get(name) or "") != str(expected)]
        if mismatched:
            raise ValueError(f"{metric} {period}: frozen metadata mismatch ({', '.join(mismatched)})")
        if mapping.locator.startswith("derived:"):
            if mapping.transform != "direct" or mapping.scale:
                raise ValueError(f"{metric} {period}: derived facts support only the direct transform")
            expression = mapping.locator[len("derived:"):]
            operands = re.findall(r"[a-z_][a-z0-9_]*", expression)
            missing = [op for op in operands if (op, period) not in actual_by_key
                       or not str(actual_by_key[(op, period)].get("value") or "").strip()]
            if missing:
                raise ValueError(f"{metric} {period}: derived replay missing operands {missing}")
            values = {op: float(actual_by_key[(op, period)]["value"]) for op in operands}
            expected = eval(expression, {"__builtins__": {}}, values)  # closed fact-map arithmetic
            if not _same_value(value, expected):
                raise ValueError(f"{metric} {period}: frozen derived value does not replay from operands")
            if row.get("lineage_scheme") != "derived" or not all(op in row.get("lineage_key", "") for op in operands):
                raise ValueError(f"{metric} {period}: derived lineage does not identify every operand")
            replayed += 1
            continue

        replay_spec = dict(spec)
        boundary = dict(spec["source_boundary"])
        lineage = str(row.get("lineage_path") or "")
        if row.get("lineage_scheme") == "sec_snapshot":
            match = re.match(r"data/tables/([^/]+)/([^/]+)/", lineage)
            if not match or match.group(1) != ticker:
                raise ValueError(f"{metric} {period}: invalid SEC source lineage {lineage!r}")
            run_id = match.group(2)
            boundary["selected_sec_snapshot"] = run_id
            table_names = re.findall(r"data/tables/[^/]+/[^/]+/([^/]+)\.parquet", lineage)
            for table_name in table_names:
                if (run_id, table_name) not in tables:
                    raise ValueError(f"{metric} {period}: source table is not pinned: {run_id}/{table_name}")
        elif row.get("lineage_scheme") in {"8k_exhibit", "raw_payload"}:
            # The locator's content address must be one of the originals pinned above.
            parsed = re.search(r"(?:raw_payload:[^/]+/|data/raw/[^/]+/[^/]+/)([0-9a-f]{64})/", str(row.get("locator", "")) + "/" + lineage)
            if not parsed:
                parsed = re.search(r"([0-9a-f]{64})", str(row.get("lineage_key", "")))
            if not parsed:
                raise ValueError(f"{metric} {period}: raw source hash is absent from lineage")
            digest = parsed.group(1)
            provider_match = re.match(r"raw_payload:([^/]+)/", str(row.get("locator", "")))
            if row.get("lineage_scheme") == "8k_exhibit":
                provider = "sec"
            elif provider_match is None:
                raise ValueError(f"{metric} {period}: raw-payload locator is malformed")
            else:
                provider = provider_match.group(1)
            if (ticker, provider, digest) not in originals:
                raise ValueError(f"{metric} {period}: source original is not pinned: {provider}/{digest}")
        else:
            raise ValueError(f"{metric} {period}: unsupported populated lineage scheme {row.get('lineage_scheme')!r}")
        replay_spec["source_boundary"] = boundary
        try:
            resolved = resolve(mapping, period, replay_spec)
        except Exception as exc:
            raise ValueError(f"{metric} {period}: source replay failed: {exc}") from exc
        if not _same_value(value, resolved.value):
            raise ValueError(f"{metric} {period}: frozen value {value!r} does not replay (source={resolved.value!r})")
        if row.get("lineage_scheme") != resolved.lineage_scheme:
            raise ValueError(f"{metric} {period}: frozen lineage scheme does not replay")
        if row.get("lineage_path") != resolved.lineage_path:
            raise ValueError(f"{metric} {period}: frozen source path does not replay")
        if row.get("lineage_key") != resolved.lineage_key:
            raise ValueError(f"{metric} {period}: frozen source locator key does not replay")
        replayed += 1

    benchmark_replayed = 0
    for row in benchmark_rows or []:
        if not str(row.get("value") or "").strip():
            continue
        metric, period = row.get("metric", "?"), row.get("period", "?")
        locator = str(row.get("locator") or "")
        if not locator.startswith("raw_payload:"):
            raise ValueError(f"benchmark {metric} {period}: accepted benchmark must resolve from a pinned raw payload")
        required_benchmark_fields = ("units", "basis", "dimension", "transform", "source",
                                     "as_of_date", "locator", "lineage_scheme", "lineage_path", "lineage_key")
        absent = [field for field in required_benchmark_fields if field not in row]
        if absent:
            raise ValueError(f"benchmark {metric} {period}: missing replay metadata {absent}")
        if not str(row.get("units") or "").strip() or not str(row.get("basis") or "").strip():
            raise ValueError(f"benchmark {metric} {period}: units and basis are required for replay")
        if not str(row.get("as_of_date") or "").strip():
            raise ValueError(f"benchmark {metric} {period}: as_of_date is required for replay")
        if row.get("transform", "direct") != "direct":
            raise ValueError(f"benchmark {metric} {period}: only direct raw-payload replay is supported")
        as_of_date = str(row.get("as_of_date") or "")
        if not _ISO_DATE.fullmatch(as_of_date):
            raise ValueError(f"benchmark {metric} {period}: as_of_date must be an ISO date")
        if _ISO_DATE.fullmatch(period) and as_of_date != period:
            raise ValueError(f"benchmark {metric} {period}: dated benchmark as_of_date must equal its period")
        provider_match = re.match(r"raw_payload:([^/]+)/", locator)
        if (provider_match is None
                or re.sub(r"[^a-z0-9]", "", provider_match.group(1).casefold())
                != re.sub(r"[^a-z0-9]", "", str(row.get("source") or "").casefold())):
            raise ValueError(f"benchmark {metric} {period}: source does not match the raw-payload provider")
        mapping = FactMapping(metric, row.get("dimension") or None, str(row.get("basis") or ""),
            str(row.get("units") or ""), locator, "date", "direct", "required")
        try:
            resolved = resolve(mapping, period, spec)
        except Exception as exc:
            raise ValueError(f"benchmark {metric} {period}: source replay failed: {exc}") from exc
        if not _same_value(str(row["value"]), resolved.value):
            raise ValueError(f"benchmark {metric} {period}: frozen value does not replay from pinned source")
        if (row.get("lineage_scheme") != resolved.lineage_scheme
                or row.get("lineage_path") != resolved.lineage_path
                or row.get("lineage_key") != resolved.lineage_key):
            raise ValueError(f"benchmark {metric} {period}: frozen source lineage does not replay")
        benchmark_replayed += 1

    price = spec.get("price")
    if price is not None:
        if not isinstance(price, dict):
            raise ValueError("model_spec.price must be an object when present")
        price_date = str(price.get("date") or "")
        try:
            if not _ISO_DATE.fullmatch(price_date):
                raise ValueError
            date.fromisoformat(price_date)
            price_value = float(price["value"])
            if not math.isfinite(price_value):
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("model_spec.price requires a finite value and ISO date") from exc
        candidates = [row for row in (benchmark_rows or [])
                      if str(row.get("metric") or "") == "price_dated"
                      and str(row.get("value") or "").strip()
                      and (str(row.get("period") or "") == price_date
                           or str(row.get("as_of_date") or "") == price_date)]
        if len(candidates) != 1:
            raise ValueError(f"model_spec.price {price_date}: expected exactly one replayed price_dated benchmark, "
                             f"found {len(candidates)}")
        row = candidates[0]
        if str(row.get("period") or "") != price_date or str(row.get("as_of_date") or "") != price_date:
            raise ValueError(f"model_spec.price {price_date}: benchmark date conflicts with price date")
        if not _same_value(str(row.get("value") or ""), price_value):
            raise ValueError(f"model_spec.price {price_date}: value does not match replayed price_dated benchmark")
    return {"actuals_replayed": replayed, "benchmarks_replayed": benchmark_replayed}

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
