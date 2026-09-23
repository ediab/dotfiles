"""Isolated contract tests for ``check_full`` cached-formula behavior.

openpyxl cannot persist a formula together with its cached result, so the fixtures below build a
real workbook and then edit the sheet XML to store fake calculation results, including Excel error
values.  No calculator, renderer or VRT-specific rule is involved.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from openpyxl import Workbook  # noqa: E402
from checks import check_fast, check_full  # noqa: E402
from evidence import build_actuals, freeze  # noqa: E402
from pull_fixture import create_source, fact_mappings  # noqa: E402
from engine import build_workbook  # noqa: E402
from nine_sheet_fixture import synthetic_project  # noqa: E402


def _inject_cached_values(workbook_path: Path, cached: dict[str, object]) -> None:
    """Store fake formula results, writing ``#``-prefixed values with the Excel error cell type."""
    with zipfile.ZipFile(workbook_path) as archive:
        names = archive.namelist()
        parts = {name: archive.read(name) for name in names}
    sheet_parts = [name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
    for coordinate, value in cached.items():
        for name in sheet_parts:
            xml = parts[name].decode()
            pattern = re.compile(r'<c r="%s"([^>]*)>(<f>[^<]*</f>)<v></v></c>' % coordinate)

            def replace(match, coordinate=coordinate, value=value):
                attributes = match.group(1)
                if isinstance(value, str) and value.startswith("#"):
                    attributes += ' t="e"'
                return f'<c r="{coordinate}"{attributes}>{match.group(2)}<v>{value}</v></c>'

            xml, replacements = pattern.subn(replace, xml)
            if replacements:
                parts[name] = xml.encode()
                break
        else:
            raise AssertionError(f"expected one formula cell {coordinate!r}")
    with zipfile.ZipFile(workbook_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(name, parts[name])


class CheckFullCachedFormulaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _write_project(self, build, *, include_evidence: bool = True) -> Path:
        output = self.project / "Book.xlsx"
        workbook = Workbook()
        workbook.active.title = "SourceData"
        build(workbook.create_sheet("RegionalModel"))
        workbook.save(output)
        spec = {"workbook": {"filename": "Book.xlsx", "sheets": ["SourceData", "RegionalModel"]}}
        if include_evidence:
            source_spec, facts = create_source(self.project / "pull" / "data", "TST")
            spec.update(source_spec)
            spec["workbook"] = {"filename": "Book.xlsx", "sheets": ["SourceData", "RegionalModel"]}
            (self.project / "fact_map.json").write_text(json.dumps({"schema_version": 1,
                "ticker": "TST", "facts": facts[:1]}))
            freeze(build_actuals(fact_mappings(facts[:1]), spec, ["2026Q2"]),
                   self.project / "evidence")
        (self.project / "model_spec.json").write_text(json.dumps(spec))
        return output

    def _cache_warnings(self, report) -> list[str]:
        return [warning for warning in report.warnings if "cached calculation results" in warning]

    def test_missing_cached_results_warns_without_failing(self):
        def build(sheet):
            sheet["A1"] = "=1+1"
            sheet["A2"] = "=A1+1"

        self._write_project(build)
        report = check_full(self.project)
        self.assertTrue(report.ok, report.failures)
        self.assertEqual(len(self._cache_warnings(report)), 1)

    def test_cached_excel_error_fails_closed(self):
        def build(sheet):
            sheet["A1"] = "=1+1"
            sheet["A2"] = "=1/0"

        output = self._write_project(build)
        _inject_cached_values(output, {"A1": "2", "A2": "#DIV/0!"})
        report = check_full(self.project)
        self.assertFalse(report.ok)
        self.assertIn("RegionalModel!A2 recalculates to #DIV/0!", report.failures)

    def test_evaluated_workbook_without_errors_passes_without_cache_warning(self):
        def build(sheet):
            sheet["A1"] = "=1+1"
            sheet["A2"] = "=A1*2"

        output = self._write_project(build)
        _inject_cached_values(output, {"A1": "2", "A2": "4"})
        report = check_full(self.project)
        self.assertTrue(report.ok, report.failures)
        self.assertEqual(self._cache_warnings(report), [])

    def test_formula_free_workbook_is_not_warned(self):
        def build(sheet):
            sheet["A1"] = 5

        self._write_project(build)
        report = check_full(self.project)
        self.assertTrue(report.ok, report.failures)
        self.assertEqual(self._cache_warnings(report), [])

    def test_existing_workbook_without_mandatory_evidence_fails_closed(self):
        self._write_project(lambda sheet: sheet.__setitem__("A1", 5), include_evidence=False)
        report = check_full(self.project)
        self.assertFalse(report.ok)
        self.assertIn("mandatory frozen evidence is missing: evidence/actuals.csv", report.failures)
        self.assertIn("mandatory frozen evidence is missing: fact_map.json", report.failures)


class NineSheetInactiveForecastChecks(unittest.TestCase):
    def test_proposed_inputs_remain_visible_but_forecast_output_tampering_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            spec, actuals, drivers, module = synthetic_project()
            spec["workbook"]["filename"] = "Thin.xlsx"
            (project / "model_spec.json").write_text(json.dumps(spec))
            output = project / "Thin.xlsx"
            workbook = build_workbook(spec, actuals, drivers, module).workbook
            workbook.save(output)
            self.assertEqual(workbook["Inputs"]["D7"].value, 0.1)
            self.assertTrue(check_fast(project).ok)
            workbook["Operating Model"]["E8"] = 999
            workbook.save(output)
            report = check_fast(project)
            self.assertIn("Operating Model!E8 activates an unapproved forecast", report.failures)


if __name__ == "__main__":
    unittest.main()
