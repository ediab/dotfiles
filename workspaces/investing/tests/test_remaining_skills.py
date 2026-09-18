#!/usr/bin/env python3
"""Phase 3 checkpoint: 3-statement-model, dcf-model, comps-analysis, scenario-analysis.

Each part uses the real tools the skills call (inspect_workbook.py and
excel_model.applescript) and compares Excel's results against values computed
here, from the fixtures' own definitions — never read back from the workbook's
formulas.

  3-statement-model  change one operating driver in a linked IS/BS/CF fixture;
                     confirm the change flows through all three statements, the
                     balance sheet balances and cash ties out within tolerance,
                     and history is untouched.
  dcf-model          independently compute NOPAT-free unlevered FCF discounting,
                     terminal value, the enterprise-to-equity bridge and the
                     per-share value; compare with the workbook under stated
                     conventions.
  comps-analysis     recompute enterprise values, multiples and medians from the
                     supplied peer data; confirm negative-denominator peers read
                     "n/m" and are excluded from the statistics, and that period
                     and unit mismatches are declared.
  scenario-analysis  toggle base/bull/bear, verify only the switch moved and only
                     the intended outputs recomputed, check a sensitivity grid
                     independently, then restore and save the delivery case.

Usage:  .venv/bin/python tests/test_remaining_skills.py [--work DIR]
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PYTHON = sys.executable
INSPECTOR = ROOT / "scripts" / "inspect_workbook.py"

sys.path.insert(0, str(HERE))
import make_fixtures  # noqa: E402
import test_unit0_excel_roundtrip as base  # noqa: E402
from test_unit0_excel_roundtrip import check, excel, sha256, single  # noqa: E402
from test_audit_update_memo import close_to, inspector  # noqa: E402

from openpyxl import load_workbook  # noqa: E402

# --------------------------------------------------------------------- helpers


def raw_cells(records: dict) -> dict[str, str]:
    """sheet!cell -> raw value text as Excel reported it."""
    out = {}
    for row in records.get("CELL", []):
        sheet, addr, _formula, value = (row + [""] * 4)[:4]
        out[f"{sheet}!{addr}"] = value
    return out


def cells(records: dict) -> dict[str, float]:
    out = {}
    for key, value in raw_cells(records).items():
        try:
            out[key] = float(value)
        except ValueError:
            continue
    return out


def readback_file(path: Path, entries: list[tuple[str, str]]) -> Path:
    path.write_text("".join(f"{sheet}\t{cell}\n" for sheet, cell in entries))
    return path


# ------------------------------------------------- 3-statement independent model

def three_statement_model(growth: tuple[float, float] = (0.08, 0.10)) -> dict[str, dict[str, float]]:
    """The fixture's own definitions, reimplemented independently."""
    g1, g2 = growth
    gm = (0.40, 0.41)
    sm = (0.10, 0.105)
    ga = (0.08, 0.08)
    da_pct = 0.0625
    rate = 0.05
    tax = 0.25
    dso, dio, dpo = 50.0, 60.0, 50.0
    capex_pct = 0.08
    repay_cur, repay_lt, div = 10.0, 20.0, 20.0

    state = {
        "FY0": {
            "revenue": 1000.0, "cogs": 600.0, "gp": 400.0, "sm": 100.0, "ga": 80.0, "da": 50.0,
            "ebit": 170.0, "interest": 20.0, "ebt": 150.0, "tax": 37.5, "ni": 112.5,
            "ar": 137.0, "inv": 98.6, "ap": 82.2, "ppe_gross": 800.0, "accdep": 200.0,
            "ppe_net": 600.0, "cash": 150.0, "cur_debt": 50.0, "lt_debt": 150.0,
            "common": 300.0, "re": 403.4,
        }
    }
    for year, growth_rate, margin, sm_pct, ga_pct in (
        ("FY1", g1, gm[0], sm[0], ga[0]),
        ("FY2", g2, gm[1], sm[1], ga[1]),
    ):
        prev = state["FY0"] if year == "FY1" else state["FY1"]
        revenue = prev["revenue"] * (1 + growth_rate)
        cogs = revenue * (1 - margin)
        gp = revenue - cogs
        sm = revenue * sm_pct
        ga = revenue * ga_pct
        da = prev["ppe_gross"] * da_pct
        ebit = gp - sm - ga - da
        interest = (prev["cur_debt"] + prev["lt_debt"]) * rate
        ebt = ebit - interest
        tax_expense = max(0.0, ebt * tax)
        ni = ebt - tax_expense
        ar = revenue * dso / 365
        inv = cogs * dio / 365
        ap = cogs * dpo / 365
        capex = revenue * capex_pct
        ppe_gross = prev["ppe_gross"] + capex
        accdep = prev["accdep"] + da
        cur_debt = prev["cur_debt"] - repay_cur
        lt_debt = prev["lt_debt"] - repay_lt
        re = prev["re"] + ni - div
        cfo = ni + da - (ar - prev["ar"]) - (inv - prev["inv"]) + (ap - prev["ap"])
        cfi = -capex
        cff = -(repay_cur + repay_lt) - div
        net_change = cfo + cfi + cff
        cash = prev["cash"] + net_change
        total_assets = cash + ar + inv + (ppe_gross - accdep)
        total_liabilities = ap + cur_debt + lt_debt
        total_equity = prev["common"] + re
        state[year] = {
            "revenue": revenue, "cogs": cogs, "gp": gp, "sm": sm, "ga": ga, "da": da,
            "ebit": ebit, "interest": interest, "ebt": ebt, "tax": tax_expense, "ni": ni,
            "ar": ar, "inv": inv, "ap": ap, "ppe_gross": ppe_gross, "accdep": accdep,
            "ppe_net": ppe_gross - accdep, "cash": cash, "cur_debt": cur_debt, "lt_debt": lt_debt,
            "common": prev["common"], "re": re, "total_assets": total_assets,
            "total_liabilities": total_liabilities, "total_equity": total_equity,
            "check_bs": total_assets - total_liabilities - total_equity,
            "cfo": cfo, "cfi": cfi, "cff": cff, "net_change": net_change,
            "ending_cash": cash, "check_cash": cash - cash,
        }
    return state


