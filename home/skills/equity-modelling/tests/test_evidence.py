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


class SourceReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        sys.path.insert(0, str(Path(__file__).parent))
        from pull_fixture import create_source, fact_mappings
        self.create_source = create_source
        self.fact_mappings = fact_mappings

    def tearDown(self):
        self.temp.cleanup()

    def test_sec_concept_dimension_must_resolve_to_one_row(self):
        spec, facts = self.create_source(Path(self.temp.name) / "duplicate-sec" / "data", "TST",
                                         duplicate_sec_rows=True)
        with self.assertRaisesRegex(ValueError, "ambiguous SEC concept 'Revenues'"):
            build_actuals(self.fact_mappings(facts[:1]), spec, ["2026Q2"])

    def test_replay_accepts_multiple_pinned_snapshots_for_distinct_lineage(self):
        import shutil
        from pull_fixture import digest
        from evidence import replay_frozen_evidence
        root = Path(self.temp.name) / "multiple" / "data"
        spec, facts = self.create_source(root, "TST")
        spec["periods"]["historical_quarters"] = ["2026Q1", "2026Q2"]
        mappings = self.fact_mappings(facts)
        rows = build_actuals(mappings, spec, ["2026Q1", "2026Q2"])
        old = root / "tables" / "TST" / "run-fixture-1"
        new = root / "tables" / "TST" / "run-fixture-2"
        new.mkdir()
        shutil.copyfile(old / "income_quarterly_0.parquet", new / "income_quarterly_0.parquet")
        manifest = json.loads((old / "snapshot.json").read_text())
        manifest["run_id"] = "run-fixture-2"
        new_snapshot = new / "snapshot.json"
        new_snapshot.write_text(json.dumps(manifest, sort_keys=True))
        table_hash = digest((new / "income_quarterly_0.parquet").read_bytes())
        spec["source_boundary"]["snapshots"].append({"ticker": "TST", "run_id": "run-fixture-2",
                                                       "sha256": digest(new_snapshot.read_bytes())})
        spec["source_boundary"]["tables"].append({"ticker": "TST", "run_id": "run-fixture-2",
            "name": "income_quarterly_0", "sha256": table_hash})
        for row in rows:
            if row.lineage_scheme == "sec_snapshot":
                row.lineage_path = row.lineage_path.replace("run-fixture-1", "run-fixture-2")
        frozen = [row.__dict__ for row in rows]
        result = replay_frozen_evidence(spec, frozen, [], mappings)
        self.assertEqual(result, {"actuals_replayed": 3, "benchmarks_replayed": 0})

    def test_unit_scale_is_applied_and_replayed_from_source_arithmetic(self):
        from evidence import replay_frozen_evidence
        spec, facts = self.create_source(Path(self.temp.name) / "scaled" / "data", "TST")
        spec["periods"]["historical_quarters"] = ["2026Q2"]
        facts = [dict(facts[0], transform="unit_scale", scale=1)]
        mappings = self.fact_mappings(facts)
        rows = build_actuals(mappings, spec, ["2026Q2"])
        self.assertEqual(rows[0].value, 1100.0)
        result = replay_frozen_evidence(spec, [rows[0].__dict__], [], mappings)
        self.assertEqual(result, {"actuals_replayed": 1, "benchmarks_replayed": 0})

    def test_sign_flip_and_ytd_deaccumulation_replay_applied_arithmetic(self):
        from evidence import replay_frozen_evidence
        spec, facts = self.create_source(Path(self.temp.name) / "transforms" / "data", "TST")
        spec["periods"]["historical_quarters"] = ["2026Q2"]
        for transform, expected in (("sign_flip", -110.0), ("ytd_deaccumulate", 140.0)):
            with self.subTest(transform=transform):
                mapping = self.fact_mappings([dict(facts[0], transform=transform)])
                rows = build_actuals(mapping, spec, ["2026Q2"])
                self.assertEqual(rows[0].value, expected)
                replay_frozen_evidence(spec, [rows[0].__dict__], [], mapping)

    def test_quarterly_fact_does_not_fall_back_to_annual_fy_value(self):
        from unittest.mock import patch
        from evidence import resolve
        spec, facts = self.create_source(Path(self.temp.name) / "no-quarter" / "data", "TST")
        mapping = self.fact_mappings([facts[0]])[0]
        with patch("evidence._find_in_quarterly", return_value=(None, None, None)), patch(
                "evidence._find_in_annual",
                return_value=("income_annual_0", "2026-12-31 (FY)", 999.0)) as annual:
            resolved = resolve(mapping, "2026Q2", spec)
        self.assertIsNone(resolved.value)
        annual.assert_not_called()

    def test_q4_transform_is_rejected_for_non_q4_period(self):
        spec, facts = self.create_source(Path(self.temp.name) / "wrong-q4" / "data", "TST")
        mapping = self.fact_mappings([dict(facts[0], transform="q4_from_fy_minus_9m")])
        with self.assertRaisesRegex(ValueError, "only valid for Q4 periods"):
            build_actuals(mapping, spec, ["2026Q2"])


class RawPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        sys.path.insert(0, str(Path(__file__).parent))
        from pull_fixture import create_source
        self.spec, _ = create_source(Path(self.temp.name) / "pull" / "data", "VRT")
        self.original = next(item for item in self.spec["source_boundary"]["originals"]
                             if item["provider"] == "yahoo")

    def tearDown(self):
        self.temp.cleanup()

    def mapping(self, index):
        return FactMapping("price_dated", None, "market", "USD/share",
                           f"raw_payload:yahoo/{self.original['sha256']}/payload.json#index={index}&field=Close",
                           "date", "direct", "required")

    def test_resolves_literal_payload_hash(self):
        actuals = build_actuals([self.mapping("{date}")], self.spec, ["2026-09-18"])
        self.assertEqual(actuals[0].value, 250.0)
        self.assertEqual(actuals[0].provenance_status, "verified")

    def test_required_payload_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "required fact unresolved"):
            build_actuals([self.mapping("{date}")], self.spec, ["2026-09-19"])

    def test_duplicate_date_indexes_fail_instead_of_selecting_first(self):
        from pull_fixture import create_source
        spec, _ = create_source(Path(self.temp.name) / "duplicate-index" / "data", "VRT",
                                duplicate_quote_date=True)
        source = next(item for item in spec["source_boundary"]["originals"]
                      if item["provider"] == "yahoo")
        mapping = FactMapping("price_dated", None, "market", "USD/share",
            f"raw_payload:yahoo/{source['sha256']}/payload.json#index={{date}}&field=Close",
            "date", "direct", "required")
        with self.assertRaisesRegex(ValueError, "ambiguous raw-payload index.*2026-09-18"):
            build_actuals([mapping], spec, ["2026-09-18"])


class RoleLocatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        sys.path.insert(0, str(Path(__file__).parent))
        from pull_fixture import create_source
        self.spec, _ = create_source(Path(self.temp.name) / "pull" / "data", "VRT")
        original = next(item for item in self.spec["source_boundary"]["originals"]
                        if item["provider"] == "sec")
        self.mapping = FactMapping("organic_growth_americas", None, "GAAP", "%",
            "8k_exhibit_role:caption=Regional Segment Results|row_labels=AMER|column_role=Organic Δ%(2)"
            f"|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={original['sha256']}",
            "fiscal_quarter", "direct", "unavailable")

    def tearDown(self):
        self.temp.cleanup()

    def test_role_locator_replays_from_pinned_original(self):
        # A stale, mutable export must not affect the raw-original result.
        view = Path(self.spec["source_boundary"]["root"]) / "derived" / "VRT" / "8k_cells.csv"
        view.parent.mkdir(parents=True)
        view.write_text("accession,value\\nACC,999\\n")
        value, sha, keys = _resolve_8k_exhibit_role(self.mapping, "2026Q2", self.spec,
                                                    Path(self.spec["source_boundary"]["root"]), "VRT")
        self.assertEqual(value, 21.1)
        self.assertEqual(sha, self.mapping.locator.rsplit("=", 1)[1])
        self.assertTrue(keys)

    def test_role_period_header_cannot_be_borrowed_from_another_table(self):
        from pull_fixture import create_source
        spec, _ = create_source(Path(self.temp.name) / "cross-table" / "data", "VRT",
                                cross_table_scope=True)
        source = next(item for item in spec["source_boundary"]["originals"]
                      if item["provider"] == "sec")
        mapping = FactMapping("organic_growth_americas", None, "GAAP", "%",
            "8k_exhibit_role:caption=Regional Segment Results|row_labels=AMER|column_role=Organic Δ%(2)"
            f"|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={source['sha256']}",
            "fiscal_quarter", "direct", "unavailable")
        self.assertEqual(_resolve_8k_exhibit_role(mapping, "2026Q2", spec,
                         Path(spec["source_boundary"]["root"]), "VRT"), (None, None, None))

    def test_role_locator_rejects_duplicate_candidates_with_diagnostic(self):
        from pull_fixture import create_source
        dup, _ = create_source(Path(self.temp.name) / "duplicate" / "data", "VRT", duplicate_role=True)
        source = next(item for item in dup["source_boundary"]["originals"] if item["provider"] == "sec")
        mapping = FactMapping("organic_growth_americas", None, "GAAP", "%",
            "8k_exhibit_role:caption=Regional Segment Results|row_labels=AMER|column_role=Organic Δ%(2)"
            f"|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={source['sha256']}",
            "fiscal_quarter", "direct", "unavailable")
        with self.assertRaisesRegex(ValueError, r"organic_growth_americas 2026Q2: ambiguous 8-K candidates"):
            _resolve_8k_exhibit_role(mapping, "2026Q2", dup,
                                     Path(dup["source_boundary"]["root"]), "VRT")

    def test_generic_8k_locator_rejects_duplicate_candidates_with_diagnostic(self):
        from pull_fixture import create_source
        from evidence import _resolve_8k_exhibit
        dup, _ = create_source(Path(self.temp.name) / "duplicate-generic" / "data", "VRT",
                               duplicate_generic=True)
        mapping = FactMapping("adjusted_operating_profit", None, "adjusted", "USDm",
            "8k_exhibit:row_label=Adjusted operating profit|col_pattern={month} {day}, {year}",
            "fiscal_quarter", "direct", "required")
        with self.assertRaisesRegex(ValueError, r"adjusted_operating_profit 2026Q2: ambiguous 8-K candidates"):
            _resolve_8k_exhibit(mapping, "2026Q2", dup,
                                Path(dup["source_boundary"]["root"]), "VRT")


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
        from pull_fixture import create_source
        with tempfile.TemporaryDirectory() as temp:
            spec, _ = create_source(Path(temp) / "pull" / "data", "AVGO")
            original = next(item for item in spec["source_boundary"]["originals"]
                            if item["provider"] == "sec")
            spec["release_accessions"] = {"2026Q3": "ACC"}
            explicit = {"2026Q3": "2026-06-30"}
            spec["periods"]["period_end_dates"] = explicit
            mapping = FactMapping("organic_growth_americas", None, "GAAP", "%",
                "8k_exhibit_role:caption=Regional Segment Results|row_labels=AMER|column_role=Organic Δ%(2)"
                f"|period_scope=Three months ended {{month}} {{day}}|exhibit_sha256={original['sha256']}",
                "fiscal_quarter", "direct", "unavailable")
            root = Path(spec["source_boundary"]["root"])
            self.assertEqual(_resolve_8k_exhibit_role(mapping, "2026Q3", spec, root, "AVGO", explicit)[0], 21.1)
            self.assertEqual(_resolve_8k_exhibit_role(mapping, "2026Q3", spec, root, "AVGO"),
                             (None, None, None))

    def test_build_actuals_fails_visibly_on_incomplete_or_malformed_mapping(self):
        from pull_fixture import create_source
        with tempfile.TemporaryDirectory() as temp:
            spec, _ = create_source(Path(temp) / "calendar" / "data", "VRT")
            spec["periods"]["period_end_dates"] = {"2026Q3": "2026-08-02"}
            with self.assertRaisesRegex(ValueError, "omits requested period"):
                build_actuals([], spec, ["2026Q3", "2026Q4"])
            malformed = dict(spec)
            malformed["periods"] = {"period_end_dates": {"2026Q3": "soon"}}
            with self.assertRaisesRegex(ValueError, "ISO date"):
                build_actuals([], malformed, ["2026Q3"])


class MissingReasonTests(unittest.TestCase):
    """A declared `missing_reason` is the frozen row's visible reason; an `unavailable`
    mapping is an intentional gap that must carry one and can never resolve a value."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        sys.path.insert(0, str(Path(__file__).parent))
        from pull_fixture import create_source
        self.spec, _ = create_source(Path(self.temp.name) / "pull" / "data", "AVGO")
        self.store = Path(self.spec["source_boundary"]["root"])

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
