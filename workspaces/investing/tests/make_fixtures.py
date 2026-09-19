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
data_tables.xlsx
    Three sheets with two injected <dataTable> blocks on one of them, so the
    per-sheet sensitivity-table count cannot be satisfied by a workbook-wide
    count reported per sheet.
three_statement.xlsx
    A small linked three-statement model (Assumptions / IS / BS / CF) that
    balances and ties its cash, so a changed operating driver can be traced
    through the income statement, balance sheet and cash flow.
dcf.xlsx
    A five-year unlevered DCF with known inputs (mid-year convention, perpetuity
    terminal value, net-debt bridge, diluted shares) whose arithmetic can be
    recomputed independently.
comps.xlsx
    A five-peer comparables table with declared units and fiscal periods,
    including a peer with negative EBITDA/earnings and peers whose period and
    units differ, plus a ratios-only statistics block.
scenario.xlsx
    A switched base/bull/bear model plus a growth x margin sensitivity grid. The
    grid cells recompute the same driver arithmetic in closed form, so they are a
    cross-check of that arithmetic, NOT a recapture of the model's linkages - the
    test asserts the distinction and separately proves that a broken model
    linkage is detected.
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
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


# Marks the one worksheet that receives injected data tables, so the part is
# found by content rather than by relying on worksheet part ordering.
DATA_TABLE_MARKER = "DATA-TABLE-MARKER"
DATA_TABLE_SHEET = "Sensitivity"
DATA_TABLE_ROWS = 2

# A data-table formula as Excel stores it: the `<dataTable>` element lives inside
# the formula. openpyxl cannot author these, so they are injected into the saved
# part. The audit counts the element name, so the surrounding ref/r1/r2 only need
# to be well-formed.
_DATA_TABLE_ROW = (
    '<row r="{row}"><c r="A{row}" t="str"><v>sensitivity</v></c>'
    '<c r="B{row}"><f t="dataTable" ref="B{row}:C{row}" dt2D="1" dtr="0" r1="A1" r2="B1">'
    '<dataTable/></f></c></row>'
)