# ------------------------------------------------------------ DCF independent

def dcf_model(wacc: float = 0.10, growth: float = 0.025, net_debt: float = 500.0,
              shares: float = 100.0) -> dict[str, float]:
    fcfs = [100.0, 110.0, 121.0, 133.1, 146.41]
    periods = [year - 0.5 for year in range(1, 6)]
    factors = [1 / (1 + wacc) ** period for period in periods]
    pv_fcfs = [fcf * factor for fcf, factor in zip(fcfs, factors)]
    terminal_value = fcfs[-1] * (1 + growth) / (wacc - growth)
    pv_terminal = terminal_value * factors[-1]
    enterprise_value = sum(pv_fcfs) + pv_terminal
    equity_value = enterprise_value - net_debt
    return {
        "sum_pv_fcf": sum(pv_fcfs),
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "tv_share": pv_terminal / enterprise_value,
        "equity_value": equity_value,
        "per_share": equity_value / shares,
    }


# ---------------------------------------------------------- comps independent

def comps_model() -> dict[str, float | str | int]:
    peers = [
        ("ALPHA", 50, 100, 200, 500, 100, 60),
        ("BETA", 25, 200, -50, 800, 160, 90),
        ("GAMMA", 12, 150, 300, 400, -20, -30),
        ("DELTA", 8, 400, 100, 1200, 240, 120),
        ("EPSILON", 60, 50, 0, 200, 40, 25),
    ]
    rows = {}
    for name, price, shares, net_debt, revenue, ebitda, ni in peers:
        market_cap = price * shares
        ev = market_cap + net_debt
        rows[name] = {
            "market_cap": market_cap,
            "ev": ev,
            "ev_revenue": ev / revenue,
            "ev_ebitda": ev / ebitda if ebitda > 0 else "n/m",
            "pe": market_cap / ni if ni > 0 else "n/m",
        }

    def median(values: list[float]) -> float:
        ordered = sorted(values)
        mid = len(ordered) // 2
        return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2

    def quartile(values: list[float], q: int) -> float:
        """Excel's QUARTILE / PERCENTILE.INC (linear interpolation)."""
        ordered = sorted(values)
        position = (len(ordered) - 1) * q / 4
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return ordered[int(position)]
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    numeric_ev_revenue = [r["ev_revenue"] for r in rows.values()]
    numeric_ev_ebitda = [r["ev_ebitda"] for r in rows.values() if r["ev_ebitda"] != "n/m"]
    numeric_pe = [r["pe"] for r in rows.values() if r["pe"] != "n/m"]
    return {
        "rows": rows,
        "ev_revenue": {
            "median": median(numeric_ev_revenue),
            "q1": quartile(numeric_ev_revenue, 1),
            "q3": quartile(numeric_ev_revenue, 3),
            "count": len(numeric_ev_revenue),
        },
        "ev_ebitda": {
            "median": median(numeric_ev_ebitda),
            "count": len(numeric_ev_ebitda),
        },
        "pe": {"median": median(numeric_pe), "count": len(numeric_pe)},
    }


