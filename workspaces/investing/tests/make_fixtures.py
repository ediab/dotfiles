#!/usr/bin/env python3
"""Generate disposable synthetic Excel fixtures for the investing toolset.

Fixtures are deliberately synthetic and contain no real financial data. They are
written to a disposable directory (default: tests/tmp/fixtures) so they never
enter Git.

Usage:
    .venv/bin/python tests/make_fixtures.py [--out DIR]

Fixture inventory
-----------------
feasibility.xlsx
    Small input -> formula -> output chain plus the workbook features that must
    survive an Excel save (defined name, data validation, conditional format,
    chart, hidden sheet, comment, number formats, freeze panes, column widths,
    tab colour) and one stored error cell.
linked.xlsx
    References feasibility.xlsx through a real OOXML externalLink part, so that
    "open without updating links" can be tested on a disposable workbook.
audit.xlsx
    Deliberately defective: broken #REF! reference, an inconsistent formula
    inside an otherwise uniform row, a failed tie-out, and harmless hardcoded
    assumptions that must not be reported as defects.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from openpyxl import Workbook
from openpyxl.packaging.relationship import Relationship
from openpyxl.workbook.external_link.external import (
    ExternalBook,
    ExternalCell,
    ExternalLink,
    ExternalRow,
    ExternalSheetData,
    ExternalSheetDataSet,
    ExternalSheetNames,
)
from openpyxl.chart import BarChart, Reference
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")
BOLD = Font(bold=True)


def build_feasibility(path: Path) -> None:
    wb = Workbook()

    inputs = wb.active
    inputs.title = "Inputs"
    inputs["A1"] = "Synthetic feasibility fixture - disposable, not financial data"
    inputs["A3"] = "Units sold"
    inputs["B3"] = 1000
    inputs["A4"] = "Price per unit"
    inputs["B4"] = 25.5
    inputs["A5"] = "Net income tie-out (Model!B8)"
    inputs["B5"] = "=Model!B8"

    inputs["B3"].number_format = "#,##0"
    inputs["B4"].number_format = '"$"#,##0.00'
    for ref in ("A3", "A4", "A5"):
        inputs[ref].font = BOLD
    inputs.column_dimensions["A"].width = 32
    inputs.column_dimensions["B"].width = 14
    inputs["B3"].comment = Comment("Input cell: only this should change in the test", "fixture")
    inputs.freeze_panes = "A3"

    dv = DataValidation(type="whole", operator="between", formula1="0", formula2="1000000")
    dv.promptTitle = "Units sold"
    inputs.add_data_validation(dv)
    dv.add(inputs["B3"])

    model = wb.create_sheet("Model")
    model["A1"] = "Model"
    model["A1"].font = BOLD
    model["A3"] = "Revenue"
    model["B3"] = "=UnitsSold*Inputs!$B$4"
    model["A4"] = "Gross profit"
    model["B4"] = "=B3*0.4"
    model["A5"] = "Opex"
    model["B5"] = 1500
    model["A6"] = "EBIT"
    model["B6"] = "=B4-B5"
    model["A7"] = "Tax"
    model["B7"] = "=IF(B6>0,B6*0.25,0)"
    model["A8"] = "Net income"
    model["B8"] = "=B6-B7"
    model["A10"] = "Stored error cell"
    model["B10"] = "=1/0"
    for row in range(3, 9):
        model.cell(row=row, column=2).number_format = "#,##0.00"
    model.column_dimensions["A"].width = 24
    model.column_dimensions["B"].width = 16
    model.freeze_panes = "A3"
    for ref in ("A3", "A4", "A5", "A6", "A7", "A8", "A10"):
        model[ref].font = BOLD
    model.conditional_formatting.add(
        "B6", CellIsRule(operator="lessThan", formula=["0"], fill=PatternFill("solid", fgColor="FFC7CE"))
    )

    chart = BarChart()
    chart.title = "Revenue vs net income"
    chart.add_data(Reference(model, min_col=2, min_row=3, max_row=4), titles_from_data=False)
    model.add_chart(chart, "D3")

    hidden = wb.create_sheet("Hidden")
    hidden["A1"] = "hidden sentinel"
    hidden["A2"] = 4242
    hidden.sheet_state = "hidden"

    wb.create_sheet("Notes")["A1"] = "Unused tab kept so the fixture has three visible sheets"
    wb["Notes"].sheet_properties.tabColor = "00B050"

    wb.defined_names.add(_name("UnitsSold", "Inputs!$B$3"))
    wb.save(path)


def _name(name: str, attr_text: str):
    from openpyxl.workbook.defined_name import DefinedName

    return DefinedName(name, attr_text=attr_text)


def build_linked(path: Path, target_name: str) -> None:
    """Write a workbook whose B2 formula points at target_name via an externalLink part.

    Built with openpyxl's external-link object model rather than hand-written XML:
    Excel rejects a workbook whose externalLink parts do not match its expectations
    (observed: AppleScript `open workbook` fails with error -50).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Link"
    ws["A1"] = "External link fixture - value below comes from another workbook"
    ws["A2"] = "Linked Model!B8"
    ws["B2"] = f"='[{target_name}]Model'!B8"
    ws["A4"] = "Cached value carried in the external link part"
    ws["B4"] = 5100

    link = ExternalLink(
        externalBook=ExternalBook(
            sheetNames=ExternalSheetNames(sheetName=["Model"]),
            sheetDataSet=ExternalSheetDataSet(
                sheetData=[
                    ExternalSheetData(
                        sheetId=0,
                        refreshError=True,
                        row=[ExternalRow(r=8, cell=[ExternalCell(r="B8", t="n", v="5100")])],
                    )
                ]
            ),
            id="rId1",
        )
    )
    # file_link is a class attribute on ExternalLink, not a constructor argument.
    link.file_link = Relationship(
        Id="rId1", type="externalLinkPath", Target=target_name, TargetMode="External"
    )
    wb._external_links.append(link)
    wb.save(path)


