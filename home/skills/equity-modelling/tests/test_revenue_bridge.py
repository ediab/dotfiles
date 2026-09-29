"""Company-owned revenue bridge contract and pinned-source prepared-project proof."""
from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
from cli import build, check  # noqa: E402
from engine import NINE_SHEET_ORDER, build_workbook  # noqa: E402
from evidence import build_actuals, freeze, load_fact_map  # noqa: E402
from company_revenue_fixture import AsterSystemsCompany, revenue_bridge_project  # noqa: E402
from nine_sheet_fixture import synthetic_project  # noqa: E402
from pull_fixture import create_source  # noqa: E402


class CompanyRevenueBridgeTests(unittest.TestCase):
    def build(self, *, missing_hardware=False, consolidated=125.0):
        spec, actuals, drivers, company = revenue_bridge_project()
        for fact in actuals:
            if fact["metric"] == "consolidated_revenue" and fact["period"] == "2026Q1":
                fact["value"] = consolidated
            if (missing_hardware and fact["metric"] == "hardware_revenue"
                    and fact["period"] == "2026Q1"):
                fact["value"] = None
        return build_workbook(spec, actuals, drivers, company)

    def test_two_category_company_bridge_uses_explicit_base_and_keyed_links(self):
        context = self.build()
        workbook = context.workbook
        self.assertEqual(tuple(workbook.sheetnames), NINE_SHEET_ORDER)
        bridge = workbook["Bridge Model"]
        self.assertEqual(bridge["B7"].value, "Historical segment bridge")
        labels = [bridge.cell(row, 2).value for row in range(7, bridge.max_row + 1)]
        self.assertIn("Hardware Revenue — Same Fiscal Quarter Last Year", labels)
        self.assertIn("Software Revenue — Same Fiscal Quarter Last Year", labels)
        self.assertIn("Hardware Revenue YoY Growth", labels)
        self.assertIn("Software Revenue — Reported / Bridged", labels)
        self.assertIn("Independently Sourced Consolidated Revenue", labels)
        self.assertIn("Segment Revenue Residual", labels)
        self.assertIn("Segment-to-Consolidated Revenue Check", labels)

        # 2026Q1 is the second historical column (D); the base/growth/output formulas
        # reference SourceData values and named Bridge Model rows, never cell addresses.
        self.assertEqual(bridge["D8"].value, '=IF(em_actual_hardware_revenue_2025Q1="","",em_actual_hardware_revenue_2025Q1)')
        self.assertIn("em_actual_hardware_revenue_2026Q1/em_actual_hardware_revenue_2025Q1-1",
                      bridge["D9"].value)
        self.assertIn("em_model_Bridge_Model_hardware_base_same_quarter_last_year_2026Q1",
                      bridge["D10"].value)
        self.assertIn("em_actual_consolidated_revenue_2026Q1", bridge["D16"].value)
        self.assertIn("COUNT(", bridge["D15"].value)
        self.assertIn('"Unavailable"', bridge["D18"].value)
        self.assertIn('"Fail"', bridge["D18"].value)
        self.assertEqual(workbook["Operating Model"]["D11"].value,
                         '=IF(em_model_Bridge_Model_bridged_segment_revenue_total_2026Q1="","",'
                         'em_model_Bridge_Model_bridged_segment_revenue_total_2026Q1)')
        self.assertEqual(workbook["Financial Statements"]["D8"].value,
                         '=IF(em_model_Operating_Model_revenue_2026Q1="","",'
                         'em_model_Operating_Model_revenue_2026Q1)')
        self.assertEqual(workbook["Checks"]["C9"].value,
                         "=em_model_Bridge_Model_segment_to_consolidated_status_2025Q1")
        self.assertEqual(workbook["Checks"]["D9"].value,
                         "=em_model_Bridge_Model_segment_to_consolidated_status_2026Q1")
        self.assertIn("em_model_Bridge_Model_segment_to_consolidated_status_2026Q1",
                      workbook["Outlook"]["D8"].value)
        self.assertNotIn("volume", " ".join(labels).lower())
        self.assertNotIn("price", " ".join(labels).lower())
        self.assertNotIn("mix", " ".join(labels).lower())
        self.assertNotIn("fx", " ".join(labels).lower())

        # Formula inputs are independently sourced; this numeric expected result checks the
        # fixture's underlying arithmetic, while Excel evaluation is performed at the release gate.
        self.assertAlmostEqual(45.0 * (1 + (50.0 / 45.0 - 1)) +
                               55.0 * (1 + (75.0 / 55.0 - 1)), 125.0)
        self.assertEqual(context.workbook["SourceData"]["B7"].value, "Consolidated Revenue")

    def test_missing_segment_is_blank_and_reconciliation_formula_is_unavailable(self):
        context = self.build(missing_hardware=True)
        bridge = context.workbook["Bridge Model"]
        self.assertIn('COUNT(', bridge["D10"].value)
        self.assertIn('<>2,"",', bridge["D10"].value)
        self.assertIn('<>2,"",', bridge["D13"].value)
        self.assertIn('<>2,"",', bridge["D15"].value)
        self.assertIn('"Unavailable"', bridge["D18"].value)
        self.assertIn('"Pass"', bridge["D18"].value)
        # The formulas guard against missing hardware rather than coercing it to zero;
        # the missing SourceData fact remains an empty cell.
        self.assertIsNone(context.workbook["SourceData"]["D8"].value)
        self.assertIn('IF(em_actual_hardware_revenue_2026Q1="","",',
                      context.workbook["Operating Model"]["D8"].value)
        self.assertIn('IF(em_model_Operating_Model_revenue_2026Q1="","",',
                      context.workbook["Financial Statements"]["D8"].value)
        self.assertIn('em_model_Bridge_Model_bridged_segment_revenue_total_2026Q1',
                      context.workbook["Operating Model"]["D11"].value)

    def test_independent_total_mismatch_produces_fail_and_nonzero_residual(self):
        context = self.build(consolidated=126.0)
        bridge = context.workbook["Bridge Model"]
        self.assertIn("em_actual_consolidated_revenue_2026Q1", bridge["D16"].value)
        self.assertIn("em_model_Bridge_Model_segment_revenue_residual_2026Q1", bridge["D18"].value)
        self.assertIn('"Pass","Fail"', bridge["D18"].value)
        self.assertAlmostEqual((50.0 + 75.0) - 126.0, -1.0)
        self.assertNotIn("=em_model_Bridge_Model_bridged_segment_revenue_total_2026Q1",
                         bridge["D18"].value)

    def test_each_historical_period_keeps_its_own_bridge_formula(self):
        spec, actuals, drivers, company = revenue_bridge_project()
        spec["periods"]["historical_quarters"] = ["2024Q1", "2025Q1", "2026Q1"]
        actuals.extend([
            {"metric": "hardware_revenue", "period": "2024Q1", "value": 40.0},
            {"metric": "software_revenue", "period": "2024Q1", "value": 60.0},
            {"metric": "consolidated_revenue", "period": "2024Q1", "value": 100.0},
        ])
        workbook = build_workbook(spec, actuals, drivers, company).workbook
        bridge = workbook["Bridge Model"]
        self.assertIn("em_actual_hardware_revenue_2024Q1", bridge["D8"].value)
        self.assertIn("em_actual_hardware_revenue_2025Q1", bridge["E8"].value)
        self.assertIn("em_actual_hardware_revenue_2025Q1", bridge["D9"].value)
        self.assertIn("em_actual_hardware_revenue_2026Q1", bridge["E9"].value)
        self.assertIn("em_model_Bridge_Model_hardware_base_same_quarter_last_year_2025Q1",
                      bridge["D10"].value)
        self.assertIn("em_model_Bridge_Model_hardware_base_same_quarter_last_year_2026Q1",
                      bridge["E10"].value)
        self.assertIn("em_model_Bridge_Model_segment_to_consolidated_status_2024Q1",
                      workbook["Checks"]["C9"].value)

    def test_prepared_build_and_full_check_replay_segment_and_independent_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "evidence").mkdir()
            spec, mappings = create_source(project / "pull" / "data", "AST", nine_sheet=True,
                                           revenue_bridge=True)
            template, _, _, _ = revenue_bridge_project()
            spec["periods"] = template["periods"]
            spec["forecast_gate"] = template["forecast_gate"]
            spec["workbook"] = {"filename": "AST_2026-09-23_revenue_bridge.xlsx",
                                "sheets": list(NINE_SHEET_ORDER)}
            (project / "model_spec.json").write_text(json.dumps(spec))
            (project / "model_AST.py").write_text(
                inspect.getsource(AsterSystemsCompany) + "\ncompany_module = AsterSystemsCompany()\n")
            (project / "fact_map.json").write_text(json.dumps(
                {"schema_version": 1, "ticker": "AST", "facts": mappings}))
            fact_mappings = load_fact_map(project / "fact_map.json")
            freeze(build_actuals(fact_mappings, spec, spec["periods"]["historical_quarters"]),
                   project / "evidence")
            fields = ["driver_id", "driver_name", "status", *template["periods"]["forecast_quarters"]]
            with (project / "drivers.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()

            with (project / "evidence" / "actuals.csv").open(newline="") as handle:
                frozen = list(csv.DictReader(handle))
            hardware = next(row for row in frozen if row["metric"] == "hardware_revenue"
                            and row["period"] == "2026Q1")
            software = next(row for row in frozen if row["metric"] == "software_revenue"
                            and row["period"] == "2026Q1")
            consolidated = next(row for row in frozen if row["metric"] == "consolidated_revenue"
                               and row["period"] == "2026Q1")
            self.assertEqual(hardware["lineage_scheme"], "sec_snapshot")
            self.assertEqual(software["lineage_scheme"], "sec_snapshot")
            self.assertEqual(consolidated["lineage_scheme"], "8k_exhibit")
            self.assertNotEqual(hardware["lineage_path"], consolidated["lineage_path"])
            self.assertNotEqual(software["lineage_path"], consolidated["lineage_path"])

            output = build(project)
            workbook = __import__("openpyxl").load_workbook(output, data_only=False)
            self.assertEqual(tuple(workbook.sheetnames), NINE_SHEET_ORDER)
            self.assertIn("em_actual_hardware_revenue_2026Q1",
                          workbook["Operating Model"]["D8"].value)
            self.assertIn("em_actual_consolidated_revenue_2026Q1",
                          workbook["Bridge Model"]["D16"].value)
            report = check(project, mode="full")
            self.assertTrue(report.ok, report.failures)
            self.assertIn("source replay: 6 actuals, 0 benchmarks", report.coverage)

            # The same generic nine-sheet renderer also accepts the existing distinct
            # one-revenue-company blueprint; no issuer switch was introduced in the renderer.
            generic_spec, generic_actuals, generic_drivers, generic_company = synthetic_project()
            generic = build_workbook(generic_spec, generic_actuals, generic_drivers, generic_company)
            self.assertEqual(tuple(generic.workbook.sheetnames), NINE_SHEET_ORDER)
            self.assertIn("revenue", generic.module_rows["Operating Model"])


if __name__ == "__main__":
    unittest.main()
