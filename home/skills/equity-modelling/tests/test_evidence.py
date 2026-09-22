import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from evidence import (FactMapping, _find_period_column, _issued_and_outstanding_shares,
                      _resolve_8k_exhibit_role, build_actuals, load_fact_map, period_end_date,
                      period_end_dates)


class RawPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name) / "data"
        self.sha = "a" * 64
        path = self.store / "raw" / "VRT" / "yahoo" / self.sha
        path.mkdir(parents=True)
        (path / "payload.json").write_text(json.dumps({
            "columns": ["Close"],
            "index": ["2026-09-18T04:00:00.000Z"],
            "data": [[249.39]],
        }))
        self.spec = {
            "ticker": "VRT",
            "source_boundary": {"root": str(self.store), "latest_sec_snapshot": "unused"},
        }

    def tearDown(self):
        self.temp.cleanup()

    def mapping(self, index):
        return FactMapping("price_dated", None, "market", "USD/share",
                           f"raw_payload:yahoo/{self.sha}/payload.json#index={index}&field=Close",
                           "date", "direct", "required")

    def test_resolves_literal_payload_hash(self):
        actuals = build_actuals([self.mapping("{date}")], self.spec, ["2026-09-18"])
        self.assertEqual(actuals[0].value, 249.39)
        self.assertEqual(actuals[0].provenance_status, "verified")

    def test_required_payload_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "required fact unresolved"):
            build_actuals([self.mapping("{date}")], self.spec, ["2026-09-19"])


class RoleLocatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name) / "data"
        cells = self.store / "derived" / "VRT" / "8k_cells.csv"
        cells.parent.mkdir(parents=True)
        self.sha = "b" * 64
        common = {"accession": "ACC", "table_index": "5", "caption": "Regional Segment Results",
                  "exhibit_sha256": self.sha, "column_label": "", "value": ""}
        rows = [
            dict(common, row_kind="header", row_index="1", col_index="3", row_label="",
                 raw_text="Three months ended June 30,"),
            dict(common, row_kind="data", row_index="2", col_index="27", row_label="",
                 raw_text="Organic Δ%(2)"),
            dict(common, row_kind="data", row_index="4", col_index="27", row_label="AMER",
                 raw_text="21.1", value="21.1"),
            dict(common, row_kind="data", row_index="5", col_index="27", row_label="APAC",
                 raw_text="25.7", value="25.7"),
        ]
        with cells.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        self.spec = {"ticker": "VRT", "release_accessions": {"2026Q2": "ACC"}}
        self.mapping = FactMapping("organic_growth_americas", None, "GAAP", "%",
            "8k_exhibit_role:caption=Regional Segment Results|row_labels=AMER|column_role=Organic Δ%(2)"
            f"|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={self.sha}",
            "fiscal_quarter", "direct", "unavailable")

    def tearDown(self):
        self.temp.cleanup()

    def test_role_locator_requires_pinned_table_and_semantic_column_role(self):
        value, sha, keys = _resolve_8k_exhibit_role(self.mapping, "2026Q2", self.spec, self.store, "VRT")
        self.assertEqual((value, sha, keys), (21.1, self.sha, ("ACC", "5", "4", "27")))

    def test_role_locator_rejects_duplicate_target_cells(self):
        path = self.store / "derived" / "VRT" / "8k_cells.csv"
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows.append(dict(rows[2], row_index="9", value="99", raw_text="99"))
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        # Cache keys are immutable store paths; clear this test's fixture entry after editing it.
        from evidence import _cells_cache
        _cells_cache.pop(str(self.store) + "VRT", None)
        self.assertEqual(_resolve_8k_exhibit_role(self.mapping, "2026Q2", self.spec, self.store, "VRT"),
                         (None, None, None))

    def test_role_locator_uses_prior_header_level_for_header_roles(self):
        path = self.store / "derived" / "VRT" / "8k_cells.csv"
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        # These sibling headers must not replace the preceding period header.
        rows.extend([
            dict(rows[0], row_kind="header", row_index="2", col_index="3", row_label="",
                 raw_text="Net income"),
            dict(rows[0], row_kind="header", row_index="2", col_index="39", row_label="",
                 raw_text="Diluted EPS"),
            dict(rows[0], row_kind="data", row_index="8", col_index="39",
                 row_label="Diluted shares", raw_text="390.5", value="390.5"),
        ])
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        from evidence import _cells_cache
        _cells_cache.pop(str(self.store) + "VRT", None)
        mapping = FactMapping("diluted_shares", None, "GAAP", "m shares",
            "8k_exhibit_role:caption=Regional Segment Results|row_labels=Diluted shares"
            f"|column_role=Diluted EPS|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={self.sha}",
            "fiscal_quarter", "direct", "unavailable")
        self.assertEqual(_resolve_8k_exhibit_role(mapping, "2026Q2", self.spec, self.store, "VRT"),
                         (390.5, self.sha, ("ACC", "5", "8", "39")))


