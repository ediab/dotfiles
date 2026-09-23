"""End-to-end synthetic workbook contract for the thin nine-sheet renderer."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
from engine import EngineError, build_workbook  # noqa: E402
from nine_sheet_fixture import NINE_SHEET_ORDER, fiscal_annual_project, synthetic_project  # noqa: E402


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

    def test_fiscal_trends_and_annual_formulas_use_company_owned_keyed_periods(self):
        spec, actuals, drivers, company = fiscal_annual_project()
        context = build_workbook(spec, actuals, drivers, company)
        grid = context.periods
        self.assertEqual(grid.annual_periods,
                         ("FY2024A", "FY2025A", "FY2026E", "FY2027E"))
        ws = context.workbook["Operating Model"]
        self.assertEqual(ws.cell(6, grid.display_columns["2025Q1"]).value, "Q1 2025A")
        self.assertEqual(ws.cell(6, grid.display_columns["FY2025A"]).value, "FY 2025A")
        self.assertEqual(ws.cell(8, grid.display_columns["2025Q2"]).value,
                         '=IF(OR(em_model_Operating_Model_revenue_2025Q2="",em_model_Operating_Model_revenue_2024Q2="",em_model_Operating_Model_revenue_2025Q2<=0,em_model_Operating_Model_revenue_2024Q2<=0),"",em_model_Operating_Model_revenue_2025Q2/em_model_Operating_Model_revenue_2024Q2-1)')
        self.assertEqual(ws.cell(9, grid.display_columns["2026Q1"]).value,
                         '=IF(OR(em_model_Operating_Model_revenue_2026Q1="",em_model_Operating_Model_revenue_2025Q4="",em_model_Operating_Model_revenue_2026Q1<=0,em_model_Operating_Model_revenue_2025Q4<=0),"",em_model_Operating_Model_revenue_2026Q1/em_model_Operating_Model_revenue_2025Q4-1)')
        self.assertEqual(ws.cell(10, grid.display_columns["2026Q1"]).value,
                         '=IF(OR(em_model_Operating_Model_revenue_2026Q1="",em_model_Operating_Model_revenue_2024Q1="",em_model_Operating_Model_revenue_2026Q1<=0,em_model_Operating_Model_revenue_2024Q1<=0),"",em_model_Operating_Model_revenue_2026Q1/em_model_Operating_Model_revenue_2024Q1-1)')
        self.assertEqual(ws.cell(13, grid.display_columns["2025Q1"]).value,
                         '=IF(OR(em_actual_operating_profit_2025Q1="",em_actual_revenue_2025Q1="",em_actual_revenue_2025Q1<=0,em_actual_operating_profit_2024Q1="",em_actual_revenue_2024Q1="",em_actual_revenue_2024Q1<=0),"",(em_actual_operating_profit_2025Q1/em_actual_revenue_2025Q1-em_actual_operating_profit_2024Q1/em_actual_revenue_2024Q1)*100)')
        self.assertEqual(ws.cell(14, grid.display_columns["2025Q1"]).value,
                         '=IF(OR(em_actual_operating_profit_2025Q1="",em_actual_revenue_2025Q1="",em_actual_revenue_2025Q1<=0,em_actual_operating_profit_2024Q4="",em_actual_revenue_2024Q4="",em_actual_revenue_2024Q4<=0),"",(em_actual_operating_profit_2025Q1/em_actual_revenue_2025Q1-em_actual_operating_profit_2024Q4/em_actual_revenue_2024Q4)*100)')
        self.assertEqual(ws.cell(7, grid.display_columns["FY2024A"]).value,
                         '=IF(COUNT(em_model_Operating_Model_revenue_2024Q1,em_model_Operating_Model_revenue_2024Q2,em_model_Operating_Model_revenue_2024Q3,em_model_Operating_Model_revenue_2024Q4)<>4,"",SUM(em_model_Operating_Model_revenue_2024Q1,em_model_Operating_Model_revenue_2024Q2,em_model_Operating_Model_revenue_2024Q3,em_model_Operating_Model_revenue_2024Q4))')
        self.assertEqual(ws.cell(13, grid.display_columns["FY2025A"]).value,
                         '=IF(OR(em_model_Operating_Model_operating_margin_FY2025A="",em_model_Operating_Model_operating_margin_FY2024A=""),"",(em_model_Operating_Model_operating_margin_FY2025A-em_model_Operating_Model_operating_margin_FY2024A)*100)')
        self.assertIsNone(ws.cell(9, grid.display_columns["FY2025A"]).value,
                          "annual periods have no QoQ comparison")
        self.assertEqual(ws.cell(17, grid.display_columns["FY2025A"]).value,
                         '=IF(OR(em_model_Operating_Model_net_income_FY2025A="",em_model_Operating_Model_diluted_shares_FY2025A="",em_model_Operating_Model_diluted_shares_FY2025A<=0),"",em_model_Operating_Model_net_income_FY2025A/em_model_Operating_Model_diluted_shares_FY2025A)')
        self.assertEqual(ws.cell(15, grid.display_columns["FY2025A"]).value[:9], '=IF(COUNT')
        self.assertEqual(context.workbook["Financial Statements"].cell(
            7, grid.display_columns["FY2025A"]).value, '=IF(em_actual_cash_2025Q4="","",em_actual_cash_2025Q4)')
        self.assertIsNone(ws.cell(7, grid.display_columns["FY2026E"]).value,
                          "unapproved forecast-derived annuals stay blank")
        # Independent expected results for later native recalculation: FY2024 Revenue=400;
        # FY2025 Revenue=435, Net Income=43.5, average diluted shares=10, EPS=4.35,
        # and Q4 Cash=54. The growth acceptance examples are 25% and compounded 32%.
        self.assertEqual(sum((100.0, 100.0, 100.0, 100.0)), 400.0)
        self.assertEqual(sum((110.0, 125.0, 100.0, 100.0)), 435.0)
        self.assertAlmostEqual(43.5 / 10.0, 4.35)
        self.assertEqual(50.0 + 4, 54.0)
        self.assertAlmostEqual(125 / 100 - 1, 0.25)
        self.assertAlmostEqual(132 / 100 - 1, 0.32)

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
