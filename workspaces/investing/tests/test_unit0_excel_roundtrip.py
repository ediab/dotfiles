#!/usr/bin/env python3
"""Unit 0 feasibility test: prove the Excel path before porting any skills.

Runs the AppleScript automation layer against disposable synthetic workbooks and
checks, with openpyxl reading the saved files:

  * input edit -> dependent formulas recalculate to the arithmetically correct values
  * save / close / reopen preserves formulas, and Excel's results survive the round trip
  * workbook features survive an Excel save (defined name, data validation,
    conditional format, chart, hidden sheet, comment, number formats, freeze panes,
    column widths, tab colour)
  * an unedited baseline copy recalculates separately from the edited copy (A->B->C)
  * external links are NOT refreshed on open (open without updating links)
  * Excel application settings are restored, with the post-restore values read back
  * unrelated open workbooks block the run instead of being recalculated
  * the supplied originals are never written to (hashes unchanged)

Usage:   .venv/bin/python tests/test_unit0_excel_roundtrip.py [--work DIR]
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APPLESCRIPT = ROOT / "scripts" / "excel_model.applescript"

sys.path.insert(0, str(HERE))
import make_fixtures  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}      {detail}")
        FAILURES.append(label)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excel(*args: str) -> dict[str, list[list[str]]]:
    """Run excel_model.applescript and parse its TSV report into records."""
    proc = subprocess.run(
        ["osascript", str(APPLESCRIPT), *args], capture_output=True, text=True, timeout=900
    )
    if proc.returncode != 0:
        raise RuntimeError(f"osascript failed ({proc.returncode}): {proc.stderr.strip()}")
    records: dict[str, list[list[str]]] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        records.setdefault(parts[0], []).append(parts[1:])
    return records


def single(records: dict, key: str, field: int = 0, default: str = "") -> str:
    rows = records.get(key)
    if not rows:
        return default
    row = rows[0]
    return row[field] if len(row) > field else default


def app_value(records: dict, key: str, default: str = "") -> str:
    """Look up an APP record by its key (APP rows are key/value pairs)."""
    for row in records.get("APP", []):
        if row and row[0] == key:
            return row[1] if len(row) > 1 else default
    return default


def cells(records: dict) -> dict[str, tuple[str, str, bool]]:
    """sheet!cell -> (formula, raw value text, is_error)"""
    out = {}
    for row in records.get("CELL", []):
        sheet, addr, formula, value, _text, is_error = (row + [""] * 6)[:6]
        out[f"{sheet}!{addr}"] = (formula, value, is_error == "true")
    return out


def num(value_text: str) -> float:
    return float(value_text)


def _rgb(color) -> str:
    """Normalise an openpyxl colour to its six RGB hex digits (alpha is dropped)."""
    rgb = getattr(color, "rgb", color)
    if not rgb or not isinstance(rgb, str):
        return ""
    return rgb[-6:]


def features(path: Path) -> dict:
    """Inventory the workbook features an Excel save must not destroy."""
    wb = load_workbook(path)
    inv: dict = {
        "sheets": wb.sheetnames,
        "hidden_sheets": [ws.title for ws in wb.worksheets if ws.sheet_state != "visible"],
        "defined_names": sorted(wb.defined_names.keys()),
        "sheet_features": {},
    }
    for ws in wb.worksheets:
        inv["sheet_features"][ws.title] = {
            "freeze_panes": ws.freeze_panes,
            "col_a_width": ws.column_dimensions["A"].width,
            "col_b_width": ws.column_dimensions["B"].width,
            "data_validations": len(ws.data_validations.dataValidation),
            "conditional_formats": len(list(ws.conditional_formatting)),
            "charts": len(ws._charts),
            # Excel rewrites the alpha byte (00xxxxxx -> FFxxxxxx) on save; compare RGB only.
            "tab_color": _rgb(ws.sheet_properties.tabColor),
            "comments": sum(1 for row in ws.iter_rows() for c in row if c.comment),
            "number_formats": {
                f"{ws.title}!{c.coordinate}": c.number_format
                for row in ws.iter_rows()
                for c in row
                if c.number_format != "General"
            },
        }
    return inv


def formulas(path: Path) -> dict[str, str]:
    wb = load_workbook(path)
    out = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    out[f"{ws.title}!{c.coordinate}"] = c.value
    return out


def cached(path: Path) -> dict[str, object]:
    wb = load_workbook(path, data_only=True)
    out = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    out[f"{ws.title}!{c.coordinate}"] = c.value
    return out


def write_cells_file(path: Path, entries: list[tuple[str, str]]) -> None:
    path.write_text("".join(f"{s}\t{c}\n" for s, c in entries))


def write_changes_file(path: Path, entries: list[tuple[str, str, str, str]]) -> None:
    path.write_text("".join("\t".join(e) + "\n" for e in entries))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=str(HERE / "tmp" / "unit0-run"))
    args = parser.parse_args()

    work = Path(args.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fixtures = work / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    make_fixtures.build_feasibility(fixtures / "feasibility.xlsx")
    make_fixtures.build_linked(fixtures / "linked.xlsx", "feasibility.xlsx")

    original = fixtures / "feasibility.xlsx"
    original_hash = sha256(original)
    original_features = features(original)
    original_formulas = formulas(original)

    print("== A: original fixture (disposable synthetic workbook)")
    check("fixture has the expected formula chain", len(original_formulas) == 7, str(len(original_formulas)))
    check("fixture carries a defined name", "UnitsSold" in original_features["defined_names"])
    check("fixture carries a chart", original_features["sheet_features"]["Model"]["charts"] == 1)

    readback = work / "readback.tsv"
    write_cells_file(
        readback,
        [
            ("Inputs", "B3"),
            ("Inputs", "B5"),
            ("Model", "B3"),
            ("Model", "B6"),
            ("Model", "B8"),
            ("Model", "B10"),
        ],
    )

    print("== status before any run")
    before = excel("status")
    check("no other workbooks open in Excel at the start", not before.get("OTHER_WORKBOOK"), str(before.get("OTHER_WORKBOOK")))
    pre_settings = {row[0]: row[1] for row in before.get("APP", []) if len(row) >= 2}
    pre_book_count = app_value(before, "workbook_count")

    print("== B: baseline recalculation of an unedited copy")
    copy_b = work / "copy-b.xlsx"
    shutil.copy2(original, copy_b)
    report_b = excel("recalc", f"workbook={copy_b}", f"readback={readback}", f"out={work}/report-b.tsv")
    status_b = single(report_b, "STATUS")
    check("baseline recalculation reports OK", status_b == "OK", status_b + single(report_b, "MESSAGE"))
    check("baseline recalculated via calculate full", "calculate full" in str(report_b.get("CALC")))
    check("baseline was saved", single(report_b, "SAVED") != "")
    check("baseline was closed", single(report_b, "CLOSED") != "")
    restored_b = single(report_b, "RESTORED")
    check("settings restored and read back (match=true)", "match=true" in restored_b, restored_b)

    cb = cells(report_b)
    check("B Model!B3 = 1000 * 25.5", "Model!B3" in cb and num(cb["Model!B3"][1]) == 25500.0)
    check("B Model!B8 net income = 6525", "Model!B8" in cb and num(cb["Model!B8"][1]) == 6525.0)
    check("B tie-out Inputs!B5 equals Model!B8", num(cb["Inputs!B5"][1]) == num(cb["Model!B8"][1]))
    check("B stored error cell flagged as an error", cb["Model!B10"][2] is True)

    saved_b = cached(copy_b)
    check("B saved file carries Excel's result for Model!B3", float(saved_b["Model!B3"]) == 25500.0)
    check("B saved file carries Excel's result for Model!B8", float(saved_b["Model!B8"]) == 6525.0)
    check("B preserved every formula verbatim", formulas(copy_b) == original_formulas)
    check("B preserved workbook features", features(copy_b) == original_features)
    hash_b_before_edit = sha256(copy_b)
    check("original A was not modified by the baseline run", sha256(original) == original_hash)

    print("== C: approved edit applied to a fresh copy of A")
    copy_c = work / "copy-c.xlsx"
    shutil.copy2(original, copy_c)
    changes = work / "changes.tsv"
    write_changes_file(changes, [("Inputs", "B3", "number", "2000")])
    report_c = excel(
        "edit",
        f"workbook={copy_c}",
        f"changes={changes}",
        f"readback={readback}",
        f"out={work}/report-c.tsv",
    )
    status_c = single(report_c, "STATUS")
    check("edit run reports OK", status_c == "OK", status_c + single(report_c, "MESSAGE"))
    check("change count is 1", any(row[:3] == ["*", "*", "count"] and row[3] == "1" for row in report_c.get("CHANGE", [])))
    change_row = report_c.get("CHANGE", [[]])[0]
    check(
        "change log shows old and new content",
        len(change_row) >= 4 and "before[1000] after[2000]" in change_row[3],
        str(change_row),
    )

    cc = cells(report_c)
    check("C input edit took effect", num(cc["Inputs!B3"][1]) == 2000.0)
    check("C dependent revenue recalculated to 51000", num(cc["Model!B3"][1]) == 51000.0)
    check("C dependent EBIT recalculated to 18900", num(cc["Model!B6"][1]) == 18900.0)
    check("C dependent net income recalculated to 14175", num(cc["Model!B8"][1]) == 14175.0)
    check("C unrelated error cell still an error", cc["Model!B10"][2] is True)

    saved_c = cached(copy_c)
    check("C saved workbook holds the edited result", float(saved_c["Model!B3"]) == 51000.0)
    check("C preserved every formula verbatim", formulas(copy_c) == original_formulas)
    check("C preserved workbook features", features(copy_c) == original_features)
    check("C baseline copy B untouched by the edit run", sha256(copy_b) == hash_b_before_edit)

    print("== C reopened in Excel: results persist")
    reopen = excel("recalc", f"workbook={copy_c}", f"readback={readback}", "calc=dirty")
    rc = cells(reopen)
    check("reopened workbook reports OK", single(reopen, "STATUS") == "OK")
    check("reopened Model!B3 still 51000", num(rc["Model!B3"][1]) == 51000.0)
    check("reopened Model!B8 still 14175", num(rc["Model!B8"][1]) == 14175.0)
    check("reopened formulas unchanged", formulas(copy_c) == original_formulas)

    print("== external links are not refreshed on open")
    linked = work / "linked.xlsx"
    shutil.copy2(fixtures / "linked.xlsx", linked)
    target = work / "feasibility-for-link.xlsx"
    shutil.copy2(fixtures / "feasibility.xlsx", linked.parent / "feasibility.xlsx")
    link_readback = work / "readback-link.tsv"
    write_cells_file(link_readback, [("Link", "B2")])
    report_link = excel("recalc", f"workbook={linked}", f"readback={link_readback}")
    ok_link = single(report_link, "STATUS") == "OK"
    check("workbook with an external link opens", ok_link, str(report_link.get("MESSAGE")))
    if ok_link:
        lc = cells(report_link)
        value = lc.get("Link!B2", ("", "0", False))[1]
        # 5100 is the value cached in the externalLink part; 6525 would mean Excel
        # refreshed the link from the other workbook. Target copy is uncalculated,
        # so any refreshed value differs from the cached one.
        check("external link value is the cached one, not a refreshed one", num(value) == 5100.0, value)

    print("== guard: unrelated open workbook blocks the run")
    held = work / "held-open.xlsx"
    shutil.copy2(fixtures / "feasibility.xlsx", held)
    hold = excel("recalc", f"workbook={held}", "close=no")
    check("holding run reports OK", single(hold, "STATUS") == "OK")
    blocked = excel("recalc", f"workbook={held}")
    check("second run is blocked while a workbook is open", single(blocked, "STATUS") == "BLOCKED", str(blocked.get("STATUS")))
    # Close exactly the workbook this test deliberately left open.
    closed = excel("close", f"workbook={held}")
    check("close command closed the held-open workbook", single(closed, "CLOSED") == "held-open.xlsx")

    print("== settings and session state after all runs")
    after = excel("status")
    check("no stray workbooks left open", app_value(after, "workbook_count") == "0", app_value(after, "workbook_count"))
    post_settings = {row[0]: row[1] for row in after.get("APP", []) if len(row) >= 2}
    check(
        "display alerts restored to pre-run value",
        post_settings.get("display_alerts") == pre_settings.get("display_alerts"),
        f"{pre_settings.get('display_alerts')} -> {post_settings.get('display_alerts')}",
    )
    check(
        "ask-to-update-links restored to pre-run value",
        post_settings.get("ask_to_update_links") == pre_settings.get("ask_to_update_links"),
        f"{pre_settings.get('ask_to_update_links')} -> {post_settings.get('ask_to_update_links')}",
    )
    check("original A unchanged overall", sha256(original) == original_hash)
    check(
        "workbook count unchanged",
        pre_book_count == app_value(after, "workbook_count"),
        f"{pre_book_count} -> {app_value(after, 'workbook_count')}",
    )

    print()
    if FAILURES:
        print(f"{len(FAILURES)}/{CHECKS} checks FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"all {CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