class SecLabelTests(unittest.TestCase):
    LABEL = ("Common stock, $0.0001 par value, 700,000,000 shares authorized, "
             "384,936,985 and 382,553,680 shares issued and outstanding at June 30, 2026 "
             "and December 31, 2025, respectively")

    def test_resolves_only_share_count_matched_to_period_end_date(self):
        self.assertEqual(_issued_and_outstanding_shares(self.LABEL, "2026Q2"), 384936985.0)
        self.assertEqual(_issued_and_outstanding_shares(self.LABEL, "2025Q4"), 382553680.0)
        self.assertIsNone(_issued_and_outstanding_shares(self.LABEL, "2026Q1"))

    def test_rejects_ambiguous_label_without_respective_date_pairs(self):
        self.assertIsNone(_issued_and_outstanding_shares(
            "Common stock, 400 shares issued and outstanding at June 30, 2026", "2026Q2"))


class _StubFrame:
    """Minimal stand-in for a parquet frame: `_find_period_column` only reads `.columns`."""

    def __init__(self, columns):
        self.columns = columns


class FiscalCalendarTests(unittest.TestCase):
    """A model_spec period_end_dates mapping must drive every date-sensitive lookup."""

    EXPLICIT = {"2026Q3": "2026-08-02", "2026Q4": "2026-11-01"}

    def test_period_end_date_uses_mapping_then_calendar_fallback(self):
        self.assertEqual(period_end_date("2026Q3", self.EXPLICIT), "2026-08-02")
        self.assertEqual(period_end_date("2026Q3"), "2026-09-30")

    def test_period_end_date_fails_when_mapping_omits_requested_period(self):
        with self.assertRaisesRegex(ValueError, "omits this period"):
            period_end_date("2025Q4", self.EXPLICIT)

    def test_period_end_dates_validates_malformed_mappings(self):
        self.assertEqual(period_end_dates({"periods": {"fiscal_calendar": "x"}}), {})
        self.assertEqual(period_end_dates({"periods": {"period_end_dates": self.EXPLICIT}}), self.EXPLICIT)
        with self.assertRaisesRegex(ValueError, "canonical period"):
            period_end_dates({"periods": {"period_end_dates": {"Q3-2026": "2026-08-02"}}})
        with self.assertRaisesRegex(ValueError, "ISO date"):
            period_end_dates({"periods": {"period_end_dates": {"2026Q3": "08/02/2026"}}})
        with self.assertRaisesRegex(ValueError, "not a real date"):
            period_end_dates({"periods": {"period_end_dates": {"2026Q3": "2026-02-30"}}})

    def test_sec_period_column_uses_mapping(self):
        frame = _StubFrame(["2026-08-02 (Q3)", "2025-07-31 (Q3)"])
        self.assertEqual(_find_period_column(frame, "2026Q3", explicit=self.EXPLICIT), "2026-08-02 (Q3)")
        # A stock/balance-sheet table labels the column with the bare ISO date.
        bare = _StubFrame(["2026-08-02", "2025-07-31"])
        self.assertEqual(_find_period_column(bare, "2026Q3", explicit=self.EXPLICIT), "2026-08-02")
        # Without the mapping the calendar fallback looks for a September column and finds none.
        self.assertIsNone(_find_period_column(frame, "2026Q3"))

    def test_sec_label_matches_non_calendar_period_end(self):
        label = ("Common stock, 700,000,000 shares authorized, "
                 "384,936,985 and 380,100,000 shares issued and outstanding at August 2, 2026 "
                 "and May 3, 2026, respectively")
        explicit = {"2026Q3": "2026-08-02", "2026Q2": "2026-05-03"}
        self.assertEqual(_issued_and_outstanding_shares(label, "2026Q3", explicit), 384936985.0)
        self.assertEqual(_issued_and_outstanding_shares(label, "2026Q2", explicit), 380100000.0)
        # The calendar fallback would look for 2026-09-30 and must not match.
        self.assertIsNone(_issued_and_outstanding_shares(label, "2026Q3"))

    def test_8k_role_period_scope_uses_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "data"
            sha = "c" * 64
            cells = store / "derived" / "AVGO" / "8k_cells.csv"
            cells.parent.mkdir(parents=True)
            common = {"accession": "ACC", "table_index": "5", "caption": "Regional Segment Results",
                      "exhibit_sha256": sha, "column_label": "", "value": ""}
            rows = [
                dict(common, row_kind="header", row_index="1", col_index="3", row_label="",
                     raw_text="Three months ended August 2,"),
                dict(common, row_kind="data", row_index="2", col_index="27", row_label="",
                     raw_text="Organic Δ%(2)"),
                dict(common, row_kind="data", row_index="4", col_index="27", row_label="AMER",
                     raw_text="21.1", value="21.1"),
            ]
            with cells.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            spec = {"ticker": "AVGO", "release_accessions": {"2026Q3": "ACC"}}
            mapping = FactMapping("organic_growth_americas", None, "GAAP", "%",
                "8k_exhibit_role:caption=Regional Segment Results|row_labels=AMER|column_role=Organic Δ%(2)"
                f"|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={sha}",
                "fiscal_quarter", "direct", "unavailable")
            self.assertEqual(_resolve_8k_exhibit_role(mapping, "2026Q3", spec, store, "AVGO", self.EXPLICIT),
                             (21.1, sha, ("ACC", "5", "4", "27")))
            # The calendar fallback (2026-09-30) cannot match this header and must not guess.
            self.assertEqual(_resolve_8k_exhibit_role(mapping, "2026Q3", spec, store, "AVGO"),
                             (None, None, None))
            from evidence import _cells_cache
            _cells_cache.pop(str(store) + "AVGO", None)

    def test_build_actuals_fails_visibly_on_incomplete_or_malformed_mapping(self):
        spec = {"source_boundary": {"root": "/tmp/none"},
                "periods": {"period_end_dates": {"2026Q3": "2026-08-02"}}}
        with self.assertRaisesRegex(ValueError, "omits requested period"):
            build_actuals([], spec, ["2026Q3", "2026Q4"])
        malformed = {"source_boundary": {"root": "/tmp/none"},
                     "periods": {"period_end_dates": {"2026Q3": "soon"}}}
        with self.assertRaisesRegex(ValueError, "ISO date"):
            build_actuals([], malformed, ["2026Q3"])