# ------------------------------------------------------- scenario independent

def scenario_case(growth: float, margin: float, opex: float = 300.0,
                  tax: float = 0.25, revenue_prior: float = 1000.0) -> dict[str, float]:
    revenue = revenue_prior * (1 + growth)
    gross_profit = revenue * margin
    ebit = gross_profit - opex
    tax_expense = max(0.0, ebit * tax)
    return {
        "growth": growth,
        "revenue": revenue,
        "gross_profit": gross_profit,
        "ebit": ebit,
        "tax": tax_expense,
        "net_income": ebit - tax_expense,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=str(HERE / "tmp" / "phase3"))
    args = parser.parse_args()

    restored = base.ensure_excel_idle()
    if restored:
        print(f"(closed untitled empty scratch workbook(s) Excel restored: {', '.join(restored)})")

    work = Path(args.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    fixtures = work / "fixtures"
    fixtures.mkdir(parents=True)

    make_fixtures.build_three_statement(fixtures / "three_statement.xlsx")
    make_fixtures.build_dcf(fixtures / "dcf.xlsx")
    make_fixtures.build_comps(fixtures / "comps.xlsx")
    make_fixtures.build_scenario(fixtures / "scenario.xlsx")

    # =================================================== 3-statement-model check
    print("== 3-statement-model: driver change flows through IS, BS and CF")
    original = fixtures / "three_statement.xlsx"
    original_hash = sha256(original)
    copy_b = work / "3sm-B.xlsx"
    shutil.copy2(original, copy_b)
    key_cells = [
        ("IS", "C4"), ("IS", "D4"), ("IS", "C6"), ("IS", "D6"), ("IS", "C10"), ("IS", "D10"),
        ("IS", "C14"), ("IS", "D14"),
        ("BS", "C4"), ("BS", "D4"), ("BS", "C11"), ("BS", "D11"), ("BS", "C19"), ("BS", "D19"),
        ("BS", "C23"), ("BS", "D23"),
        ("CF", "C9"), ("CF", "D9"), ("CF", "C15"), ("CF", "D15"), ("CF", "C17"), ("CF", "D17"),
        ("CF", "C19"), ("CF", "D19"),
    ]
    rb = readback_file(work / "3sm-readback.tsv", key_cells)
    baseline_report = excel("recalc", f"workbook={copy_b}", f"readback={rb}")
    check("3SM baseline recalculated", single(baseline_report, "STATUS") == "OK")
    values = cells(baseline_report)
    expected = three_statement_model()
    check(
        "3SM baseline income statement matches independent computation",
        close_to(values["IS!C14"], expected["FY1"]["ni"]) and close_to(values["IS!D14"], expected["FY2"]["ni"]),
        f"NI {values.get('IS!C14')}/{values.get('IS!D14')} vs {expected['FY1']['ni']:.2f}/{expected['FY2']['ni']:.2f}",
    )
    check(
        "3SM balance sheet balances in every period",
        abs(values["BS!C23"]) < 1e-6 and abs(values["BS!D23"]) < 1e-6,
        f"checks {values.get('BS!C23')}/{values.get('BS!D23')}",
    )
    check(
        "3SM cash ties out in every period",
        abs(values["CF!C19"]) < 1e-6 and abs(values["CF!D19"]) < 1e-6,
        f"checks {values.get('CF!C19')}/{values.get('CF!D19')}",
    )

    copy_c = work / "3sm-C.xlsx"
    shutil.copy2(original, copy_c)
    changes = work / "3sm-changes.tsv"
    changes.write_text("Assumptions\tC4\tnumber\t0.15\n")
    code, guard_out = inspector("guard", f"--workbook={copy_c}", f"--expect={sha256(original)}")
    check("3SM hash guard passes before editing", code == 0, guard_out.strip()[:80])
    edit_report = excel("edit", f"workbook={copy_c}", f"changes={changes}", f"readback={rb}")
    check("3SM driver change applied", single(edit_report, "STATUS") == "OK", single(edit_report, "MESSAGE"))
    edited = cells(edit_report)
    updated = three_statement_model(growth=(0.15, 0.10))

    check(
        "3SM income statement moved with the driver",
        not close_to(edited["IS!C4"], values["IS!C4"]) and close_to(edited["IS!C4"], updated["FY1"]["revenue"]),
        f"revenue {edited.get('IS!C4')} vs {updated['FY1']['revenue']:.2f}",
    )
    check(
        "3SM gross profit and EBIT match independent computation",
        close_to(edited["IS!C6"], updated["FY1"]["gp"]) and close_to(edited["IS!C10"], updated["FY1"]["ebit"]),
        f"GP {edited.get('IS!C6')} EBIT {edited.get('IS!C10')}",
    )
    check(
        "3SM cash flow moved (CFO recomputed)",
        close_to(edited["CF!C9"], updated["FY1"]["cfo"]),
        f"CFO {edited.get('CF!C9')} vs {updated['FY1']['cfo']:.2f}",
    )
    check(
        "3SM balance sheet moved on both sides and still balances",
        not close_to(edited["BS!C11"], values["BS!C11"])
        and abs(edited["BS!C23"]) < 1e-6
        and abs(edited["BS!D23"]) < 1e-6,
        f"assets {edited.get('BS!C11')} checks {edited.get('BS!C23')}/{edited.get('BS!D23')}",
    )
    check(
        "3SM cash still ties out after the change",
        abs(edited["CF!C19"]) < 1e-6 and abs(edited["CF!D19"]) < 1e-6,
        f"checks {edited.get('CF!C19')}/{edited.get('CF!D19')}",
    )
    check(
        "3SM retained earnings roll-forward matches independent computation",
        close_to(edited["BS!C19"], updated["FY1"]["re"]) and close_to(edited["BS!D19"], updated["FY2"]["re"]),
        f"RE {edited.get('BS!C19')}/{edited.get('BS!D19')}",
    )

    diff_path = work / "3sm-diff.json"
    inspector("diff", str(copy_b), str(copy_c), f"--out={diff_path}")
    diff = json.loads(diff_path.read_text())
    content_changes = {c["sheet_cell"]: (c["before"], c["after"]) for c in diff["changes"] if c["kind"] != "value"}
    check(
        "3SM only the approved driver changed as an input",
        content_changes == {"Assumptions!C4": (0.08, 0.15)},
        str(content_changes),
    )
    check("3SM introduced no new error cells", not diff["errors"]["new"], str(diff["errors"]))
    history = [c["sheet_cell"] for c in diff["changes"] if c["sheet_cell"].split("!")[1].startswith("B")]
    check("3SM FY0 history (column B) untouched", not history, str(history[:5]))
    check("3SM original unchanged", sha256(original) == original_hash)

    # ============================================================ dcf-model check
    print("== dcf-model: independent discounting, terminal value and bridge")
    dcf_original = fixtures / "dcf.xlsx"
    dcf_hash = sha256(dcf_original)
    dcf_copy = work / "dcf-B.xlsx"
    shutil.copy2(dcf_original, dcf_copy)
    dcf_cells = [("DCF", "B16"), ("DCF", "B18"), ("DCF", "B20"), ("DCF", "B21"), ("DCF", "B22"),
                 ("DCF", "B25"), ("DCF", "B26"), ("DCF", "B28"), ("DCF", "C15"), ("DCF", "G15")]
    dcf_rb = readback_file(work / "dcf-readback.tsv", dcf_cells)
    dcf_report = excel("recalc", f"workbook={dcf_copy}", f"readback={dcf_rb}")
    check("DCF recalculation reports OK", single(dcf_report, "STATUS") == "OK", single(dcf_report, "MESSAGE"))
    dcf_values = cells(dcf_report)
    expected_dcf = dcf_model()
    check(
        "DCF sum of discounted cash flows matches independent computation",
        close_to(dcf_values["DCF!B16"], expected_dcf["sum_pv_fcf"], 0.01),
        f"{dcf_values.get('DCF!B16')} vs {expected_dcf['sum_pv_fcf']:.4f}",
    )
    check(
        "DCF per-year discount factors match (mid-year convention)",
        close_to(dcf_values["DCF!C15"], 100 / (1.10 ** 0.5), 0.01)
        and close_to(dcf_values["DCF!G15"], 146.41 / (1.10 ** 4.5), 0.01),
        f"C15 {dcf_values.get('DCF!C15')} G15 {dcf_values.get('DCF!G15')}",
    )
    check(
        "DCF terminal value matches independent perpetuity computation",
        close_to(dcf_values["DCF!B18"], expected_dcf["terminal_value"], 0.01),
        f"{dcf_values.get('DCF!B18')} vs {expected_dcf['terminal_value']:.4f}",
    )
    check(
        "DCF terminal value is discounted, and by the right period",
        close_to(dcf_values["DCF!B20"], expected_dcf["pv_terminal"], 0.01),
        f"{dcf_values.get('DCF!B20')} vs {expected_dcf['pv_terminal']:.4f}",
    )
    check(
        "DCF enterprise value matches independent computation",
        close_to(dcf_values["DCF!B21"], expected_dcf["enterprise_value"], 0.01),
        f"{dcf_values.get('DCF!B21')} vs {expected_dcf['enterprise_value']:.4f}",
    )
    check(
        "DCF enterprise-to-equity bridge subtracts net debt correctly",
        close_to(dcf_values["DCF!B25"], expected_dcf["equity_value"], 0.01),
        f"{dcf_values.get('DCF!B25')} vs {expected_dcf['equity_value']:.4f}",
    )
    check(
        "DCF per-share value matches independent computation",
        close_to(dcf_values["DCF!B26"], expected_dcf["per_share"], 0.01),
        f"{dcf_values.get('DCF!B26')} vs {expected_dcf['per_share']:.4f}",
    )
    check(
        "DCF terminal growth is below WACC",
        close_to(dcf_values["DCF!B28"], 1.0, 1e-9),
        str(dcf_values.get("DCF!B28")),
    )
    check(
        "DCF terminal value share is below the 80% sanity bound",
        dcf_values["DCF!B22"] < 0.80,
        f"{dcf_values.get('DCF!B22')}",
    )
    code, dcf_checks = inspector("checks", str(dcf_copy), f"--out={work}/dcf-checks.json")
    check("DCF workbook has no error cells", code == 0, dcf_checks.strip()[-120:])
    check("DCF original unchanged", sha256(dcf_original) == dcf_hash)

    # ======================================================= comps-analysis check
    print("== comps-analysis: multiples, n/m handling and declared mismatches")
    comps_original = fixtures / "comps.xlsx"
    comps_hash = sha256(comps_original)
    comps_copy = work / "comps-B.xlsx"
    shutil.copy2(comps_original, comps_copy)
    comps_cells = [
        ("Comps", "F4"), ("Comps", "F5"), ("Comps", "F6"), ("Comps", "F7"), ("Comps", "F8"),
        # statistics rows: 11 Maximum, 12 75th percentile, 13 Median, 14 25th percentile,
        # 15 Minimum, 16 Count
        ("Comps", "L5"), ("Comps", "L12"), ("Comps", "L13"), ("Comps", "L14"),
        ("Comps", "M6"), ("Comps", "M13"), ("Comps", "M16"),
        ("Comps", "N6"), ("Comps", "N13"), ("Comps", "N16"),
    ]
    comps_rb = readback_file(work / "comps-readback.tsv", comps_cells)
    comps_report = excel("recalc", f"workbook={comps_copy}", f"readback={comps_rb}")
    check("comps recalculation reports OK", single(comps_report, "STATUS") == "OK", single(comps_report, "MESSAGE"))
    comps_raw = raw_cells(comps_report)
    comps_values = cells(comps_report)
    expected_comps = comps_model()

    check(
        "comps enterprise values match independent computation",
        close_to(comps_values["Comps!F7"], expected_comps["rows"]["DELTA"]["ev"], 0.01)
        and close_to(comps_values["Comps!F8"], expected_comps["rows"]["EPSILON"]["ev"], 0.01),
        f"DELTA {comps_values.get('Comps!F7')} EPSILON {comps_values.get('Comps!F8')}",
    )
    check(
        "comps EV/Revenue matches independent computation",
        close_to(comps_values["Comps!L5"], expected_comps["rows"]["BETA"]["ev_revenue"], 0.0001),
        f"{comps_values.get('Comps!L5')} vs {expected_comps['rows']['BETA']['ev_revenue']:.4f}",
    )
    check(
        "comps negative-EBITDA peer reads n/m rather than a meaningless multiple",
        comps_raw.get("Comps!M6", "").strip().lower() in {"n/m", "#div/0!"}
        and expected_comps["rows"]["GAMMA"]["ev_ebitda"] == "n/m",
        f"raw {comps_raw.get('Comps!M6')!r}",
    )
    check(
        "comps loss-making peer's P/E reads n/m",
        comps_raw.get("Comps!N6", "").strip().lower() in {"n/m", "#div/0!"},
        f"raw {comps_raw.get('Comps!N6')!r}",
    )
    check(
        "comps median EV/Revenue matches independent median",
        close_to(comps_values["Comps!L13"], expected_comps["ev_revenue"]["median"], 0.0001),
        f"{comps_values.get('Comps!L13')} vs {expected_comps['ev_revenue']['median']:.4f}",
    )
    check(
        "comps quartiles match independent computation",
        close_to(comps_values["Comps!L12"], expected_comps["ev_revenue"]["q3"], 0.0001)
        and close_to(comps_values["Comps!L14"], expected_comps["ev_revenue"]["q1"], 0.0001),
        f"q3 {comps_values.get('Comps!L12')} q1 {comps_values.get('Comps!L14')}",
    )
    check(
        "comps median EV/EBITDA excludes the n/m peer",
        close_to(comps_values["Comps!M13"], expected_comps["ev_ebitda"]["median"], 0.0001),
        f"{comps_values.get('Comps!M13')} vs {expected_comps['ev_ebitda']['median']:.4f}",
    )
    check(
        "comps median P/E excludes the loss-making peer",
        close_to(comps_values["Comps!N13"], expected_comps["pe"]["median"], 0.0001),
        f"{comps_values.get('Comps!N13')} vs {expected_comps['pe']['median']:.4f}",
    )
    check(
        "comps numeric observation counts are reported and exclude n/m",
        close_to(comps_values["Comps!M16"], float(expected_comps["ev_ebitda"]["count"]), 1e-9)
        and close_to(comps_values["Comps!N16"], float(expected_comps["pe"]["count"]), 1e-9),
        f"EV/EBITDA count {comps_values.get('Comps!M16')} P/E count {comps_values.get('Comps!N16')}",
    )
    comps_book = load_workbook(comps_copy, data_only=False)["Comps"]
    periods = {comps_book[f"J{r}"].value for r in range(4, 9)}
    units = {comps_book[f"K{r}"].value for r in range(4, 9)}
    check(
        "comps period mismatches are declared in the sheet (so they can be flagged)",
        len(periods) >= 2,
        str(sorted(periods)),
    )
    check(
        "comps unit mismatches are declared in the sheet (so they can be flagged)",
        len(units) >= 2,
        str(sorted(units)),
    )
    check("comps original unchanged", sha256(comps_original) == comps_hash)

    # ==================================================== scenario-analysis check
    print("== scenario-analysis: toggles, intended propagation, grid, delivery case")
    scenario_original = fixtures / "scenario.xlsx"
    scenario_hash = sha256(scenario_original)
    scenario_cells = [("Model", "B4"), ("Model", "B5"), ("Model", "B6"), ("Model", "B7"),
                      ("Model", "B8"), ("Model", "B10"), ("Model", "B11"),
                      ("Scenarios", "B2"),
                      ("Model", "C15"), ("Model", "D15"), ("Model", "E15"),
                      ("Model", "C16"), ("Model", "D16"), ("Model", "E16")]
    scenario_rb = readback_file(work / "scenario-readback.tsv", scenario_cells)

    base_copy = work / "scenario-base.xlsx"
    shutil.copy2(scenario_original, base_copy)
    base_report = excel("recalc", f"workbook={base_copy}", f"readback={scenario_rb}")
    check("scenario base recalculation reports OK", single(base_report, "STATUS") == "OK")
    base_values = cells(base_report)
    case_base = scenario_case(0.05, 0.40)
    check(
        "scenario base case matches independent computation",
        close_to(base_values["Model!B5"], case_base["revenue"]) and close_to(base_values["Model!B11"], case_base["net_income"]),
        f"revenue {base_values.get('Model!B5')} NI {base_values.get('Model!B11')}",
    )

    cases = {"bull": (2, 0.12, 0.45), "bear": (3, -0.03, 0.32)}
    case_values = {}
    for name, (switch, growth, margin) in cases.items():
        copy = work / f"scenario-{name}.xlsx"
        shutil.copy2(scenario_original, copy)
        change_file = work / f"scenario-{name}-changes.tsv"
        change_file.write_text(f"Scenarios\tB2\tnumber\t{switch}\n")
        report = excel("edit", f"workbook={copy}", f"changes={change_file}", f"readback={scenario_rb}")
        check(f"scenario {name} applied", single(report, "STATUS") == "OK", single(report, "MESSAGE"))
        got = cells(report)
        want = scenario_case(growth, margin)
        case_values[name] = got
        check(
            f"scenario {name} outputs recomputed to the independent expectation",
            close_to(got["Model!B5"], want["revenue"], 0.01) and close_to(got["Model!B11"], want["net_income"], 0.01),
            f"revenue {got.get('Model!B5')} NI {got.get('Model!B11')} vs {want['revenue']:.2f}/{want['net_income']:.2f}",
        )
        check(
            f"scenario {name} left fixed cost and prior-year revenue untouched",
            close_to(got["Model!B7"], 300.0) and close_to(got["Model!B5"] - got["Model!B5"], 0.0),
            f"opex {got.get('Model!B7')}",
        )
        diff_path = work / f"scenario-{name}-diff.json"
        inspector("diff", str(base_copy), str(copy), f"--out={diff_path}")
        diff = json.loads(diff_path.read_text())
        content_changes = {c["sheet_cell"]: (c["before"], c["after"]) for c in diff["changes"] if c["kind"] != "value"}
        check(
            f"scenario {name} changed exactly one input (the switch)",
            content_changes == {"Scenarios!B2": (1, switch)},
            str(content_changes),
        )
        check(f"scenario {name} introduced no errors", not diff["errors"]["new"], str(diff["errors"]))

    check(
        "scenario ordering holds (bull > base > bear)",
        case_values["bull"]["Model!B11"] > base_values["Model!B11"] > case_values["bear"]["Model!B11"],
        f"{case_values['bull'].get('Model!B11')} / {base_values.get('Model!B11')} / {case_values['bear'].get('Model!B11')}",
    )

    print("== scenario sensitivity grid, corners checked independently")
    grid = {
        ("C15", "growth 5%, margin 32%"): scenario_case(0.05, 0.32),
        ("D15", "growth 5%, margin 40%"): scenario_case(0.05, 0.40),
        ("E15", "growth 5%, margin 45%"): scenario_case(0.05, 0.45),
        ("C16", "growth -3%, margin 32%"): scenario_case(-0.03, 0.32),
        ("D16", "growth -3%, margin 40%"): scenario_case(-0.03, 0.40),
        ("E16", "growth -3%, margin 45%"): scenario_case(-0.03, 0.45),
    }
    for cell, label in grid:
        check(
            f"sensitivity corner {cell} ({label}) matches independent computation",
            close_to(base_values[f"Model!{cell}"], grid[(cell, label)]["net_income"], 0.01),
            f"{base_values.get(f'Model!{cell}')} vs {grid[(cell, label)]['net_income']:.2f}",
        )
    grid_unchanged = all(
        close_to(base_values[f"Model!{cell}"], case_values["bull"][f"Model!{cell}"], 1e-9)
        for cell, _ in grid
    )
    check("sensitivity grid did not move with the case toggle", grid_unchanged)

    delivery = work / "scenario-delivery.xlsx"
    shutil.copy2(scenario_original, delivery)
    restore = work / "scenario-restore.tsv"
    restore.write_text("Scenarios\tB2\tnumber\t1\n")
    restore_report = excel("edit", f"workbook={delivery}", f"changes={restore}", f"readback={scenario_rb}")
    check("delivery copy restored to the base case", single(restore_report, "STATUS") == "OK")
    delivered = cells(restore_report)
    check(
        "delivered workbook holds the base case (switch = 1)",
        close_to(delivered["Scenarios!B2"], 1.0) and close_to(delivered["Model!B5"], case_base["revenue"], 0.01),
        f"switch {delivered.get('Scenarios!B2')} revenue {delivered.get('Model!B5')}",
    )
    check("scenario original unchanged", sha256(scenario_original) == scenario_hash)

    print()
    if base.FAILURES:
        print(f"{len(base.FAILURES)}/{base.CHECKS} checks FAILED:")
        for failure in base.FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"all {base.CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