def build_data_tables(path: Path) -> None:
    """Three sheets, two injected data tables on one of them.

    Excel's `calculate full` does not refresh data-table caches unless asked, and
    the audit must account for sensitivity tables per sheet. A workbook-wide count
    reported per sheet would multiply by the sheet count, so the fixture has two
    more sheets than tables.
    """
    wb = Workbook()
    wb.active.title = "Summary"
    wb["Summary"]["A1"] = "Sensitivity tables live on the Sensitivity sheet"
    wb.create_sheet(DATA_TABLE_SHEET)["A1"] = DATA_TABLE_MARKER
    wb.create_sheet("Notes")["A1"] = "A third sheet, so a workbook-wide count is obvious"
    wb.save(path)

    injected = "".join(_DATA_TABLE_ROW.format(row=20 + i) for i in range(DATA_TABLE_ROWS))
    with zipfile.ZipFile(path) as source:
        members = [(item, source.read(item.filename)) for item in source.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for item, data in members:
            if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                if DATA_TABLE_MARKER in text:
                    text = text.replace("</sheetData>", injected + "</sheetData>", 1)
                    data = text.encode("utf-8")
            target.writestr(item, data)


def build_three_statement(path: Path) -> None:
    """A small linked 3-statement model that balances and ties its cash.

    Column B = FY0 actuals (constants), C = FY1, D = FY2 (formulas). The model is
    built so the identity holds by construction: every non-cash balance-sheet
    movement appears on the cash flow statement, so assets - L&E = 0 and BS cash
    - CF ending cash = 0 in both forecast years.
    """
    wb = Workbook()

    a = wb.active
    a.title = "Assumptions"
    a["A1"] = "Synthetic three-statement fixture - disposable, not financial data"
    a["A3"] = "Driver"
    a["B3"] = "FY0A"
    a["C3"] = "FY1E"
    a["D3"] = "FY2E"
    rows = [
        ("Revenue growth", None, 0.08, 0.10),
        ("Gross margin", 0.40, 0.40, 0.41),
        ("S&M % of revenue", 0.10, 0.10, 0.105),
        ("G&A % of revenue", 0.08, 0.08, 0.08),
        ("D&A % of opening gross PP&E", 0.0625, 0.0625, 0.0625),
        ("Interest rate on opening debt", 0.05, 0.05, 0.05),
        ("Tax rate", 0.25, 0.25, 0.25),
        ("DSO (days)", 50, 50, 50),
        ("DIO (days)", 60, 60, 60),
        ("DPO (days)", 50, 50, 50),
        ("Capex % of revenue", 0.08, 0.08, 0.08),
        ("Current debt repayment", 10, 10, 10),
        ("Long-term debt repayment", 20, 20, 20),
        ("Dividends", 20, 20, 20),
    ]
    for i, (label, fy0, fy1, fy2) in enumerate(rows, start=4):
        a.cell(row=i, column=1, value=label)
        for col, val in ((2, fy0), (3, fy1), (4, fy2)):
            if val is not None:
                a.cell(row=i, column=col, value=val)
    for col, fmt in ((2, "0.000"), (3, "0.000"), (4, "0.000")):
        pass
    a.column_dimensions["A"].width = 32
    for c in "BCD":
        a.column_dimensions[c].width = 12

    is_ = wb.create_sheet("IS")
    is_["A3"] = "Income statement"
    is_lines = [
        ("Revenue", 1000, "=B4*(1+Assumptions!C4)", "=C4*(1+Assumptions!D4)"),
        ("COGS", 600, "=C4*(1-Assumptions!C5)", "=D4*(1-Assumptions!D5)"),
        ("Gross profit", "=B4-B5", "=C4-C5", "=D4-D5"),
        ("S&M", 100, "=C4*Assumptions!C6", "=D4*Assumptions!D6"),
        ("G&A", 80, "=C4*Assumptions!C7", "=D4*Assumptions!D7"),
        ("D&A", 50, "=BS!B8*Assumptions!C8", "=BS!C8*Assumptions!D8"),
        ("EBIT", "=B6-B7-B8-B9", "=C6-C7-C8-C9", "=D6-D7-D8-D9"),
        ("Interest expense", 20, "=(BS!B14+BS!B15)*Assumptions!C9", "=(BS!C14+BS!C15)*Assumptions!D9"),
        ("Pre-tax income", "=B10-B11", "=C10-C11", "=D10-D11"),
        ("Tax", "=MAX(0,B12*Assumptions!B10)", "=MAX(0,C12*Assumptions!C10)", "=MAX(0,D12*Assumptions!D10)"),
        ("Net income", "=B12-B13", "=C12-C13", "=D12-D13"),
    ]
    for i, (label, b, c, d) in enumerate(is_lines, start=4):
        is_.cell(row=i, column=1, value=label)
        is_.cell(row=i, column=2, value=b)
        is_.cell(row=i, column=3, value=c)
        is_.cell(row=i, column=4, value=d)
    is_.column_dimensions["A"].width = 24

    bs = wb.create_sheet("BS")
    bs["A3"] = "Balance sheet"
    bs_lines = [
        ("Cash", 150, "=CF!C17", "=CF!D17"),
        ("Accounts receivable", 137.0, "=IS!C4*Assumptions!C11/365", "=IS!D4*Assumptions!D11/365"),
        ("Inventory", 98.6, "=IS!C5*Assumptions!C12/365", "=IS!D5*Assumptions!D12/365"),
        ("Total current assets", "=SUM(B4:B6)", "=SUM(C4:C6)", "=SUM(D4:D6)"),
        ("PP&E, gross", 800, "=B8+CF!C10", "=C8+CF!D10"),
        ("Accumulated depreciation", 200, "=B9+IS!C9", "=C9+IS!D9"),
        ("PP&E, net", "=B8-B9", "=C8-C9", "=D8-D9"),
        ("Total assets", "=B7+B10", "=C7+C10", "=D7+D10"),
        ("Accounts payable", 82.2, "=IS!C5*Assumptions!C13/365", "=IS!D5*Assumptions!D13/365"),
        ("Current portion of debt", 50, "=B14-Assumptions!C15", "=C14-Assumptions!D15"),
        ("Long-term debt", 150, "=B15-Assumptions!C16", "=C15-Assumptions!D16"),
        ("Total liabilities", "=SUM(B13:B15)", "=SUM(C13:C15)", "=SUM(D13:D15)"),
        ("Common stock", 300, "=B18", "=C18"),
        ("Retained earnings", 403.4, "=B19+IS!C14-Assumptions!C17", "=C19+IS!D14-Assumptions!D17"),
        ("Total equity", "=B18+B19", "=C18+C19", "=D18+D19"),
        ("Total liabilities and equity", "=B16+B20", "=C16+C20", "=D16+D20"),
        ("Check: assets - L&E", "=B11-B21", "=C11-C21", "=D11-D21"),
    ]
    # rows must land on the addresses the formulas reference (4,5,6,7,8,9,10,11,13,14,15,16,18,19,20,21,23)
    targets = [4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 18, 19, 20, 21, 23]
    for row, (label, b, c, d) in zip(targets, bs_lines):
        bs.cell(row=row, column=1, value=label)
        bs.cell(row=row, column=2, value=b)
        bs.cell(row=row, column=3, value=c)
        bs.cell(row=row, column=4, value=d)
    bs.column_dimensions["A"].width = 30

    cf = wb.create_sheet("CF")
    cf["A3"] = "Cash flow"
    cf_lines = [
        ("Net income", 4, "=IS!C14", "=IS!D14"),
        ("D&A", 5, "=IS!C9", "=IS!D9"),
        ("Change in accounts receivable", 6, "=-(BS!C5-BS!B5)", "=-(BS!D5-BS!C5)"),
        ("Change in inventory", 7, "=-(BS!C6-BS!B6)", "=-(BS!D6-BS!C6)"),
        ("Change in accounts payable", 8, "=(BS!C13-BS!B13)", "=(BS!D13-BS!C13)"),
        ("CFO", 9, "=SUM(C4:C8)", "=SUM(D4:D8)"),
        ("Capital expenditure (outflow)", 10, "=IS!C4*Assumptions!C14", "=IS!D4*Assumptions!D14"),
        ("CFI", 11, "=-C10", "=-D10"),
        ("Debt repayment", 12, "=-(Assumptions!C15+Assumptions!C16)", "=-(Assumptions!D15+Assumptions!D16)"),
        ("Dividends", 13, "=-Assumptions!C17", "=-Assumptions!D17"),
        ("CFF", 14, "=C12+C13", "=D12+D13"),
        ("Net change in cash", 15, "=C9+C11+C14", "=D9+D11+D14"),
        ("Opening cash", 16, "=BS!B4", "=BS!C4"),
        ("Ending cash", 17, "=C16+C15", "=D16+D15"),
        ("Check: BS cash - CF ending cash", 19, "=BS!C4-C17", "=BS!D4-D17"),
    ]
    for label, row, c, d in cf_lines:
        cf.cell(row=row, column=1, value=label)
        cf.cell(row=row, column=3, value=c)
        cf.cell(row=row, column=4, value=d)
    cf.column_dimensions["A"].width = 34
    wb.save(path)


def build_dcf(path: Path) -> None:
    """Five-year unlevered DCF with known inputs and a mid-year convention."""
    wb = Workbook()
    ws = wb.active
    ws.title = "DCF"
    ws["A1"] = "Synthetic DCF fixture - disposable, not financial data"
    ws["A3"] = "Inputs (all supplied)"
    inputs = [
        ("WACC", 0.10),
        ("Terminal growth rate", 0.025),
        ("Tax rate", 0.25),
        ("Net debt (as of FY0 end)", 500),
        ("Diluted shares (m)", 100),
        ("Discounting convention", "mid-year"),
    ]
    for i, (label, value) in enumerate(inputs, start=4):
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=value)

    ws["A11"] = "Year"
    for i, year in enumerate(range(1, 6)):
        ws.cell(row=11, column=3 + i, value=year)
    ws["A12"] = "Unlevered FCF (supplied)"
    for i, fcf in enumerate([100, 110, 121, 133.1, 146.41]):
        ws.cell(row=12, column=3 + i, value=fcf)
    ws["A13"] = "Discount period (mid-year)"
    ws["A14"] = "Discount factor"
    ws["A15"] = "PV of FCF"
    for i, col in enumerate("CDEFG"):
        ws[f"{col}13"] = f"={col}11-0.5"
        ws[f"{col}14"] = f"=1/(1+$B$4)^{col}13"
        ws[f"{col}15"] = f"={col}12*{col}14"

    ws["A16"] = "Sum of PV of FCFs"
    ws["B16"] = "=SUM(C15:G15)"
    ws["A18"] = "Terminal value (perpetuity)"
    ws["B18"] = "=G12*(1+$B$5)/($B$4-$B$5)"
    ws["A19"] = "Discount factor, terminal period"
    ws["B19"] = "=1/(1+$B$4)^G13"
    ws["A20"] = "PV of terminal value"
    ws["B20"] = "=B18*B19"
    ws["A21"] = "Enterprise value"
    ws["B21"] = "=B16+B20"
    ws["A22"] = "Terminal value as % of enterprise value"
    ws["B22"] = "=B20/B21"
    ws["A24"] = "Less: net debt"
    ws["B24"] = "=-B7"
    ws["A25"] = "Equity value"
    ws["B25"] = "=B21+B24"
    ws["A26"] = "Implied value per share"
    ws["B26"] = "=B25/B8"
    ws["A28"] = "Check: terminal growth below WACC (1 = true)"
    ws["B28"] = "=IF(B5<B4,1,0)"
    ws.column_dimensions["A"].width = 42
    wb.save(path)


