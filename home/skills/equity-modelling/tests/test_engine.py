"""Contract tests for the Stage 3 generic engine."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from engine import EngineError, active_driver_values, approval_digest, build_workbook  # noqa: E402


class StubCompany:
    def __init__(self):
        self.received = None

    def workbook_rows(self, actuals, drivers, periods):
        self.received = actuals, drivers, periods
        row = {"revenue": {"2026Q3E": "=em_actual_revenue_2026Q1"}}
        return {"RegionalModel": row, "Earnings": {"adjusted_eps": row["revenue"]},
                "Scenarios": {"base": row["revenue"]}}


class RawReferenceCompany(StubCompany):
    def workbook_rows(self, actuals, drivers, periods):
        row = {"revenue": {"2026Q3E": "='SourceData'!$C$7"}}
        return {"RegionalModel": row, "Earnings": {}, "Scenarios": {}}


class AnalysisCompany:
    def workbook_rows(self, actuals, drivers, periods):
        return {"Analysis": {"revenue": {"2026Q1": "=em_actual_revenue_2026Q1"}}}


class UnsortedLegacyCompany:
    def workbook_rows(self, actuals, drivers, periods):
        return {"Analysis": {
            "zebra_metric": {"2026Q1": "=em_actual_revenue_2026Q1"},
            "alpha_metric": {"2026Q1": "=em_actual_revenue_2026Q1"},
        }}


SPEC = {
    "periods": {
        "historical_quarters": ["2026Q1", "2026Q2"],
        "forecast_quarters": ["2026Q3", "2026Q4"],
    },
    "price": {"value": 123.45, "date": "2026-09-18"},
    "forecast_gate": {"approved": True},
    "workbook": {"sheets": ["SourceData", "Drivers", "RegionalModel", "Earnings", "Scenarios"]},
}
ACTUALS = [
    {"metric": "revenue", "period": "2026Q1", "value": "100"},
    {"metric": "revenue", "period": "2026Q2", "value": "110"},
]
DRIVER = {"driver_id": "revenue_growth", "driver_name": "Revenue growth", "status": "proposed",
          "2026Q3": "0.4", "2026Q4": "0.3"}


class EngineTests(unittest.TestCase):
    def test_proposed_drivers_stay_blank_but_actuals_and_keyed_refs_are_bound(self):
        company = StubCompany()
        context = build_workbook(SPEC, ACTUALS, [DRIVER], company)
        self.assertEqual(context.active_drivers["revenue_growth"],
                         {"2026Q3E": None, "2026Q4E": None})
        self.assertEqual(company.received[0]["revenue"]["2026Q2"], 110.0)
        self.assertEqual(context.references.formula("actual.revenue.2026Q1"),
                         "=em_actual_revenue_2026Q1")
        self.assertIn("em_driver_revenue_growth_2026Q3E", context.workbook.defined_names)
        self.assertEqual(context.references.formula("benchmark.price_dated"), "=em_benchmark_price_dated")
        self.assertEqual(context.workbook["SourceData"]["E8"].value, 123.45)
        self.assertEqual(context.workbook["Drivers"]["D7"].value, None)
        self.assertIsNone(context.workbook["RegionalModel"]["E7"].value)
        self.assertEqual(context.references.formula("model.RegionalModel.revenue.2026Q3E"),
                         "=em_model_RegionalModel_revenue_2026Q3E")

    def test_approved_batch_requires_its_exact_manifest(self):
        approved = dict(DRIVER, status="approved", approval_id="APR-1")
        digest = approval_digest([
            ("revenue_growth", "2026Q3", 0.4),
            ("revenue_growth", "2026Q4", 0.3),
        ])
        manifest = {"approvals": {"APR-1": {"sha256": digest}}}
        values = active_driver_values([approved], ("2026Q3E", "2026Q4E"), manifest,
                                      forecast_gate_approved=True)
        self.assertEqual(values["revenue_growth"]["2026Q3E"], 0.4)
        context = build_workbook(SPEC, ACTUALS, [approved], StubCompany(), manifest)
        self.assertEqual(context.workbook["RegionalModel"]["E7"].value,
                         "=em_actual_revenue_2026Q1")
        changed = dict(approved, **{"2026Q4": "0.31"})
        with self.assertRaisesRegex(EngineError, "manifest hash"):
            active_driver_values([changed], ("2026Q3E", "2026Q4E"), manifest,
                                 forecast_gate_approved=True)

    def test_gate_true_with_valid_manifest_activates_forecast(self):
        approved = dict(DRIVER, status="approved", approval_id="APR-1")
        manifest = {"approvals": {"APR-1": {"sha256": approval_digest([
            ("revenue_growth", "2026Q3", 0.4),
            ("revenue_growth", "2026Q4", 0.3),
        ])}}}
        context = build_workbook(SPEC, ACTUALS, [approved], StubCompany(), manifest)
        self.assertEqual(context.active_drivers["revenue_growth"],
                         {"2026Q3E": 0.4, "2026Q4E": 0.3})
        self.assertEqual(context.workbook["Drivers"]["F7"].value, 0.4)
        self.assertEqual(context.workbook["Drivers"]["G7"].value, 0.3)
        self.assertEqual(context.workbook["RegionalModel"]["E7"].value,
                         "=em_actual_revenue_2026Q1")

    def test_closed_gate_blocks_approved_inputs_despite_valid_manifest(self):
        approved = dict(DRIVER, status="approved", approval_id="APR-1")
        manifest = {"approvals": {"APR-1": {"sha256": approval_digest([
            ("revenue_growth", "2026Q3", 0.4),
            ("revenue_growth", "2026Q4", 0.3),
        ])}}}
        closed = dict(SPEC, forecast_gate={"approved": False})
        with self.assertRaisesRegex(EngineError, "forecast_gate.approved is false"):
            build_workbook(closed, ACTUALS, [approved], StubCompany(), manifest)
        with self.assertRaisesRegex(EngineError, "forecast_gate.approved is false"):
            active_driver_values([approved], ("2026Q3E", "2026Q4E"), manifest,
                                 forecast_gate_approved=False)

    def test_activation_requires_a_declared_forecast_gate(self):
        approved = dict(DRIVER, status="approved", approval_id="APR-1")
        manifest = {"approvals": {"APR-1": {"sha256": approval_digest([
            ("revenue_growth", "2026Q3", 0.4),
            ("revenue_growth", "2026Q4", 0.3),
        ])}}}
        undeclared = {key: value for key, value in SPEC.items() if key != "forecast_gate"}
        with self.assertRaisesRegex(EngineError, "must declare forecast_gate.approved"):
            build_workbook(undeclared, ACTUALS, [approved], StubCompany(), manifest)
        with self.assertRaisesRegex(EngineError, "must declare forecast_gate.approved"):
            active_driver_values([approved], ("2026Q3E", "2026Q4E"), manifest)

    def test_declared_forecast_gate_must_be_an_explicit_boolean(self):
        for gate in ("approved", {"approved": "yes"}, {"approved": 1}):
            with self.assertRaises(EngineError):
                build_workbook(dict(SPEC, forecast_gate=gate), ACTUALS, [DRIVER], StubCompany())

    def test_partial_approval_fails_closed(self):
        approved = dict(DRIVER, status="approved", approval_id="APR-1")
        with self.assertRaisesRegex(EngineError, "partial forecast approval"):
            active_driver_values([approved, dict(DRIVER, driver_id="margin")],
                                 ("2026Q3E", "2026Q4E"), {"APR-1": "0" * 64})

    def test_module_cannot_emit_positional_cross_sheet_formula(self):
        with self.assertRaisesRegex(EngineError, "positional cross-sheet"):
            build_workbook(SPEC, ACTUALS, [DRIVER], RawReferenceCompany())

    def test_declared_sheet_contract_has_no_fixed_company_sheet_names(self):
        spec = dict(SPEC, workbook={"sheets": ["SourceData", "Drivers", "Analysis"]})
        context = build_workbook(spec, ACTUALS, [DRIVER], AnalysisCompany())
        self.assertEqual(context.workbook.sheetnames, ["SourceData", "Drivers", "Analysis"])
        self.assertEqual(context.workbook["Analysis"]["C7"].value, "=em_actual_revenue_2026Q1")

    def test_legacy_company_rows_keep_historical_alphabetical_metric_order(self):
        spec = dict(SPEC, workbook={"sheets": ["SourceData", "Drivers", "Analysis"]})
        workbook = build_workbook(spec, ACTUALS, [DRIVER], UnsortedLegacyCompany()).workbook
        self.assertEqual(workbook["Analysis"]["B7"].value, "Alpha Metric")
        self.assertEqual(workbook["Analysis"]["B8"].value, "Zebra Metric")

    def test_company_rows_must_exactly_cover_declared_company_sheets(self):
        spec = dict(SPEC, workbook={"sheets": ["SourceData", "Drivers", "Analysis"]})
        with self.assertRaisesRegex(EngineError, "exactly match"):
            build_workbook(spec, ACTUALS, [DRIVER], StubCompany())


if __name__ == "__main__":
    unittest.main()