def build_audit(path: Path) -> None:
    """Defective fixture for the audit-xls acceptance check."""
    wb = Workbook()
    ws = wb.active
    ws.title = "P&L"
    ws["A1"] = "Synthetic audit fixture - contains deliberate defects"
    ws["A3"] = "Segment"
    ws["B3"] = "FY24A"
    ws["C3"] = "FY25E"
    ws["A4"] = "Segment A"
    ws["B4"] = 1000
    ws["C4"] = "=B4*1.1"
    ws["A5"] = "Segment B"
    ws["B5"] = 2000
    ws["C5"] = "=B5*1.1"
    ws["A6"] = "Segment C"
    ws["B6"] = 3000
    ws["C6"] = "=B6+500"  # inconsistent with the uniform growth pattern above
    ws["A8"] = "Total revenue"
    ws["B8"] = "=SUM(B4:B6)"
    ws["C8"] = "=SUM(C4:C6)"
    ws["A10"] = "Stated total (supplied assumption)"
    ws["B10"] = 6000
    ws["C10"] = "=B10*1.1"
    ws["A12"] = "Tie-out check (should be zero)"
    ws["B12"] = "=B8-B10"
    ws["C12"] = "=C8-C10*1.05"  # deliberately wrong: fails the tie-out
    ws["A14"] = "Broken reference"
    ws["B14"] = "=#REF!*2"
    ws["A16"] = "Growth assumption"
    ws["B16"] = "=FileMissing!B4"  # unsupported/broken sheet reference

    bs = wb.create_sheet("BS")
    bs["A1"] = "Balance sheet tie-out"
    bs["A3"] = "Total assets"
    bs["B3"] = 5000
    bs["A4"] = "Total liabilities and equity"
    bs["B4"] = 5000
    bs["A6"] = "Check"
    bs["B6"] = "=B3-B4"
    wb.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "tmp" / "fixtures"),
        help="output directory (recreated on each run)",
    )
    args = parser.parse_args()

    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    build_feasibility(out / "feasibility.xlsx")
    build_linked(out / "linked.xlsx", "feasibility.xlsx")
    build_audit(out / "audit.xlsx")
    for f in sorted(out.iterdir()):
        print(f)


if __name__ == "__main__":
    main()
