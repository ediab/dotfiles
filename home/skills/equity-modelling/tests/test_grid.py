"""Unit checks for v2 keyed grids; no Excel installation is required."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from grid import GridError, KeyedReferences, PeriodGrid, labels  # noqa: E402


class PeriodGridTests(unittest.TestCase):
    def test_complete_years_require_four_like_status_quarters(self):
        grid = PeriodGrid(("2025Q1", "2025Q2", "2025Q3", "2025Q4"),
                          ("2026Q1E", "2026Q2E"))
        self.assertEqual(grid.annual_periods, ("FY2025A",))
        self.assertEqual(grid.annual_members("FY2025A"),
                         ("2025Q1", "2025Q2", "2025Q3", "2025Q4"))
        mixed = PeriodGrid(("2026Q1", "2026Q2"), ("2026Q3E", "2026Q4E"))
        self.assertEqual(mixed.annual_periods, ("FY2026E",))
        self.assertEqual(mixed.annual_members("FY2026E"),
                         ("2026Q1", "2026Q2", "2026Q3E", "2026Q4E"))
        with self.assertRaises(GridError):
            grid.annual_members("FY2026E")

    def test_annual_columns_follow_quarters_and_require_complete_fiscal_year(self):
        grid = PeriodGrid(("2024Q1", "2024Q2", "2024Q3", "2024Q4",
                           "2025Q1", "2025Q2", "2025Q3"), ("2025Q4E",))
        self.assertEqual(grid.annual_periods, ("FY2024A", "FY2025E"))
        self.assertEqual(grid.annual_members("FY2025E"),
                         ("2025Q1", "2025Q2", "2025Q3", "2025Q4E"))
        self.assertEqual(grid.annual_columns["FY2024A"], grid.first_column + len(grid.periods))
        self.assertNotIn("FY2024A", grid.columns)
        self.assertIn("FY2024A", grid.display_columns)
        self.assertEqual(grid.display_periods[-2:], ("FY2024A", "FY2025E"))
        self.assertEqual(labels(("2025Q4E", "FY2025E")), ["Q4 2025E", "FY 2025E"])
        incomplete = PeriodGrid(("2025Q1", "2025Q2", "2025Q4"), ())
        self.assertEqual(incomplete.annual_periods, ())

    def test_fiscal_comparison_keys_do_not_depend_on_calendar_dates(self):
        # Fiscal year 2025's Q1 need not be a calendar Q1; keys define comparability.
        grid = PeriodGrid(("2024Q4", "2025Q1", "2025Q2", "2026Q1"), ())
        self.assertEqual(grid.comparable_period("2025Q1", quarters_back=1), "2024Q4")
        self.assertEqual(grid.comparable_period("2026Q1", years_back=1), "2025Q1")
        self.assertIsNone(grid.comparable_period("2025Q1", years_back=1))
        self.assertEqual(grid.comparison_period("2026Q1", years_back=2), "2024Q1")
        self.assertIsNone(grid.comparable_period("2026Q1", years_back=2))

    def test_actual_and_forecast_periods_cannot_be_misclassified_or_duplicated(self):
        with self.assertRaises(GridError):
            PeriodGrid(("2025Q1E",), ())
        with self.assertRaises(GridError):
            PeriodGrid((), ("2025Q1",))
        with self.assertRaises(GridError):
            PeriodGrid(("2025Q1",), ("2025Q1",))
        with self.assertRaises(GridError):
            PeriodGrid(("2025Q1",), ("2025Q1E",))

    def test_keyed_references_use_defined_names_not_cross_sheet_a1(self):
        workbook = Workbook()
        workbook.active.title = "Data - Actuals"
        refs = KeyedReferences(workbook)
        name = refs.bind("revenue:2025Q1", "Data - Actuals", 8, 3)
        self.assertEqual(name, "em_revenue_2025Q1")
        self.assertEqual(KeyedReferences.name("revenue:2025Q1"), "em_revenue_2025Q1")
        self.assertEqual(refs.formula("revenue:2025Q1"), "=em_revenue_2025Q1")
        self.assertIn(name, workbook.defined_names)
        with self.assertRaises(GridError):
            refs.bind("revenue:2025Q1", "Data - Actuals", 9, 3)
        with self.assertRaises(GridError):
            refs.bind("Revenue:2025Q1", "Data - Actuals", 9, 3)
        with self.assertRaises(GridError):
            refs.bind("missing-sheet", "Missing", 1, 1)
        with self.assertRaises(GridError):
            refs.ref("missing")

    def test_heading_labels_are_explicit_actual_or_estimate(self):
        self.assertEqual(labels(["2025Q4", "2026Q1E"]), ["Q4 2025A", "Q1 2026E"])


if __name__ == "__main__":
    unittest.main()
