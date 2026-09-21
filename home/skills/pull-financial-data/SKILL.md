---
name: pull-financial-data
description: Fetch a company's financial data into a local immutable cache (SEC statements, Yahoo prices and analyst datasets, Alpha Vantage estimates and call transcripts, Item 2.02 earnings 8-K press releases), or read what is already held as CSV, readable documents or a per-cell dump of the release tables. Use when a task needs financial statements, prices, analyst estimates, earnings-call transcripts, an earnings press release, or a figure from one.
---

# Pull financial data

`financial_data_pull` acquires and caches only — no model, checks, valuation or
interpretation. Run it from its checkout:

```sh
cd ~/Dev/financial_data_pull
.venv/bin/financial-data-pull VRT                     # all sources, cache-first
.venv/bin/financial-data-pull VRT --refresh           # add a new snapshot version
.venv/bin/financial-data-pull VRT --sources sec --earnings-8k 10
.venv/bin/financial-data-pull VRT --export-csv        # CSVs from what is held, no network
.venv/bin/financial-data-pull VRT --export-views      # readable release + cell dump, no network
```

Data lands under `data/` in that checkout (or `FINANCIAL_DATA_PULL_ROOT`).

## Read what is already held (default; no network)

Prefer the CSVs. `export_csv` takes, per table, the newest snapshot that actually
carries it. `read_table` reads only the **newest** snapshot, so an 8-K-only run can
KeyError on a statement that is still held — that is the drift the CSV export avoids.

```python
from financial_data_pull import export_csv, read_table

export_csv("VRT")                                   # (re)writes data/csv/VRT/*.csv
read_table("VRT", "income_annual_0", run_id="...")  # one table from one pinned snapshot
```

- SEC statements: `income_` / `balance_` / `cashflow_` × `annual_0..2` and
  `quarterly_0..7` (index 0 is the most recent filing); one row per XBRL concept,
  period columns labelled as the filing states them.
- Yahoo: `yahoo_prices` plus 7 analyst datasets (`yahoo_*`).
- Alpha Vantage: `av_earnings_estimates`, and `av_transcript` when quarters were
  requested.

`pull("TICKER", cache_only=True)` returns `{"status": "MISSING: NOT_RETRIEVED"}`
when nothing is held for that scope.

## Earnings documents

Run `--export-views` once (offline, seconds) and read `data/derived/VRT/`:

- `documents/8-k/<date>-<accession>-<exhibit>.htm` — the ten Item 2.02 releases, Exhibit
  99.1, under readable names (open in a browser).
- `documents/transcript/<quarter>.md` — each held call as Markdown, one speaker turn per
  paragraph.
- `8k_cells.csv` — one row per cell of every table of every held release:
  `accession, filing_date, exhibit_sha256, table_index, caption, row_kind, row_index,
  col_index, row_label, column_label, raw_text, value, unit`. Filter
  `row_kind == "data"`, match on `row_label` (`Net sales`, `Adjusted diluted EPS(1)`,
  `Free cash flow`), read `value`/`unit`, and use `column_label`/`col_index` for the
  period. Guidance ranges do not parse: they stay in `raw_text` with a blank `value`.
  `data/csv/VRT/sec_8k.csv` is still the index (per filing: date, accession, items,
  exhibit file and path).

The derived files are rewritable views, never evidence: cite the snapshot or the original
`data/raw/.../payload.htm`, and re-run `--export-views` after a refresh. This library ships
no per-ticker metric map — `8k_cells.csv` is cells, and mapping cells to metrics is the
consumer's job.

## Cost before a fresh pull

- SEC: ~22 requests for the 11 statements filings, ~1 more per 8-K filing, plus a
  few for the filing index, and the preserved originals run to ~100 MB per ticker.
  Needs `EDGAR_IDENTITY` in `.env`.
- Alpha Vantage free tier is tightly limited: the estimates cost one request;
  transcripts are opt-in, one request per quarter, spaced and retried.
  `--ceiling alpha_vantage=10,sec=40` caps a run (requests are reported either way).
- Yahoo is unofficial and free.
- `--earnings-8k` (and `transcripts=`) makes a **new scope**, so the first such run
  re-acquires its whole source set — Yahoo, Alpha Vantage and all 11 SEC filings,
  not only the documents. For documents only, name `--sources sec` (plus
  `alpha_vantage` when transcripts are wanted).
- Freshness is explicit and there is no TTL: a plain pull is a cache hit until
  `refresh=True`, and a plain `pull(ticker)` spends exactly one Alpha Vantage request.

A read-only task needs none of the above. Ask the user before a live pull that
spends quota.
