"""Unit tests for excel_gate pure logic (no Excel required).

Run: python3 -m unittest home/skills/excel/tests/test_excel_gate.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GATE_PATH = os.path.join(_HERE, "..", "scripts", "excel_gate.py")

_spec = importlib.util.spec_from_file_location("excel_gate", _GATE_PATH)
gate = importlib.util.module_from_spec(_spec)
sys.modules["excel_gate"] = gate
_spec.loader.exec_module(gate)


class TestSplitTarget(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(gate.split_target("Sheet1!B5"), ("Sheet1", "B5"))

    def test_range_rejected_for_targets(self):
        with self.assertRaises(gate.GateError):
            gate.split_target("Sheet1!A1:A5")

    def test_range_allowed_for_renders(self):
        self.assertEqual(gate.split_target("Sheet1!A1:A5", allow_range=True), ("Sheet1", "A1:A5"))

    def test_quoted_sheet(self):
        self.assertEqual(gate.split_target("'My Sheet'!A1"), ("My Sheet", "A1"))

    def test_range_ref(self):
        self.assertEqual(gate.split_target("Data!A1:M40", allow_range=True), ("Data", "A1:M40"))

    def test_missing_bang(self):
        with self.assertRaises(gate.GateError):
            gate.split_target("Sheet1B5")

    def test_empty_sheet(self):
        with self.assertRaises(gate.GateError):
            gate.split_target("!A1")

    def test_empty_ref(self):
        with self.assertRaises(gate.GateError):
            gate.split_target("Sheet!")


def _make_error_workbook() -> str:
    """Workbook with error-typed cells (#SPILL!, #CALC!, #REF!) plus a plain
    string that merely looks like an error, saved into a temp dir."""
    import openpyxl

    path = os.path.join(tempfile.mkdtemp(), "errors.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"] = "#SPILL!"
    ws["A1"].data_type = "e"
    ws["B2"] = "#CALC!"
    ws["B2"].data_type = "e"
    ws["C3"] = "#REF!"
    ws["C3"].data_type = "e"
    # plain string that looks like an error but is not error-typed
    ws["D4"] = "#SPILL!"
    wb.save(path)
    return path


class TestErrorDetection(unittest.TestCase):
    def test_modern_and_classic_errors_detected_with_addresses(self):
        _, errors = gate.read_cached_state(_make_error_workbook(), [])
        self.assertEqual(
            errors,
            {"S!A1!#SPILL!", "S!B2!#CALC!", "S!C3!#REF!"},
        )

    def test_plain_string_error_lookalike_not_detected(self):
        _, errors = gate.read_cached_state(_make_error_workbook(), [])
        self.assertNotIn("S!D4!#SPILL!", errors)

    def test_extract_error_kinds_aggregates_modern_errors(self):
        kinds = gate.extract_error_kinds(
            {"S!A1!#SPILL!", "S!B2!#SPILL!", "S!C3!#CALC!", "S!C4!#REF!"})
        self.assertEqual(kinds, {"#SPILL!": 2, "#CALC!": 1, "#REF!": 1})


class TestPackageInventory(unittest.TestCase):
    def _make_workbook(self, **features) -> str:
        import openpyxl
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.formatting.rule import CellIsRule
        from openpyxl.comments import Comment
        from openpyxl.chart import BarChart, Reference

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"
        ws["A1"] = 1
        ws["A2"] = 2
        ws["A3"] = "=SUM(A1:A2)"
        if features.get("table"):
            from openpyxl.worksheet.table import Table, TableStyleInfo
            ws["C1"] = "col"
            ws["C2"] = "x"
            t = Table(displayName="Tbl1", ref="C1:C2")
            t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1")
            ws.add_table(t)
        if features.get("chart"):
            chart = BarChart()
            chart.add_data(Reference(ws, min_col=1, min_row=1, max_row=2))
            ws.add_chart(chart, "E5")
        if features.get("validation"):
            dv = DataValidation(type="whole", operator="between", formula1=1, formula2=10)
            ws.add_data_validation(dv)
            dv.add("A1:A2")
        if features.get("cond_format"):
            ws.conditional_formatting.add(
                "A1:A2", CellIsRule(operator="greaterThan", formula=["0"]))
        if features.get("comment"):
            ws["A1"].comment = Comment("source: example", "gate")
        if features.get("defined_name"):
            wb.defined_names["MyName"] = openpyxl.workbook.defined_name.DefinedName(
                "MyName", attr_text="Data!$A$1:$A$2")
        path = os.path.join(tempfile.mkdtemp(), "inv.xlsx")
        wb.save(path)
        return path

    def test_plain_workbook_inventory(self):
        path = self._make_workbook()
        inv = gate.package_inventory(path)
        self.assertEqual(inv["charts"], [])
        self.assertEqual(inv["tables"], [])
        self.assertEqual(inv["vba"], [])
        self.assertEqual(inv["defined_names"], [])

    def test_featureful_workbook_inventory(self):
        path = self._make_workbook(
            table=True, chart=True, validation=True,
            cond_format=True, comment=True, defined_name=True)
        inv = gate.package_inventory(path)
        self.assertEqual(len(inv["charts"]), 1)
        self.assertEqual(len(inv["tables"]), 1)
        self.assertIn("Data", inv["data_validations"])
        self.assertIn("Data", inv["conditional_formats"])
        self.assertIn("MyName", inv["defined_names"])
        self.assertTrue(inv["comments"], "comment part expected in package inventory")

    def test_inventory_lost_detects_missing_chart(self):
        rich = self._make_workbook(chart=True, table=True)
        plain = self._make_workbook()
        lost = gate.inventory_lost(gate.package_inventory(rich), gate.package_inventory(plain))
        self.assertTrue(any(f.startswith("charts:") for f in lost))
        self.assertTrue(any(f.startswith("tables:") for f in lost))
        self.assertTrue(any(f.startswith("drawings:") for f in lost))

    def test_inventory_lost_empty_when_stable(self):
        a = self._make_workbook(chart=True)
        b = self._make_workbook(chart=True)
        self.assertEqual(gate.inventory_lost(gate.package_inventory(a), gate.package_inventory(b)), [])


class TestComputeErrorDelta(unittest.TestCase):
    def test_no_changes(self):
        cells = {"S!A1!#REF!"}
        added, removed = gate.compute_error_delta(cells, cells)
        self.assertEqual((added, removed), ([], []))

    def test_added_and_removed(self):
        added, removed = gate.compute_error_delta(
            {"S!B2!#DIV/0!"}, {"S!A1!#REF!"})
        self.assertEqual(added, ["S!B2!#DIV/0!"])
        self.assertEqual(removed, ["S!A1!#REF!"])

    def test_moved_error_is_added_and_removed(self):
        # Same error type, different cell: must not net out as "no change".
        added, removed = gate.compute_error_delta(
            {"S!B2!#DIV/0!"}, {"S!A1!#DIV/0!"})
        self.assertEqual(added, ["S!B2!#DIV/0!"])
        self.assertEqual(removed, ["S!A1!#DIV/0!"])

    def test_extract_error_kinds(self):
        kinds = gate.extract_error_kinds({"S!A1!#REF!", "S!B2!#REF!", "S!C3!#N/A"})
        self.assertEqual(kinds, {"#REF!": 2, "#N/A": 1})

    def test_modern_error_new_cell_is_added(self):
        # A fresh #SPILL! in B2 (not present at baseline) must surface as added,
        # not net out against an unrelated classic error.
        added, removed = gate.compute_error_delta(
            {"S!B2!#SPILL!"}, {"S!A1!#REF!"})
        self.assertEqual(added, ["S!B2!#SPILL!"])
        self.assertEqual(removed, ["S!A1!#REF!"])


class TestInventoryLostCounts(unittest.TestCase):
    def test_renumbered_part_not_lost(self):
        base = {"charts": ["xl/charts/chart1.xml"], "defined_names": ["A"]}
        final = {"charts": ["xl/charts/chart2.xml"], "defined_names": ["A"]}
        self.assertEqual(gate.inventory_lost(base, final), [])

    def test_count_drop_reported(self):
        base = {"charts": ["xl/charts/chart1.xml", "xl/charts/chart2.xml"]}
        final = {"charts": ["xl/charts/chart1.xml"]}
        lost = gate.inventory_lost(base, final)
        self.assertEqual(lost, ["charts: lost ['count 2 -> 1']"])

    def test_defined_name_removed(self):
        base = {"defined_names": ["A", "B"]}
        final = {"defined_names": ["A"]}
        lost = gate.inventory_lost(base, final)
        self.assertEqual(len(lost), 1)
        self.assertIn("B", lost[0])


class TestReadCachedState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import openpyxl
        path = os.path.join(tempfile.mkdtemp(), "state.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"
        ws["A1"] = 2
        ws["A2"] = "=A1*10"
        ws["B1"] = "plain"
        wb.save(path)
        cls.path = path

    def test_formula_and_cached_value(self):
        state, errors = gate.read_cached_state(self.path, ["Data!A2", "Data!B1"])
        self.assertEqual(state["Data!A2"]["formula"], "=A1*10")
        # no Excel recalculation happened, so no cached value yet
        self.assertIsNone(state["Data!A2"]["value"])
        self.assertEqual(state["Data!B1"]["value"], "plain")
        self.assertEqual(errors, set())

    def test_missing_target_sheet(self):
        with self.assertRaises(gate.GateError):
            gate.read_cached_state(self.path, ["Nope!A1"])

    def test_error_cells_detected_with_addresses(self):
        import openpyxl
        path = os.path.join(tempfile.mkdtemp(), "errors.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "S"
        ws["A1"] = 1
        ws["A2"] = "=1/0"
        ws["A3"] = "text"
        wb.save(path)
        _, errors = gate.read_cached_state(path, [])
        # without recalculation no cached error-typed cells exist yet
        self.assertEqual(errors, set())


class TestFormatReport(unittest.TestCase):
    def test_ok_true(self):
        self.assertEqual(gate.format_report(True, stage="x"), {"ok": True, "stage": "x"})

    def test_ok_false(self):
        report = gate.format_report(False, error="boom")
        self.assertFalse(report["ok"])
        self.assertEqual(report["error"], "boom")


class TestGatePreflightRejections(unittest.TestCase):
    def test_unsupported_extension_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "model.xlsb")
            with open(path, "w") as f:
                f.write("not really")
            report = gate.run_gate(path, None, [], [], tmp, 5)
            self.assertFalse(report["ok"])
            self.assertEqual(report["stage"], "preflight")
            self.assertIn("unsupported", report["error"])

    def test_missing_draft_rejected(self):
        report = gate.run_gate("/nonexistent/nope.xlsx", None, [], [], None, 5)
        self.assertFalse(report["ok"])
        self.assertEqual(report["stage"], "preflight")

    def test_missing_baseline_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ok.xlsx")
            import openpyxl
            wb = openpyxl.Workbook()
            wb.active["A1"] = 1
            wb.save(path)
            report = gate.run_gate(path, "/nonexistent/base.xlsx", [], [], tmp, 5)
            self.assertFalse(report["ok"])
            self.assertEqual(report["stage"], "preflight")

    def test_non_zip_package_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fake.xlsx")
            with open(path, "w") as f:
                f.write("this is not a zip")
            report = gate.run_gate(path, None, [], [], tmp, 5)
            self.assertFalse(report["ok"])
            self.assertEqual(report["stage"], "preflight")
            self.assertIn("not a valid", report["error"])

    def test_range_target_rejected_before_automation(self):
        with tempfile.TemporaryDirectory() as tmp:
            import openpyxl
            path = os.path.join(tmp, "ok.xlsx")
            wb = openpyxl.Workbook()
            wb.active["A1"] = 1
            wb.save(path)
            report = gate.run_gate(path, None, ["Data!A1:A5"], [], tmp, 5)
            self.assertFalse(report["ok"])
            self.assertEqual(report["stage"], "preflight")
            self.assertIn("single cell", report["error"])


if __name__ == "__main__":
    unittest.main()
