"""End-to-end contract tests for the artifact-driven Stage 3 CLI."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from cli import build, check  # noqa: E402


MODULE = '''
class Module:
    def workbook_rows(self, actuals, drivers, periods):
        regional = {"revenue": {"2026Q1": "=em_actual_revenue_2026Q1", "2026Q2": "=em_actual_revenue_2026Q2", "2026Q3E": "=em_actual_revenue_2026Q2"}}
        return {
            "RegionalModel": regional,
            "Earnings": {"adjusted_eps": {"2026Q3E": "=em_model_RegionalModel_revenue_2026Q3E"}},
            "Scenarios": {"base": {"2026Q3E": "=em_model_Earnings_adjusted_eps_2026Q3E"}},
        }
company_module = Module()
'''


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        (self.project / "evidence").mkdir()
        (self.project / "model_spec.json").write_text(json.dumps({
            "ticker": "VRT",
            "periods": {"historical_quarters": ["2026Q1", "2026Q2"],
                        "forecast_quarters": ["2026Q3"]},
            "workbook": {"filename": "VRT_2026-09-22_v2.xlsx",
                         "sheets": ["SourceData", "Drivers", "RegionalModel", "Earnings", "Scenarios"]},
        }))
        (self.project / "model_VRT.py").write_text(MODULE)
        (self.project / "fact_map.json").write_text(json.dumps({
            "schema_version": 1,
            "ticker": "VRT",
            "facts": [{"metric": "revenue", "basis": "GAAP", "units": "USDm",
                       "locator": "sec_snapshot:income#concept=Revenues",
                       "transform": "direct", "missing_treatment": "unavailable"}],
        }))
        with (self.project / "evidence" / "actuals.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "metric", "period", "value", "units", "basis", "dimension", "transform",
                "locator", "lineage_scheme", "lineage_path", "lineage_key", "provenance_status",
                "notes",
            ])
            writer.writeheader()
            for period, value in (("2026Q1", "100"), ("2026Q2", "110")):
                writer.writerow({
                    "metric": "revenue", "period": period, "value": value, "units": "USDm",
                    "basis": "GAAP", "dimension": "", "transform": "direct",
                    "locator": f"sec_snapshot:income#concept=Revenues&period={period}",
                    "lineage_scheme": "sec_snapshot",
                    "lineage_path": "data/tables/VRT/run/income_quarterly_0.parquet",
                    "lineage_key": f"concept=Revenues;col={period}", "provenance_status": "verified",
                    "notes": "",
                })
        with (self.project / "drivers.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["driver_id", "driver_name", "status", "2026Q3"])
            writer.writeheader()
            writer.writerow({"driver_id": "revenue_growth", "driver_name": "Revenue growth",
                             "status": "proposed", "2026Q3": "0.2"})

    def tearDown(self):
        self.temp.cleanup()

    def test_builds_once_from_frozen_artifacts_and_keeps_forecast_blank(self):
        output = build(self.project)
        self.assertTrue(output.is_file())
        report = check(self.project)
        self.assertTrue(report.ok, report.failures)
        from openpyxl import load_workbook
        workbook = load_workbook(output, data_only=False)
        self.assertIsNone(workbook["RegionalModel"]["E7"].value)
        self.assertIsNone(workbook["SourceData"]["B4"].value)
        with self.assertRaises(FileExistsError):
            build(self.project)

    def test_full_rejects_positional_cross_sheet_formula(self):
        output = build(self.project)
        from openpyxl import load_workbook
        workbook = load_workbook(output)
        workbook["RegionalModel"]["E7"] = "='SourceData'!C7"
        workbook.save(output)
        report = check(self.project, mode="full")
        self.assertFalse(report.ok)
        self.assertIn("RegionalModel!E7 uses a positional cross-sheet reference", report.failures)

    def _assert_build_rejects(self, expected: str) -> None:
        with self.assertRaises(ValueError) as raised:
            build(self.project)
        self.assertIn(expected, str(raised.exception))

    def _actuals(self) -> tuple[list[dict[str, str]], list[str]]:
        path = self.project / "evidence" / "actuals.csv"
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            return list(reader), list(reader.fieldnames or [])

    def _write_actuals(self, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
        with (self.project / "evidence" / "actuals.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_rejects_missing_fact_map(self):
        (self.project / "fact_map.json").unlink()
        self._assert_build_rejects("missing fact_map.json")

    def test_build_rejects_non_object_fact_map(self):
        (self.project / "fact_map.json").write_text(json.dumps(["not", "an", "object"]))
        self._assert_build_rejects("fact_map.json")

    def test_build_rejects_actuals_missing_lineage_columns(self):
        rows, _ = self._actuals()
        reduced = [{k: row[k] for k in ("metric", "period", "value")} for row in rows]
        self._write_actuals(reduced, ["metric", "period", "value"])
        self._assert_build_rejects("actuals.csv is missing columns")

    def test_build_rejects_populated_value_without_lineage(self):
        rows, fieldnames = self._actuals()
        rows[0]["lineage_path"] = ""
        self._write_actuals(rows, fieldnames)
        self._assert_build_rejects("populated value lacks lineage")

    def test_build_rejects_unavailable_value_without_reason(self):
        rows, fieldnames = self._actuals()
        rows[0]["value"] = ""
        rows[0]["provenance_status"] = "verified"
        rows[0]["notes"] = ""
        self._write_actuals(rows, fieldnames)
        self._assert_build_rejects("unavailable value has no specific missing reason")

    def test_build_rejects_bare_status_without_specific_notes(self):
        rows, fieldnames = self._actuals()
        rows[0]["value"] = ""
        rows[0]["provenance_status"] = "unavailable"
        rows[0]["notes"] = "unavailable"
        self._write_actuals(rows, fieldnames)
        self._assert_build_rejects("unavailable value has no specific missing reason")

    def test_build_accepts_unavailable_value_with_specific_reason(self):
        rows, fieldnames = self._actuals()
        rows[0]["value"] = ""
        rows[0]["provenance_status"] = "unavailable"
        rows[0]["lineage_path"] = ""
        rows[0]["notes"] = "issuer did not separately disclose the balance"
        self._write_actuals(rows, fieldnames)
        self.assertTrue(build(self.project).is_file())

    def test_build_rejects_missing_expected_actual_row(self):
        rows, fieldnames = self._actuals()
        self._write_actuals([row for row in rows if row["period"] != "2026Q2"], fieldnames)
        self._assert_build_rejects(
            "fact_map.json declares revenue 2026Q2 but actuals.csv has no row")

    def test_build_rejects_duplicate_actuals_rows(self):
        rows, fieldnames = self._actuals()
        self._write_actuals(rows + [dict(rows[0])], fieldnames)
        self._assert_build_rejects("duplicate row")


if __name__ == "__main__":
    unittest.main()
