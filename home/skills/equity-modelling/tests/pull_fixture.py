"""Small immutable pull-store fixture used by evidence and CLI contract tests."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PULL_CHECKOUT = next((parent.parent / "financial_data_pull" for parent in Path(__file__).resolve().parents
                      if (parent.parent / "financial_data_pull" / "pyproject.toml").is_file()), None)
if PULL_CHECKOUT is None:
    raise RuntimeError("tests require the adjacent financial_data_pull checkout")
for candidate in (PULL_CHECKOUT / "src", *list((PULL_CHECKOUT / ".venv/lib").glob("python3.*/site-packages"))):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_source(root: Path, ticker: str = "TST", *, duplicate_role: bool = False,
                  duplicate_generic: bool = False, duplicate_sec_rows: bool = False,
                  duplicate_quote_date: bool = False, cross_table_scope: bool = False,
                  nine_sheet: bool = False, revenue_bridge: bool = False,
                  revenue_bridge_mismatch: bool = False) -> tuple[dict, list[dict]]:
    """Create two immutable source kinds: a snapshot parquet and an SEC HTML original."""
    import pandas as pd

    checkout = root.parent
    checkout.mkdir(parents=True, exist_ok=True)
    for name, target in (("src", PULL_CHECKOUT / "src"), (".venv", PULL_CHECKOUT / ".venv")):
        link = checkout / name
        if not link.exists():
            link.symlink_to(target, target_is_directory=True)

    run_id = "run-fixture-1"
    snapshot_dir = root / "tables" / ticker / run_id
    snapshot_dir.mkdir(parents=True)
    parquet = snapshot_dir / "income_quarterly_0.parquet"
    sec_rows = [{"concept": "Revenues", "dimension_member": None, "dimension_label": None,
                 "label": "Revenue", "2026-03-31 (Q1)": 100.0, "2026-06-30 (Q2)": 110.0,
                 "2026-03-31 (YTD)": 100.0, "2026-06-30 (YTD)": 240.0}]
    if nine_sheet:
        sec_rows = [
            {"concept": concept, "dimension_member": None, "dimension_label": None,
             "label": label, "2025-03-31 (Q1)": prior, "2026-03-31 (Q1)": current}
            for concept, label, prior, current in (
                ("Revenues", "Revenue", 100.0, 125.0),
                ("NetIncomeLoss", "Net income", 10.0, 15.0),
                ("WeightedAverageNumberOfDilutedShares", "Diluted shares", 10.0, 10.0),
            )
        ]
        if revenue_bridge:
            sec_rows.extend([
                {"concept": "Revenues", "dimension_member": member,
                 "dimension_label": f"RevenueSegmentAxis:{member}", "label": label,
                 "2025-03-31 (Q1)": prior, "2026-03-31 (Q1)": current}
                for member, label, prior, current in (
                    ("HardwareMember", "Hardware Revenue", 45.0, 50.0),
                    ("SoftwareMember", "Software Revenue", 55.0, 75.0),
                )
            ])
    if duplicate_sec_rows:
        sec_rows.append(dict(sec_rows[0], label="Revenue duplicate"))
    frame = pd.DataFrame(sec_rows)
    frame.to_parquet(parquet, index=False)

    html_rows = ["<tr><td>Adjusted operating profit</td><td>42.5</td></tr>",
                 "<tr><td>AMER</td><td>21.1</td></tr>"]
    if duplicate_generic:
        html_rows.append("<tr><td>Adjusted operating profit</td><td>43.5</td></tr>")
    if duplicate_role:
        html_rows.append("<tr><td>AMER</td><td>22.1</td></tr>")
    if cross_table_scope:
        html = ("<!doctype html><html><body>"
                "<table><caption>Regional Segment Results</caption>"
                "<thead><tr><th>Metric</th><th>Three months ended March 31, 2026</th></tr>"
                "<tr><th>Region</th><th>Organic Δ%(2)</th></tr></thead>"
                "<tbody><tr><td>AMER</td><td>21.1</td></tr></tbody></table>"
                "<table><caption>Regional Segment Results</caption>"
                "<thead><tr><th>Metric</th><th>Three months ended June 30, 2026</th></tr>"
                "<tr><th>Region</th><th>Organic Δ%(2)</th></tr></thead>"
                "<tbody><tr><td>OTHER</td><td>30.0</td></tr></tbody></table>"
                "</body></html>").encode()
    else:
        html = ("<!doctype html><html><body><table><caption>Regional Segment Results</caption>"
                "<thead><tr><th>Metric</th><th>Three months ended June 30, 2026</th></tr>"
                "<tr><th>Region</th><th>Organic Δ%(2)</th></tr></thead><tbody>"
                + "".join(html_rows) + "</tbody></table></body></html>").encode()
    sec_hash = digest(html)
    sec_dir = root / "raw" / ticker / "sec" / sec_hash
    sec_dir.mkdir(parents=True)
    (sec_dir / "payload.htm").write_bytes(html)

    independent_releases = []
    if nine_sheet:
        totals = ((2025, 100.0), (2026, 125.0))
        if revenue_bridge:
            totals = ((2025, 100.0), (2026, 126.0 if revenue_bridge_mismatch else 125.0))
        for year, revenue in totals:
            release = ("<!doctype html><html><body><table><caption>Consolidated Results</caption>"
                       f"<thead><tr><th>Metric</th><th>Three months ended March 31, {year}</th></tr></thead>"
                       f"<tbody><tr><td>Consolidated revenue</td><td>{revenue}</td></tr></tbody>"
                       "</table></body></html>").encode()
            release_hash = digest(release)
            release_dir = root / "raw" / ticker / "sec" / release_hash
            release_dir.mkdir(parents=True)
            (release_dir / "payload.htm").write_bytes(release)
            independent_releases.append({"ticker": ticker, "provider": "sec", "run_id": run_id,
                                         "sha256": release_hash, "filename": "payload.htm",
                                         "accession": f"ACC{year}"})

    quote = {"columns": ["Close"],
             "index": ["2026-09-18T04:00:00.000Z", "2026-09-18T00:00:00.000Z"]
                      if duplicate_quote_date else ["2026-09-18T04:00:00.000Z"],
             "data": [[250.0], [251.0]] if duplicate_quote_date else [[250.0]]}
    quote_bytes = json.dumps(quote, separators=(",", ":")).encode()
    quote_hash = digest(quote_bytes)
    quote_dir = root / "raw" / ticker / "yahoo" / quote_hash
    quote_dir.mkdir(parents=True)
    (quote_dir / "payload.json").write_bytes(quote_bytes)

    table_hash = digest(parquet.read_bytes())
    snapshot = {
        "issuer": ticker, "ticker": ticker, "run_id": run_id,
        "table_hashes": {"income_quarterly_0": table_hash},
        "originals": {"sec_8k_ACC": str(sec_dir / "payload.htm"),
                      "yahoo_quote": str(quote_dir / "payload.json"),
                      **{f"sec_8k_{item['accession']}": str(root / "raw" / ticker / "sec" /
                          item["sha256"] / "payload.htm") for item in independent_releases}},
    }
    snapshot_path = snapshot_dir / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, sort_keys=True))
    boundary = {
        "mode": "pull-data-only", "root": str(root), "selected_sec_snapshot": run_id,
        "snapshots": [{"ticker": ticker, "run_id": run_id, "sha256": digest(snapshot_path.read_bytes())}],
        "tables": [{"ticker": ticker, "run_id": run_id, "name": "income_quarterly_0",
                    "sha256": table_hash}],
        "originals": [
            {"ticker": ticker, "provider": "sec", "run_id": run_id, "sha256": sec_hash,
             "filename": "payload.htm", "accession": "ACC"},
            {"ticker": ticker, "provider": "yahoo", "run_id": run_id, "sha256": quote_hash,
             "filename": "payload.json"},
            *independent_releases,
        ],
    }
    spec = {"ticker": ticker, "source_boundary": boundary,
            "release_accessions": {"2026Q2": "ACC", **({"2025Q1": "ACC2025", "2026Q1": "ACC2026"}
                                                  if nine_sheet else {})},
            "periods": {"historical_quarters": ["2026Q2"]}}
    if nine_sheet:
        if revenue_bridge:
            return spec, [
                {"metric": "hardware_revenue", "dimension": "RevenueSegmentAxis=HardwareMember",
                 "basis": "GAAP", "units": "USDm",
                 "locator": "sec_snapshot:income#concept=Revenues&dimension_member=HardwareMember",
                 "transform": "segment_axis_filter", "missing_treatment": "required"},
                {"metric": "software_revenue", "dimension": "RevenueSegmentAxis=SoftwareMember",
                 "basis": "GAAP", "units": "USDm",
                 "locator": "sec_snapshot:income#concept=Revenues&dimension_member=SoftwareMember",
                 "transform": "segment_axis_filter", "missing_treatment": "required"},
                {"metric": "consolidated_revenue", "basis": "GAAP", "units": "USDm",
                 "locator": "8k_exhibit:row_label=Consolidated revenue|col_pattern={month} {day}, {year}",
                 "transform": "direct", "missing_treatment": "required"},
            ]
        return spec, [
            {"metric": metric, "basis": "GAAP", "units": units,
             "locator": locator, "transform": "direct", "missing_treatment": "required"}
            for metric, units, locator in (
                ("revenue", "USDm", "sec_snapshot:income#concept=Revenues"),
                ("net_income", "USDm", "sec_snapshot:income#concept=NetIncomeLoss"),
                ("diluted_shares", "shares_m",
                 "sec_snapshot:income#concept=WeightedAverageNumberOfDilutedShares"),
                ("consolidated_revenue", "USDm",
                 "8k_exhibit:row_label=Consolidated revenue|col_pattern={month} {day}, {year}"),
            )
        ]
    return spec, [
        {"metric": "revenue", "basis": "GAAP", "units": "USDm",
         "locator": "sec_snapshot:income#concept=Revenues", "transform": "direct",
         "missing_treatment": "required"},
        {"metric": "adjusted_operating_profit", "basis": "adjusted", "units": "USDm",
         "locator": "8k_exhibit:row_label=Adjusted operating profit|col_pattern={month} {day}, {year}",
         "transform": "direct", "missing_treatment": "required", "periods": ["2026Q2"]},
    ]


def price_benchmark_row(spec: dict) -> dict:
    """Return the accepted dated benchmark row matching the fixture's pinned quote."""
    source = next(item for item in spec["source_boundary"]["originals"]
                  if item["provider"] == "yahoo")
    locator = (f"raw_payload:yahoo/{source['sha256']}/payload.json"
               "#index={date}&field=Close")
    return {
        "metric": "price_dated", "period": "2026-09-18", "value": "250.0",
        "units": "USD/share", "basis": "market", "dimension": "", "transform": "direct",
        "source": "yahoo", "as_of_date": "2026-09-18", "locator": locator,
        "lineage_scheme": "raw_payload",
        "lineage_path": str(Path(spec["source_boundary"]["root"]) / "raw" / spec["ticker"] /
                             "yahoo" / source["sha256"] / "payload.json"),
        "lineage_key": "index=2026-09-18T04:00:00.000Z;field=Close",
    }


def fact_mappings(facts: list[dict]):
    from evidence import FactMapping
    return [FactMapping(f["metric"], f.get("dimension"), f["basis"], f["units"], f["locator"],
                        f.get("period_kind", "fiscal_quarter"), f["transform"],
                        f.get("missing_treatment", "unavailable"), scale=f.get("scale", 0),
                        periods=f.get("periods"), period_hashes=f.get("period_hashes")) for f in facts]
