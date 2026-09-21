---
name: pull-financial-data
description: Fetch a company's financial data into a local immutable cache (SEC statements, Yahoo prices and analyst datasets, Alpha Vantage estimates and the last four earnings-call transcripts, Item 2.02 earnings 8-K press releases), or read what is already held as CSV, readable documents or a per-cell dump of the release tables. Use when a task needs financial statements, prices, analyst estimates, earnings-call transcripts, an earnings press release, or a figure from one.
---

# Pull financial data

`financial_data_pull` acquires and caches only — no model, checks, valuation or
interpretation. Run it from its checkout; data lands under `data/` there (or
`FINANCIAL_DATA_PULL_ROOT`). The store is keyed by *issuer*, which defaults to the
ticker.

## Run commands

```sh
cd ~/Dev/financial_data_pull
.venv/bin/financial-data-pull VRT                        # every source, cache-first —
                                                         #  includes the last 4 call transcripts
.venv/bin/financial-data-pull VRT --transcripts none      # opt out of transcripts
.venv/bin/financial-data-pull VRT --transcripts 2026Q1,2026Q2   # name quarters explicitly
.venv/bin/financial-data-pull VRT --sources sec --earnings-8k 10  # statements + 10 earnings 8-Ks
.venv/bin/financial-data-pull VRT --refresh               # add a new snapshot version
.venv/bin/financial-data-pull VRT --cache-only            # zero network
.venv/bin/financial-data-pull VRT --quiet                 # warnings only; no status line
.venv/bin/financial-data-pull VRT --ceiling alpha_vantage=10,sec=40
.venv/bin/financial-data-pull VRT --export-csv            # CSVs from what is held, no network
.venv/bin/financial-data-pull VRT --export-views          # readable releases + cell dump, no network
```

Every run prints the JSON result on **stdout** and one human status line on
**stderr**: `NEW SNAPSHOT <id> — <n> requests spent` when it fetched, `CACHED —
evidence already held, zero network (snapshot <id>)` when it answered from the
store, `no data held for <issuer> (cache-only)` for a cache-only miss, or
`FAILED — nothing published`. INFO progress lines (one per dataset) also go to
stderr; `--quiet` silences both the progress lines and the status line.

## Where every type of data lives

Under `data/` in that checkout (paths use the *issuer*, which defaults to the ticker):

| Wanted | Path |
|---|---|
| 10-K / 10-Q income, balance, cash-flow statements | `data/csv/<issuer>/income_*`, `balance_*`, `cashflow_*` (× `annual_0..2` and `quarterly_0..7`; **index 0 is the most recent filing**) |
| 10-K / 10-Q **documents** | **not archived — by design.** Only their statements are held; there is no copy of the filing text anywhere in the store |
| 8-K earnings press releases (Exhibit 99.1, Item 2.02) | `data/derived/<issuer>/documents/8-k/<filing_date>-<accession>-<exhibit_file>` (open in a browser) |
| Call transcripts | `data/derived/<issuer>/documents/transcript/<quarter>.md` — one Markdown file per held quarter |
| Per-cell dump of every release table | `data/derived/<issuer>/8k_cells.csv` |
| Prices + 7 analyst datasets | `data/csv/<issuer>/yahoo_prices.csv`, `yahoo_*.csv` |
| Alpha Vantage estimates | `data/csv/<issuer>/av_earnings_estimates.csv` |
| Transcript rows (long text) | `data/csv/<issuer>/av_transcript.csv` — multi-line quoted text; read it with a CSV reader, not by eye |
| 8-K filing index | `data/csv/<issuer>/sec_8k.csv` (date, accession, items, exhibit file and path) |
| Coverage — one row per dataset: status + reason | `data/coverage/<issuer>/<run-id>.json` |
| Evidence (immutable, never rewritten) | `data/tables/<issuer>/<run-id>/<table>.parquet` + `snapshot.json`; originals in `data/raw/<issuer>/<provider>/<sha256>/payload.<ext>` |

