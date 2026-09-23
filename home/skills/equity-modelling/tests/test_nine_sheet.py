"""End-to-end synthetic workbook contract for the thin nine-sheet renderer."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
from engine import EngineError, build_workbook  # noqa: E402
from nine_sheet_fixture import NINE_SHEET_ORDER, synthetic_project  # noqa: E402


class NineSheetWorkbookTests(unittest.TestCase):
    def build(self):
        spec, actuals, drivers, company = synthetic_project()
        return build_workbook(spec, actuals, drivers, company)

    def test_synthetic_history_flows_through_all_nine_ordered_sheets(self):
        context = self.build()
        workbook = context.workbook
        self.assertEqual(tuple(workbook.sheetnames), NINE_SHEET_ORDER)
        self.assertEqual(workbook["SourceData"]["B7"].value, "Consolidated Revenue")
        self.assertEqual(workbook["Operating Model"]["B7"].value, "Operating results")
        self.assertEqual(workbook["Operating Model"]["B8"].value, "Revenue")
        self.assertEqual(workbook["Operating Model"]["B9"].value, "Revenue YoY")
        self.assertEqual(workbook["Operating Model"]["D9"].value,
                         '=IFERROR(em_actual_revenue_2026Q1/em_actual_revenue_2025Q1-1,"")')
        self.assertEqual(workbook["Operating Model"]["D9"].number_format, "0.0%;(0.0%);-")
        self.assertIsNone(workbook["Operating Model"]["C9"].value,
                          "missing prior-year comparison must remain blank")
        self.assertEqual(workbook["Bridge Model"]["D9"].value,
                         "=em_model_Bridge_Model_base_revenue_2026Q1*(1+em_model_Bridge_Model_revenue_growth_2026Q1)")
        self.assertIn("em_actual_consolidated_revenue_2026Q1",
                      workbook["Bridge Model"]["D10"].value)
        self.assertEqual(workbook["Financial Statements"]["D8"].value,
                         "=em_model_Operating_Model_net_income_2026Q1")
        self.assertIn("em_benchmark_price_dated", workbook["Valuation"]["D8"].value)
        self.assertIn("em_model_Checks_revenue_check_2026Q1",
                      workbook["Outlook"]["D11"].value)
        self.assertIn("em_model_Bridge_Model_revenue_check_2026Q1",
                      workbook["Checks"]["D8"].value)
        self.assertIn("Unavailable (not supplied)",
                      workbook["Consensus"]["B7"].value)
        self.assertIn("actual.diluted_shares.2026Q1", context.references._names)

    def test_inputs_show_proposals_but_all_eight_forecast_periods_are_inactive(self):
        context = self.build()
        workbook = context.workbook
        self.assertEqual(len(context.periods.forecasts), 8)
        self.assertEqual(workbook["Inputs"]["D6"].value, "Q2 2026E")
        self.assertEqual(workbook["Inputs"]["K6"].value, "Q1 2028E")
        self.assertEqual(workbook["Inputs"]["D7"].value, 0.1)
        self.assertEqual(workbook["Inputs"]["C7"].value, "Proposed")
        for sheet in ("Outlook", "Operating Model", "Bridge Model", "Financial Statements",
                      "Valuation", "Consensus", "Checks"):
            for row in range(7, workbook[sheet].max_row + 1):
                for column in range(5, 13):
                    self.assertIsNone(workbook[sheet].cell(row, column).value,
                                      f"{sheet} forecast row {row}, column {column} is active")
        self.assertTrue(all(value is None for row in context.active_drivers.values()
                            for value in row.values()))

    def test_company_rows_accept_human_labels_and_reject_positional_references(self):
        spec, actuals, drivers, company = synthetic_project()
        original_rows = company.workbook_rows

        def invalid_rows(actuals, drivers, periods):
            rows = original_rows(actuals, drivers, periods)
            rows["Operating Model"]["bad_reference"] = {
                "_meta": {"label": "Bad", "format": "money"},
                "2026Q1": "='SourceData'!C7",
            }
            return rows

        company.workbook_rows = invalid_rows
        with self.assertRaisesRegex(EngineError, "positional cross-sheet"):
            build_workbook(spec, actuals, drivers, company)

    def test_wrong_nine_sheet_order_and_horizon_are_rejected(self):
        spec, actuals, drivers, company = synthetic_project()
        spec["workbook"]["sheets"].reverse()
        with self.assertRaisesRegex(EngineError, "agreed order"):
            build_workbook(spec, actuals, drivers, company)
        spec, actuals, drivers, company = synthetic_project()
        spec["periods"]["forecast_quarters"] = spec["periods"]["forecast_quarters"][:-1]
        with self.assertRaisesRegex(EngineError, "exactly eight forecast"):
            build_workbook(spec, actuals, drivers, company)


if __name__ == "__main__":
    unittest.main()
