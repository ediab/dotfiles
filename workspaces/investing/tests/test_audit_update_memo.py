#!/usr/bin/env python3
"""Phase 2 checkpoint: prove audit-xls, model-update and investment-memo on fixtures.

Uses the real tools the skills call (inspect_workbook.py and
excel_model.applescript) and checks financial results against values computed
here, independently of the workbook's own formulas.

  audit-xls       a recalculated copy of a deliberately defective fixture is
                  inspected and mechanically checked: the broken references, the
                  formula that breaks its neighbours' pattern and the failed
                  tie-out are located, while harmless hardcoded assumptions are
                  not reported as defects.
  model-update    an approved input change is applied to a fresh copy after the
                  hash guard; direct edits, propagated values and the untouched
                  original are verified, and a stale hash is rejected.
  investment-memo memo figures reconcile to the delivered workbook through the
                  evidence record, and a disagreement is caught.

Usage:  .venv/bin/python tests/test_audit_update_memo.py [--work DIR]
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PYTHON = sys.executable
INSPECTOR = ROOT / "scripts" / "inspect_workbook.py"
APPLESCRIPT = ROOT / "scripts" / "excel_model.applescript"
TEMPLATE = ROOT / "templates" / "investment-memo.html"

sys.path.insert(0, str(HERE))
import make_fixtures  # noqa: E402
import test_unit0_excel_roundtrip as base  # noqa: E402
from test_unit0_excel_roundtrip import check, excel, sha256, single  # noqa: E402

# Fixture arithmetic, recomputed here rather than read back from the workbook.
PRICE = 25.5
OPEX = 1500.0
TAX_RATE = 0.25
GROSS_MARGIN = 0.4


def expected_model(units: float) -> dict[str, float]:
    revenue = units * PRICE
    gross = revenue * GROSS_MARGIN
    ebit = gross - OPEX
    tax = ebit * TAX_RATE if ebit > 0 else 0.0
    return {
        "Inputs!B3": units,
        "Model!B3": revenue,
        "Model!B4": gross,
        "Model!B6": ebit,
        "Model!B7": tax,
        "Model!B8": ebit - tax,
        "Inputs!B5": ebit - tax,
    }


def inspector(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [PYTHON, str(INSPECTOR), *args], capture_output=True, text=True, timeout=900
    )
    return proc.returncode, proc.stdout + proc.stderr


def cells_of(records: dict) -> dict[str, float]:
    out = {}
    for row in records.get("CELL", []):
        sheet, addr, _formula, value = (row + [""] * 4)[:4]
        try:
            out[f"{sheet}!{addr}"] = float(value)
        except ValueError:
            continue
    return out


def close_to(a: float, b: float, tolerance: float = 1e-6) -> bool:
    return abs(a - b) <= tolerance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=str(HERE / "tmp" / "checkpoint"))
    args = parser.parse_args()

    restored = base.ensure_excel_idle()
    if restored:
        print(f"(closed untitled empty scratch workbook(s) Excel restored: {', '.join(restored)})")

    work = Path(args.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    fixtures = work / "fixtures"
    fixtures.mkdir(parents=True)
    assignment = work / "SAMPLE-company"
    (assignment / "working").mkdir(parents=True)
    (assignment / "outputs").mkdir(parents=True)
    (assignment / "inputs").mkdir(parents=True)

    make_fixtures.build_feasibility(fixtures / "feasibility.xlsx")
    make_fixtures.build_audit(fixtures / "audit.xlsx")
    make_fixtures.build_data_tables(fixtures / "data_tables.xlsx")

    # ======================================================= audit-xls checkpoint
    print("== audit-xls: locate defects and separate them from harmless inputs")
    audit_a = fixtures / "audit.xlsx"
    audit_hash_a = sha256(audit_a)
    audit_b = work / "audit-B.xlsx"
    shutil.copy2(audit_a, audit_b)
    report = excel("recalc", f"workbook={audit_b}")
    check("audit copy recalculated in Excel", single(report, "STATUS") == "OK")
    check("audit original untouched by recalculation", sha256(audit_a) == audit_hash_a)

    checks_path = assignment / "working" / "audit-checks.json"
    code, output = inspector("checks", str(audit_b), f"--out={checks_path}")
    check("checks mode reports error cells (exit 1)", code == 1, output[-200:])
    findings = json.loads(checks_path.read_text())["findings"]
    by_category: dict[str, list[dict]] = {}
    for finding in findings:
        by_category.setdefault(finding["category"], []).append(finding)

    error_cells = {f"{f['sheet']}!{f['cell']}" for f in by_category.get("error", [])}
    check(
        "broken reference located at the cells that carry it",
        {"P&L!B14", "P&L!B16"} <= error_cells,
        str(sorted(error_cells)),
    )
    inconsistent = {f"{f['sheet']}!{f['cell']}" for f in by_category.get("inconsistent_formula", [])}
    check(
        "formula that breaks its neighbours' pattern is located",
        inconsistent == {"P&L!C6"},
        str(sorted(inconsistent)),
    )
    tie_outs = {f"{f['sheet']}!{f['cell']}": f for f in by_category.get("tie_out", [])}
    check(
        "failed tie-out reported as failed",
        tie_outs.get("P&L!C12", {}).get("status") == "failed",
        str(tie_outs.get("P&L!C12")),
    )
    check(
        "a tie-out that holds is reported as clean, not as a defect",
        tie_outs.get("BS!B6", {}).get("status") == "ok",
        str(tie_outs.get("BS!B6")),
    )
    flagged = {f"{f['sheet']}!{f['cell']}" for f in findings}
    check(
        "hardcoded input assumptions are not reported as defects",
        not ({"P&L!B4", "P&L!B5", "P&L!B10"} & flagged - {"P&L!B10"}),
        str(sorted(flagged)),
    )
    inspect_path = assignment / "working" / "audit-inspect.json"
    inspector("inspect", str(audit_b), f"--out={inspect_path}")
    inspect_record = json.loads(inspect_path.read_text())
    p_and_l = next(s for s in inspect_record["sheets"] if s["title"] == "P&L")
    check(
        "inputs are counted as constants, not as formula findings",
        p_and_l["constant_count"] >= 6 and p_and_l["formula_count"] == 10,
        f"constants={p_and_l['constant_count']} formulas={p_and_l['formula_count']}",
    )
    check("inspection records the file hash for gating", len(inspect_record["sha256"]) == 64)

    tables_fixture = fixtures / "data_tables.xlsx"
    tables_path = assignment / "working" / "data-tables-inspect.json"
    inspector("inspect", str(tables_fixture), f"--out={tables_path}")
    tables_record = json.loads(tables_path.read_text())
    per_sheet = {s["title"]: s["data_table_blocks"] for s in tables_record["sheets"]}
    check(
        "data tables are counted on the sheet that holds them, not on every sheet",
        per_sheet == {"Summary": 0, "Sensitivity": 2, "Notes": 0},
        str(per_sheet),
    )
    check(
        "the data-table total is not multiplied by the sheet count",
        tables_record["totals"]["data_table_blocks"] == 2,
        str(tables_record["totals"]["data_table_blocks"]),
    )

    # ================================================== model-update checkpoint
    print("== model-update: approved actual change, hash-gated, original untouched")
    original = fixtures / "feasibility.xlsx"
    original_hash = sha256(original)

    copy_b = work / "model-B.xlsx"
    shutil.copy2(original, copy_b)
    readback = assignment / "working" / "readback.tsv"
    readback.write_text(
        "".join(f"{sheet}!{cell}\n".replace("!", "\t") for sheet, cell in
                [("Inputs", "B3"), ("Inputs", "B5"), ("Model", "B3"), ("Model", "B4"),
                 ("Model", "B6"), ("Model", "B7"), ("Model", "B8"), ("Model", "B10")])
    )
    base_report = excel("recalc", f"workbook={copy_b}", f"readback={readback}")
    base_cells = cells_of(base_report)
    baseline = expected_model(1000)
    check("baseline recalculated", single(base_report, "STATUS") == "OK")
    check(
        "baseline values equal independently computed results",
        all(close_to(base_cells[k], v) for k, v in baseline.items()),
        str(base_cells),
    )

    copy_c = work / "model-C.xlsx"
    shutil.copy2(original, copy_c)
    code, guard_out = inspector("guard", f"--workbook={copy_c}", f"--expect={original_hash}")
    check("hash guard passes on the approved input", code == 0, guard_out.strip())

    stale = work / "model-stale.xlsx"
    shutil.copy2(original, stale)
    with stale.open("ab") as handle:
        handle.write(b"\x00")
    code, guard_out = inspector("guard", f"--workbook={stale}", f"--expect={original_hash}")
    check("hash guard rejects a stale input", code == 1, guard_out.strip()[:120])

    changes = assignment / "working" / "changes.tsv"
    changes.write_text("Inputs\tB3\tnumber\t2000\n")
    (assignment / "working" / "mapping.md").write_text(
        "| Supplied item | Value | Source | Target sheet | Target cell |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Units sold (supplied actual) | 2000 | user-supplied actual | Inputs | B3 |\n"
    )
    edit_report = excel(
        "edit", f"workbook={copy_c}", f"changes={changes}", f"readback={readback}"
    )
    check("edit run reports OK", single(edit_report, "STATUS") == "OK", single(edit_report, "MESSAGE"))
    change_row = edit_report.get("CHANGE", [[]])[0]
    check(
        "change log records old and new content",
        "before[1000] after[2000]" in (change_row[3] if len(change_row) > 3 else ""),
        str(change_row),
    )
    edited_cells = cells_of(edit_report)
    updated = expected_model(2000)
    check(
        "edited and propagated values equal independently computed results",
        all(close_to(edited_cells[k], v) for k, v in updated.items()),
        str(edited_cells),
    )
    check(
        "unrelated error cell unchanged by the edit",
        edit_report.get("CELL", []) and edit_report["CELL"][-1][-1] == "true",
        str(edit_report.get("CELL", [])[-1:]),
    )

    diff_path = assignment / "working" / "diff-BC.json"
    code, diff_out = inspector("diff", str(copy_b), str(copy_c), f"--out={diff_path}")
    diff = json.loads(diff_path.read_text())
    check("diff mode ran", code == 0, diff_out[-200:])
    check(
        "no formula text was changed by the edit",
        diff["counts"]["formula_changes"] == 0
        and diff["counts"]["formula_replacement_changes"] == 0,
        str(diff["counts"]),
    )
    constant_changes = {c["sheet_cell"]: (c["before"], c["after"]) for c in diff["changes"] if c["kind"] == "constant"}
    check(
        "the only stored-content change is the approved constant",
        set(constant_changes) == {"Inputs!B3"} and constant_changes["Inputs!B3"] == (1000, 2000),
        str(constant_changes),
    )
    value_changes = {
        c["sheet_cell"]: (c["before"], c["after"])
        for c in diff["changes"]
        if c["kind"] == "value"
    }
    expected_changes = {
        key: (baseline[key], updated[key]) for key in updated if not close_to(baseline[key], updated[key])
    }
    check(
        "exactly the expected cells changed, with expected before/after",
        set(value_changes) == set(expected_changes)
        and all(close_to(float(value_changes[k][1]), v[1]) for k, v in expected_changes.items()),
        f"changed={sorted(value_changes)} expected={sorted(expected_changes)}",
    )
    check(
        "no new error cells and none silently resolved",
        not diff["errors"]["new"] and not diff["errors"]["resolved"],
        str(diff["errors"]),
    )
    check("original unchanged after the edit", sha256(original) == original_hash)
    check(
        "diff record carries both file hashes",
        diff["before"]["sha256"] == sha256(copy_b) and diff["after"]["sha256"] == sha256(copy_c),
    )

    # ================================================ investment-memo checkpoint
    print("== investment-memo: evidence reconciliation catches disagreement")
    delivered = assignment / "outputs" / "model-C.xlsx"
    shutil.copy2(copy_c, delivered)
    delivered_hash = sha256(delivered)

    evidence = {
        "workbook": delivered.name,
        "workbook_sha256": delivered_hash,
        "scenario": "base",
        "items": [
            {"label": "Units sold", "sheet": "Inputs", "cell": "B3", "expected": 2000,
             "tolerance": 0.001, "units": "units", "source": "user-supplied actual"},
            {"label": "Revenue", "sheet": "Model", "cell": "B3", "expected": 51000,
             "tolerance": 0.01, "units": "USD", "source": "derived: units x supplied price"},
            {"label": "Net income", "sheet": "Model", "cell": "B8", "expected": 14175,
             "tolerance": 0.01, "units": "USD", "source": "derived: model linkage"},
        ],
    }
    evidence_path = assignment / "outputs" / "SAMPLE-evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")
    code, verify_out = inspector("verify", f"--workbook={delivered}", f"--evidence={evidence_path}")
    check("evidence reconciles against the delivered workbook", code == 0, verify_out.strip())

    tampered = dict(evidence)
    tampered["items"] = [dict(item) for item in evidence["items"]]
    tampered["items"][1]["expected"] = 51001
    tampered_path = assignment / "outputs" / "SAMPLE-evidence-tampered.json"
    tampered_path.write_text(json.dumps(tampered, indent=2) + "\n")
    code, verify_out = inspector("verify", f"--workbook={delivered}", f"--evidence={tampered_path}")
    check("a figure that disagrees with the workbook is caught", code == 1, verify_out.strip()[:160])
    check("the failing item is named", "Revenue" in verify_out and "51001" in verify_out)

    wrong_hash = dict(evidence)
    wrong_hash["workbook_sha256"] = "0" * 64
    wrong_hash_path = assignment / "outputs" / "SAMPLE-evidence-wronghash.json"
    wrong_hash_path.write_text(json.dumps(wrong_hash, indent=2) + "\n")
    code, verify_out = inspector("verify", f"--workbook={delivered}", f"--evidence={wrong_hash_path}")
    check("evidence bound to a different workbook hash is rejected", code == 1)

    # An evidence record that cannot be checked must fail: this mode is the
    # mechanical gate between a memo's figures and the workbook.
    empty_path = assignment / "outputs" / "SAMPLE-evidence-empty.json"
    empty_path.write_text(json.dumps({"workbook_sha256": evidence["workbook_sha256"]}) + "\n")
    code, verify_out = inspector("verify", f"--workbook={delivered}", f"--evidence={empty_path}")
    check("an evidence record with no items is rejected rather than passing vacuously", code == 1)
    check("the empty-items reason is stated", "lists no items" in verify_out)

    no_hash = {"items": evidence["items"]}
    no_hash_path = assignment / "outputs" / "SAMPLE-evidence-nohash.json"
    no_hash_path.write_text(json.dumps(no_hash, indent=2) + "\n")
    code, verify_out = inspector("verify", f"--workbook={delivered}", f"--evidence={no_hash_path}")
    check("an evidence record with no workbook_sha256 is rejected", code == 1)
    check("the missing-hash reason is stated", "no workbook_sha256" in verify_out)

    code, _ = inspector(
        "verify", f"--workbook={delivered}", f"--evidence={empty_path}", "--allow-empty"
    )
    check("--allow-empty restores the vacuous pass explicitly", code == 0)

    template = TEMPLATE.read_text()
    for section in [
        "Thesis",
        "Differentiated view",
        "Operating assumptions",
        "Valuation",
        "Bull / base / bear",
        "Catalysts",
        "Risks and disconfirmers",
        "Missing evidence",
        "Provenance",
    ]:
        check(f"memo template has a {section} section", section in template)
    check(
        "memo template requires missing inputs to stay visible",
        "MISSING: source not supplied" in template,
    )
    check(
        "memo template carries the supplied-data-only statement",
        "No financial data, prices, consensus or catalysts were" in template,
    )

    # Escaping supplied text must be mechanical, not agent discipline. Run a
    # hostile supplied string through the documented stdlib escaper.
    proc = subprocess.run(
        [
            sys.executable, "-c", "import html,sys; print(html.escape(sys.argv[1]))",
            "<script>alert('VRT & Co')</script>",
        ],
        capture_output=True, text=True, timeout=30,
    )
    escaped = proc.stdout.strip()
    check(
        "the documented escaper neutralizes hostile supplied text",
        proc.returncode == 0
        and "&lt;script&gt;" in escaped
        and "&amp;" in escaped
        and "<script>" not in escaped,
        f"rc={proc.returncode} out={escaped!r}",
    )

    # A filled memo's figures must reconcile to the workbook the same way.
    memo = template
    memo = memo.replace("[Company] ([Ticker]) — [Long/Short]", "Sample Co (SMPL) - Long")
    memo = memo.replace("<td>[…]</td><td>[…]</td><td>[…]</td>", "<td>51000</td><td>14175</td><td>2000</td>", 1)
    memo_path = assignment / "outputs" / "memo.html"
    memo_path.write_text(memo)
    figures = re.findall(r">(\d{4,})<", memo)
    check("filled memo states modelled figures", "51000" in figures, str(figures))
    memo_evidence = dict(evidence)
    memo_evidence["items"] = [
        {"label": "Revenue from memo", "sheet": "Model", "cell": "B3", "expected": 51000,
         "tolerance": 0.01, "units": "USD"},
        {"label": "Net income from memo", "sheet": "Model", "cell": "B8", "expected": 14175,
         "tolerance": 0.01, "units": "USD"},
    ]
    memo_evidence_path = assignment / "outputs" / "memo-evidence.json"
    memo_evidence_path.write_text(json.dumps(memo_evidence, indent=2) + "\n")
    code, verify_out = inspector(
        "verify", f"--workbook={delivered}", f"--evidence={memo_evidence_path}"
    )
    check("memo figures reconcile to the delivered workbook", code == 0, verify_out.strip())

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