`data/csv/` and `data/derived/` are derived views: they are **never written by a
plain pull.** They only appear after `--export-csv` / `--export-views`, and they are
rewritable — cite the snapshot or the original under `data/raw/`, never the view.

## Confirm what is held before spending quota

Do this first, always:

1. Run `.venv/bin/financial-data-pull <TICKER> --cache-only` (zero network) and read
   the status line: it says whether the scope is held (`CACHED`) or not
   (`no data held … (cache-only)`).
2. Report to the user what is held before acquiring anything.
3. **Ask the user before any live pull.** A plain pull can spend ~22 SEC requests and
   keep ~100 MB of originals per ticker, plus up to 5 Alpha Vantage requests (one for
   the estimates and one per transcript quarter; the free tier is tightly limited). A
   scope already held costs zero — a second plain pull is `CACHED`.
4. Cap a run the user approved with `--ceiling`; requests are counted and returned
   either way.
5. After a live refresh, run `--export-csv` before reading any CSV (and `--export-views`
   as well when documents or transcripts were pulled — that is what writes
   `documents/8-k/`, `documents/transcript/` and `8k_cells.csv`).

A read-only task needs none of the steps above.

## Reading what is held

Prefer the CSVs. `export_csv` takes, per table, the newest snapshot that actually
carries it; `read_table` reads only the **newest** snapshot, so an 8-K-only run can
KeyError on a statement that is still held — the CSV export avoids that drift.

```python
from financial_data_pull import export_csv, read_table

export_csv("VRT")                                   # (re)writes data/csv/VRT/*.csv
read_table("VRT", "income_annual_0", run_id="...")  # one table from one pinned snapshot
```

For the release tables, read `8k_cells.csv` after `--export-views`: one row per cell,
with `accession, filing_date, exhibit_sha256, table_index, caption, row_kind, row_index,
col_index, row_label, column_label, raw_text, value, unit`. Filter `row_kind == "data"`,
match on `row_label`, read `value`/`unit`, and use `column_label`/`col_index` for the
period. Guidance ranges do not parse: they stay in `raw_text` with a blank `value`. A
release whose exhibit is not HTML (a PDF) has no rows and is named on stderr — read its
copy under `documents/8-k/`. Mapping cells to metrics is the consumer's job; this
library ships no per-ticker metric map.

## Gotchas

- **The default scope moves with the calendar.** A plain pull's scope includes the last
  4 completed calendar quarters, so it changes every quarter. The first plain pull after
  a rollover re-acquires the **whole** source set — SEC ~22 requests + ~100 MB of
  originals, Yahoo, estimates and the new transcript — not just that transcript. A
  plain pull within a quarter is `CACHED`; freshness beyond that is explicit `--refresh`.
- **A quarter that just ended may not be on Alpha Vantage yet.** It is recorded
  `MISSING`, and because the scope is then cached, later plain pulls keep missing it.
  Pass `--refresh` to retry it.
- **Fiscal vs. calendar offset.** The derived labels are calendar quarters; an issuer
  whose calls Alpha Vantage labels differently will MISS. Pass the labels explicitly
  (`--transcripts 2026Q1,2026Q2`) when you know the real ones.
- **Transcripts cost one Alpha Vantage request per new quarter** (held quarters cost 0),
  counted under their own `alpha_vantage_transcripts` ceiling key — `--ceiling
  alpha_vantage=10,alpha_vantage_transcripts=2` caps estimates and transcripts
  independently.
- **Restricting sources drops transcripts.** `--sources sec` (or any set without
  `alpha_vantage`) stays transcript-free instead of raising — the only way to get
  transcripts is to name `alpha_vantage`. `--earnings-8k N` needs `sec`.
- **`--export-csv` / `--export-views` refuse acquisition flags** — run the pull first.
- **SEC needs `EDGAR_IDENTITY` in `.env`; Alpha Vantage needs `ALPHAVANTAGE_API_KEY`.**
  A provider that fails degrades to `FAILED` coverage rows with a reason; the datasets
  that succeeded are still published.