class MissingReasonTests(unittest.TestCase):
    """A declared `missing_reason` is the frozen row's visible reason; an `unavailable`
    mapping is an intentional gap that must carry one and can never resolve a value."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name) / "data"
        self.spec = {
            "ticker": "AVGO",
            "source_boundary": {"root": str(self.store), "latest_sec_snapshot": "unused"},
        }

    def tearDown(self):
        self.temp.cleanup()

    def _fact_map(self, fact: dict) -> Path:
        path = Path(self.temp.name) / "fact_map.json"
        path.write_text(json.dumps({"schema_version": 1, "ticker": "AVGO", "facts": [fact]}))
        return path

    def test_unavailable_mapping_requires_a_non_empty_reason(self):
        with self.assertRaisesRegex(ValueError, "intentionally unavailable mapping requires"):
            load_fact_map(self._fact_map({
                "metric": "diluted_shares", "basis": "GAAP", "units": "shares_millions",
                "locator": "unavailable", "transform": "direct", "missing_treatment": "unavailable",
            }))

    def test_unavailable_mapping_freezes_a_blank_row_with_its_reason(self):
        mappings = load_fact_map(self._fact_map({
            "metric": "diluted_shares", "basis": "GAAP", "units": "shares_millions",
            "locator": "unavailable", "transform": "direct", "missing_treatment": "unavailable",
            "missing_reason": "the release carries two identically labelled diluted-share rows",
        }))
        rows = build_actuals(mappings, self.spec, ["2024Q4"])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].value)
        self.assertEqual(rows[0].provenance_status, "unavailable")
        self.assertEqual(rows[0].notes, "the release carries two identically labelled diluted-share rows")

    def test_missing_reason_is_carried_into_an_unresolved_row(self):
        mapping = FactMapping(
            "cash", None, "GAAP", "USDm", "sec_snapshot:balance#concept=Us-gaap_Cash",
            "fiscal_quarter", "direct", "unavailable", missing_reason="no balance sheet retained")
        rows = build_actuals([mapping], self.spec, ["2023Q3"])
        self.assertIsNone(rows[0].value)
        self.assertEqual(rows[0].provenance_status, "unresolved")
        self.assertEqual(rows[0].notes, "no balance sheet retained")


if __name__ == "__main__":
    unittest.main()