def build_comps(path: Path) -> None:
    """Five-peer comparables table with declared units and periods.

    Comparability is mechanical rather than prose: one declared base period and
    base unit sit at the top, a flag column names why each row is comparable or
    excluded, and the statistics read "comparable-only" columns. Removing the
    exclusion changes the medians, so the test can genuinely fail if the
    safeguard is dropped.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Comps"
    ws["A1"] = "Synthetic comparables fixture - disposable, not financial data"
    ws["A2"] = "All figures supplied. Comparability is decided against the declared base below."
    ws["G2"] = "Base period"
    ws["H2"] = "LTM Jun-26"
    ws["I2"] = "Base units"
    ws["J2"] = "USD m"
    headers = [
        "Company", "Price", "Diluted shares (m)", "Market cap", "Net debt (neg = net cash)",
        "Enterprise value", "Revenue", "EBITDA", "Net income", "Period", "Units",
        "EV/Revenue", "EV/EBITDA", "P/E",
        "Comparable?", "", "EV/Revenue (comparable)", "EV/EBITDA (comparable)", "P/E (comparable)",
    ]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=3, column=i, value=h)
    peers = [
        ("ALPHA", 50, 100, 200, 500, 100, 60, "LTM Jun-26", "USD m"),
        ("BETA", 25, 200, -50, 800, 160, 90, "LTM Jun-26", "USD m"),
        ("GAMMA", 12, 150, 300, 400, -20, -30, "FY25A", "USD m"),
        ("DELTA", 8, 400, 100, 1200, 240, 120, "LTM Jun-26", "USD k"),
        ("EPSILON", 60, 50, 0, 200, 40, 25, "LTM Jun-26", "USD m"),
    ]
    for i, (name, price, shares, net_debt, revenue, ebitda, ni, period, units) in enumerate(peers, start=4):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=price)
        ws.cell(row=i, column=3, value=shares)
        ws.cell(row=i, column=4, value=f"=B{i}*C{i}")
        ws.cell(row=i, column=5, value=net_debt)
        ws.cell(row=i, column=6, value=f"=D{i}+E{i}")
        ws.cell(row=i, column=7, value=revenue)
        ws.cell(row=i, column=8, value=ebitda)
        ws.cell(row=i, column=9, value=ni)
        ws.cell(row=i, column=10, value=period)
        ws.cell(row=i, column=11, value=units)
        ws.cell(row=i, column=12, value=f"=F{i}/G{i}")
        ws.cell(row=i, column=13, value=f'=IF(H{i}<=0,"n/m",F{i}/H{i})')
        ws.cell(row=i, column=14, value=f'=IF(I{i}<=0,"n/m",D{i}/I{i})')
        # the flag names its reason, so an exclusion is auditable rather than implicit
        ws.cell(
            row=i,
            column=15,
            value=(
                f'=IF(K{i}<>$J$2,"excluded: units "&K{i},'
                f'IF(J{i}<>$H$2,"excluded: period "&J{i},"comparable"))'
            ),
        )
        # comparable-only columns: empty when the row is not comparable, so
        # MEDIAN/COUNT ignore it exactly as they ignore text
        ws.cell(row=i, column=17, value=f'=IF($O{i}="comparable",L{i},"")')
        ws.cell(row=i, column=18, value=f'=IF($O{i}="comparable",M{i},"")')
        ws.cell(row=i, column=19, value=f'=IF($O{i}="comparable",N{i},"")')

    ws["A10"] = "Statistics over comparable rows only"
    stats = [
        ("Maximum", "=MAX({r})"),
        ("75th percentile", "=QUARTILE({r},3)"),
        ("Median", "=MEDIAN({r})"),
        ("25th percentile", "=QUARTILE({r},1)"),
        ("Minimum", "=MIN({r})"),
        ("Count (numeric observations)", "=COUNT({r})"),
    ]
    for i, (label, formula) in enumerate(stats, start=11):
        ws.cell(row=i, column=1, value=label)
        for col in (17, 18, 19):
            letter = get_column_letter(col)
            ws.cell(row=i, column=col, value=formula.format(r=f"{letter}4:{letter}8"))
    ws["A18"] = "Excluded rows (named reason is in column O)"
    ws["A19"] = "=TEXTJOIN(\", \",TRUE,IF($O$4:$O$8<>\"comparable\",$A$4:$A$8&\" \"&$O$4:$O$8,\"\"))"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["O"].width = 26
    wb.save(path)


def build_scenario(path: Path) -> None:
    """Switched base/bull/bear model plus a growth x margin sensitivity grid."""
    wb = Workbook()
    sc = wb.active
    sc.title = "Scenarios"
    sc["A1"] = "Synthetic scenario fixture - disposable, not financial data"
    sc["A2"] = "Switch (1 = base, 2 = bull, 3 = bear)"
    sc["B2"] = 1
    sc["A4"] = "Revenue growth"
    sc["B4"] = 0.05
    sc["C4"] = 0.12
    sc["D4"] = -0.03
    sc["A5"] = "Gross margin"
    sc["B5"] = 0.40
    sc["C5"] = 0.45
    sc["D5"] = 0.32
    sc["A7"] = "Base"
    sc["A8"] = "Bull"
    sc["A9"] = "Bear"
    for row, col in ((7, "B"), (8, "C"), (9, "D")):
        sc[f"{col}7"] = f"={col}4"
    sc["A11"] = "Delivery case is column B (base) unless the user asks otherwise."
    sc.column_dimensions["A"].width = 40

    m = wb.create_sheet("Model")
    m["A1"] = "Synthetic scenario fixture - disposable, not financial data"
    m["A3"] = "Revenue prior year (supplied)"
    m["B3"] = 1000
    m["A4"] = "Revenue growth (from switch)"
    m["B4"] = "=INDEX(Scenarios!$B$4:$D$4,1,Scenarios!$B$2)"
    m["A5"] = "Revenue"
    m["B5"] = "=B3*(1+B4)"
    m["A6"] = "Gross profit"
    m["B6"] = "=B5*INDEX(Scenarios!$B$5:$D$5,1,Scenarios!$B$2)"
    m["A7"] = "Opex (fixed)"
    m["B7"] = 300
    m["A8"] = "EBIT"
    m["B8"] = "=B6-B7"
    m["A9"] = "Tax rate"
    m["B9"] = 0.25
    m["A10"] = "Tax"
    m["B10"] = "=MAX(0,B8*B9)"
    m["A11"] = "Net income"
    m["B11"] = "=B8-B10"

    m["A13"] = (
        "Sensitivity cross-check: net income by revenue growth (rows) and gross margin (columns)"
        " - closed-form recomputation of the driver arithmetic, not a model recapture;"
        " a real grid must be recalculated through the model, axis value by axis value"
    )
    m["B14"] = "growth \ margin"
    for i, margin in enumerate([0.32, 0.40, 0.45]):
        m.cell(row=14, column=3 + i, value=margin)
    for i, growth in enumerate([0.05, -0.03]):
        m.cell(row=15 + i, column=2, value=growth)
        for j in range(3):
            col = get_column_letter(3 + j)
            # closed form: the same growth/margin/opex/tax arithmetic, written directly.
            # This is a cross-check of the driver maths; it does NOT flow through the
            # model's linkages, so a linkage break would not show up here - the test
            # proves that gap explicitly rather than papering over it.
            m.cell(
                row=15 + i,
                column=3 + j,
                value=f"=MAX(0,((1000*(1+$B{15 + i}))*{col}$14-$B$7))*(1-$B$9)",
            )
    m.column_dimensions["A"].width = 40
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
    build_data_tables(out / "data_tables.xlsx")
    build_three_statement(out / "three_statement.xlsx")
    build_dcf(out / "dcf.xlsx")
    build_comps(out / "comps.xlsx")
    build_scenario(out / "scenario.xlsx")
    for f in sorted(out.iterdir()):
        print(f)


if __name__ == "__main__":
    main()
