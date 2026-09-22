# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "xlwings==0.32.2",
#   "openpyxl==3.1.5",
# ]
# ///
"""Native Excel gate for Pi's `excel` skill.

Opens a working copy of a draft .xlsx in a dedicated hidden Microsoft Excel
instance, forces a full dependency rebuild, saves cached values, scans for
formula errors (per-cell vs. baseline), checks the OOXML package inventory,
captures target cells, and renders requested ranges to PNG.

Entrypoint: `uv run --script excel_gate.py ...` ONLY. Running it with a plain
python3 will fail the worker subprocess (xlwings lives in the uv-managed
environment created from the PEP 723 header).

Usage:
  uv run --script excel_gate.py DRAFT.xlsx \
      [--baseline BASELINE.xlsx] \
      [--target "Sheet1!B5"]... \
      [--render "Sheet1!A1:M40"]... \
      [--render-sheet "Sheet1"]...           # whole-sheet PNG (pre-recalc used range)
      [--output-dir DIR]                     # PNG output dir (default: alongside draft)
      [--timeout SECONDS]                    # automation timeout (default 180)

Charts: xlwings' Chart.to_png() is unimplemented on macOS and no reliable
automation export exists; charts are reviewed via --render/--render-sheet PNGs
that cover the chart area (a passing --chart request is rejected at preflight
with that explanation). Range renders are produced by `asp render` (agent-
spreadsheet) rather than xlwings: xlwings' macOS Range.to_png copies through
the system clipboard (clobbers it) and can hang on a hidden Excel instance.

Exit codes: 0 = pass. Non-zero = automation failure, timeout, new formula
errors, missing requested targets/renders, or lost package features. A JSON
report is printed to stdout in every handled failure path. On failure the
draft is left untouched (the Excel-resaved candidate stays in the gate's temp
dir); on success the recalculated file replaces the draft atomically.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import zipfile

UNSUPPORTED_EXTENSIONS = {
    ".xlsm", ".xls", ".xlsb", ".xltm", ".xlt", ".xla", ".xlam", ".csv", ".ods",
}


class GateError(Exception):
    """Fatal gate error with a user-facing message."""


# ---------------------------------------------------------------------------
# Pure logic (unit-testable without Excel)
# ---------------------------------------------------------------------------

def split_target(target: str, allow_range: bool = False) -> tuple[str, str]:
    """Split 'Sheet1!A1' into ('Sheet1', 'A1').

    Targets are single cells; render specs may be ranges. Quoted sheet names
    are supported ('My Sheet'!A1) but a quoted name containing '!' is rejected
    rather than misparsed.
    """
    if "!" not in target:
        raise GateError(f"target must be Sheet!Cell form, got {target!r}")
    sheet, _, ref = target.partition("!")
    sheet = sheet.strip("'\"")
    ref = ref.strip()
    if not sheet or not ref:
        raise GateError(f"target must be Sheet!Cell form, got {target!r}")
    if "!" in sheet:
        raise GateError(f"quoted sheet names containing '!' are not supported: {target!r}")
    if not allow_range:
        _require_single_cell(ref, target)
    return sheet, ref


def _require_single_cell(ref: str, spec: str) -> None:
    import re

    from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
    try:
        col, row = coordinate_from_string(ref)
        column_index_from_string(col)
        int(row)
    except Exception:
        raise GateError(
            f"--target must be a single cell (Sheet!A1); use --render for ranges: {spec!r}")
    if not re.fullmatch(r"[A-Za-z]{1,3}\d+", ref):
        raise GateError(f"--target must be a single cell, got {spec!r}")


def compute_error_delta(final_cells: set, baseline_cells: set) -> tuple[list, list]:
    """Per-cell error provenance: (added, removed) sets of 'Sheet!Ref!ERROR' keys."""
    added = sorted(final_cells - baseline_cells)
    removed = sorted(baseline_cells - final_cells)
    return added, removed


def package_inventory(path: str) -> dict:
    """Inventory OOXML package parts that cell diffs can miss.

    Zip parts are enumerated by their real OOXML paths (not substrings).
    Workbook-level features come from one openpyxl pass. Never saves a
    workbook. Raises GateError on malformed files.
    """
    from openpyxl import load_workbook

    if not zipfile.is_zipfile(path):
        raise GateError(f"not a valid .xlsx package (not a zip): {path}")

    inv: dict[str, list[str]] = {
        "charts": [], "tables": [], "images": [], "drawings": [],
        "defined_names": [], "data_validations": [], "conditional_formats": [],
        "comments": [], "pivots": [], "vba": [], "slicers": [],
        "power_query": [], "connections": [], "external_links": [],
    }
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile as e:
        raise GateError(f"cannot read xlsx package {path}: {e}")

    def parts(prefix: str) -> list[str]:
        return [n for n in names if n.startswith(prefix)]

    inv["charts"] = parts("xl/charts/chart")
    inv["tables"] = parts("xl/tables/")
    inv["images"] = parts("xl/media/")
    inv["drawings"] = [n for n in parts("xl/drawings/") if n.endswith(".xml")]
    inv["vba"] = [n for n in names if n.endswith("vbaProject.bin")]
    inv["pivots"] = parts("xl/pivotTables/") + parts("xl/pivotCache/")
    inv["slicers"] = parts("xl/slicerCaches/") + parts("xl/slicers/")
    inv["power_query"] = parts("xl/queries/") + parts("xl/queryTables/") + parts("xl/customXml/")
    inv["connections"] = parts("xl/connections")
    inv["external_links"] = parts("xl/externalLinks/")
    inv["comments"] = parts("xl/comments") + parts("xl/threadedComments/")

    wb = load_workbook(path, data_only=False)
    try:
        if hasattr(wb.defined_names, "keys"):
            inv["defined_names"] = sorted(wb.defined_names.keys())
        else:  # openpyxl < 3.1 shape
            inv["defined_names"] = [dn.name for dn in wb.defined_names.definedName]
        for ws in wb.worksheets:
            if ws.data_validations.dataValidation:
                inv["data_validations"].append(ws.title)
            if ws.conditional_formatting:
                inv["conditional_formats"].append(ws.title)
    finally:
        wb.close()
    return inv


def inventory_lost(baseline: dict, final: dict) -> list[str]:
    """Features present at baseline but missing in final.

    Compares per-feature counts rather than exact part paths: Excel re-saves
    renumber package parts (drawing1.xml -> drawing2.xml), which is not a
    lost feature. Defined names are compared by name set.
    """
    lost = []
    for feature, baseline_items in baseline.items():
        final_items = final.get(feature, [])
        if feature == "defined_names":
            missing = sorted(set(baseline_items) - set(final_items))
        else:
            if len(final_items) >= len(baseline_items):
                continue
            missing = [f"count {len(baseline_items)} -> {len(final_items)}"]
        if missing:
            lost.append(f"{feature}: lost {missing}")
    return lost


def format_report(ok: bool, **fields) -> dict:
    report = {"ok": ok}
    report.update(fields)
    return report


# ---------------------------------------------------------------------------
# Excel automation (runs in a child process)
# ---------------------------------------------------------------------------

def excel_worker(draft: str, render_ranges: list[str], out_dir: str, result_path: str) -> None:
    """Child-process body: open in Excel, full rebuild, save, quit.

    Touches only its own dedicated hidden Excel instance. Writes the JSON
    result to `result_path` (never stdout — the parent reads the file).
    Raises on failure; always quits the launched app.
    """
    import xlwings as xw

    # xlwings' activate() mis-parses `lsappinfo` when the frontmost app cannot
    # be resolved; the gate never needs focus, so disable it.
    xw.App.activate = lambda self, steal_focus=False: None

    app = xw.App(visible=False, add_book=False)
    try:
        app.display_alerts = False
        app.screen_updating = False
        book = app.books.open(draft, update_links=False)
        try:
            # calculate_full_rebuild works at Application level on macOS;
            # the workbook-level command raises OSERROR -50.
            app.api.calculate_full_rebuild()
            book.save()
            with open(result_path, "w") as f:
                json.dump({"saved": True}, f)
        finally:
            book.close()
    finally:
        app.quit()


def render_pngs(gate_copy: str, render_specs: list[str], out_dir: str, timeout: int) -> list[dict]:
    """Render each requested range to PNG via `asp render` on the
    Excel-resaved workbook (cached values, so the PNGs show results)."""
    renders = []
    for spec in render_specs:
        sheet_name, rng = split_target(spec, allow_range=True)
        fname = f"render_{sheet_name}_{rng.replace(':', '_')}.png"
        out = os.path.join(out_dir, fname)
        proc = subprocess.run(
            ["asp", "render", "--sheet", sheet_name, "--range", rng,
             "--output", out, "--force", "--quiet", gate_copy],
            capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0 or not os.path.exists(out):
            raise GateError(f"render failed for {spec}: {(proc.stderr or proc.stdout or '')[-800:]}")
        renders.append({"range": spec, "path": out, "bytes": os.path.getsize(out)})
    return renders


# ---------------------------------------------------------------------------
# Cached-value inspection (parent process, openpyxl, never saves)
# ---------------------------------------------------------------------------

def read_cached_state(path: str, targets: list[str]) -> tuple[dict, set]:
    """Return (targets: {spec: {formula, value}}, error_cells: set).

    error_cells is a set of 'Sheet!Ref!ERROR' keys for per-cell provenance.
    Two openpyxl read-only passes (formulas preserved, then data_only); the
    scan iterates cell objects and detects errors via OpenPyXL's error data
    type (`cell.data_type == 'e'`), so modern errors (#SPILL!, #CALC!, ...)
    are caught alongside classic ones. Never saves either workbook.
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    formulas: dict[tuple[str, str], str] = {}
    wb_f = load_workbook(path, data_only=False, read_only=True)
    try:
        for spec in targets:
            sheet_name, ref = split_target(spec)
            if sheet_name in wb_f.sheetnames:
                cell = wb_f[sheet_name][ref]
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    formulas[(sheet_name, ref)] = cell.value
    finally:
        wb_f.close()

    error_cells: set = set()
    wb_v = load_workbook(path, data_only=True, read_only=True)
    try:
        out_targets = {}
        for spec in targets:
            sheet_name, ref = split_target(spec)
            if sheet_name not in wb_v.sheetnames:
                raise GateError(f"target sheet not found: {spec}")
            out_targets[spec] = {
                "formula": formulas.get((sheet_name, ref)),
                "value": wb_v[sheet_name][ref].value,
            }
        for ws in wb_v.worksheets:
            for r_idx, row in enumerate(ws.iter_rows(), 1):
                for c_idx, cell in enumerate(row, 1):
                    if cell.data_type == "e":
                        token = str(cell.value).strip()
                        error_cells.add(f"{ws.title}!{get_column_letter(c_idx)}{r_idx}!{token}")
    finally:
        wb_v.close()

    return out_targets, error_cells


def extract_error_kinds(error_cells: set) -> dict[str, int]:
    """Count 'Sheet!Ref!ERROR' keys by their trailing error token.

    Keys are ``Sheet!Ref!ERROR``; the ERROR token is everything after the
    second '!' (some tokens contain '!' themselves, e.g. #REF!), so split at
    the first two separators only.
    """
    counts: dict[str, int] = {}
    for cell in error_cells:
        kind = cell.split("!", 2)[2]
        counts[kind] = counts.get(kind, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Main gate
# ---------------------------------------------------------------------------

def run_gate(draft: str, baseline: str | None, targets: list[str],
             render_ranges: list[str], out_dir: str, timeout: int) -> dict:
    if os.path.splitext(draft)[1].lower() in UNSUPPORTED_EXTENSIONS:
        return format_report(False, stage="preflight", error=f"unsupported extension: {draft}")
    for spec in targets:
        try:
            split_target(spec)
        except GateError as e:
            return format_report(False, stage="preflight", error=str(e))
    if not os.path.exists(draft):
        return format_report(False, stage="preflight", error=f"draft not found: {draft}")
    if baseline and not os.path.exists(baseline):
        return format_report(False, stage="preflight", error=f"baseline not found: {baseline}")

    try:
        baseline_inventory = package_inventory(baseline) if baseline else None
        package_inventory(draft)  # fail fast on malformed packages
    except GateError as e:
        return format_report(False, stage="preflight", error=str(e))

    state = _excel_has_file_open(os.path.abspath(draft))
    if state == "open":
        return format_report(
            False, stage="preflight",
            error="the draft workbook is already open in Excel; close it before running the gate")
    if state == "undetermined":
        return format_report(
            False, stage="preflight",
            error="could not determine whether the draft is already open in Excel "
                  "(Apple Events permission may be missing). Grant permission or confirm "
                  "no Excel instance has the file open, then rerun.")

    worker_result: dict = {}
    # Checks run against gate_copy inside the temp dir; the draft is only
    # replaced (atomically) after the gate verdict passes.
    with tempfile.TemporaryDirectory(prefix="excel_gate_") as tmp:
        gate_copy = os.path.join(tmp, "gate.xlsx")
        _copy_file(draft, gate_copy)

        result_path = os.path.join(tmp, "result.json")
        worker_payload = {
            "draft": gate_copy,
            "render_ranges": render_ranges,
            "out_dir": out_dir,
            "result_path": result_path,
        }
        payload_path = os.path.join(tmp, "payload.json")
        with open(payload_path, "w") as f:
            json.dump(worker_payload, f)

        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--_worker", payload_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            _, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # SIGTERM lets the child run its finally blocks (quit the Excel
            # instance it launched); escalate to SIGKILL only if it ignores it.
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
            return format_report(
                False, stage="excel", timeout=True,
                error=f"excel automation exceeded {timeout}s; if an Excel instance remains "
                      "open, close it manually — the gate never kills Excel processes")
        if proc.returncode != 0:
            detail = stderr or ""
            if os.path.exists(result_path):  # worker wrote a structured failure
                try:
                    with open(result_path) as f:
                        detail = json.dumps(json.load(f))
                except Exception:
                    pass
            return format_report(False, stage="excel", error="excel automation failed", detail=detail[-4000:])
        with open(result_path) as f:
            worker_result = json.load(f)

        try:
            renders = render_pngs(gate_copy, render_ranges, out_dir, timeout=min(60, timeout))
        except GateError as e:
            return format_report(False, stage="render", error=str(e))
        except subprocess.TimeoutExpired:
            return format_report(False, stage="render", timeout=True,
                                 error="asp render exceeded its timeout on the requested ranges")

        try:
            target_state, final_error_cells = read_cached_state(gate_copy, targets)
        except GateError as e:
            return format_report(False, stage="inspect", error=str(e))

        try:
            final_inventory = package_inventory(gate_copy)
        except GateError as e:
            return format_report(False, stage="inspect", error=str(e))

        lost = []
        baseline_error_cells: set = set()
        baseline_errors_available = True
        if baseline_inventory is not None:
            lost = inventory_lost(baseline_inventory, final_inventory)
            try:
                _, baseline_error_cells = read_cached_state(baseline, [])
            except GateError:
                baseline_errors_available = False
        errors_added, errors_removed = compute_error_delta(final_error_cells, baseline_error_cells)

        ok = not errors_added and not lost
        if targets and not target_state:
            ok = False
        if ok:
            # Replace the draft only after the full verdict passes.
            _atomic_copy(gate_copy, draft)
        report = format_report(
            ok,
            stage="complete",
            draft=draft,
            targets=target_state,
            errors_final=extract_error_kinds(final_error_cells),
            errors_baseline=extract_error_kinds(baseline_error_cells) if baseline else {},
            baseline_errors_available=baseline_errors_available,
            errors_added=errors_added,
            errors_removed=errors_removed,
            package_lost=lost,
            renders=renders,
        )
        if targets and not target_state:
            report["error"] = "requested targets produced no results"
        if not ok:
            report["note"] = "draft left untouched; recalculated candidate existed only in the gate temp dir"
        return report


def _copy_file(src: str, dst: str) -> None:
    import shutil
    shutil.copy2(src, dst)


def _atomic_copy(src: str, dst: str) -> None:
    """Copy src over dst atomically (temp file in dst's dir + os.replace)."""
    import shutil
    tmp_dst = dst + ".gate_tmp"
    shutil.copy2(src, tmp_dst)
    os.replace(tmp_dst, dst)


def _excel_has_file_open(abspath: str) -> str:
    """Check whether Excel currently has `abspath` open.

    Returns 'open', 'closed', or 'undetermined'. Fails closed ('undetermined')
    when AppleScript cannot answer — a silent pass would risk opening the same
    path in a second Excel instance.
    """
    script = (
        'tell application "Microsoft Excel"\n'
        "  set names to get name of every workbook\n"
        "end tell\n"
        "return names as text")
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return "undetermined"
        base = os.path.basename(abspath).lower()
        if base in [n.strip().lower() for n in out.stdout.replace(", ", ",").split(",")]:
            return "open"
        return "closed"
    except Exception:
        return "undetermined"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("draft", nargs="?", help="draft .xlsx to validate")
    parser.add_argument("--baseline")
    parser.add_argument("--target", action="append", default=[], metavar="SHEET!CELL")
    parser.add_argument("--render", action="append", default=[], metavar="SHEET!RANGE")
    parser.add_argument("--render-sheet", action="append", default=[], metavar="SHEET")
    parser.add_argument("--chart", action="append", default=[], metavar="SHEET!INDEX",
                        help="rejected at preflight: chart PNG export is unimplemented on macOS")
    parser.add_argument("--output-dir")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--_worker", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args._worker:
        # SIGTERM triggers SystemExit so the worker's finally blocks (app.quit)
        # still run when the parent enforces its timeout.
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
        with open(args._worker) as f:
            payload = json.load(f)
        try:
            excel_worker(payload["draft"], payload["render_ranges"],
                         payload["out_dir"], payload["result_path"])
            return 0
        except SystemExit:
            raise
        except Exception as e:
            import traceback
            with open(payload["result_path"], "w") as f:
                json.dump({"error": str(e), "traceback": traceback.format_exc()[-4000:]}, f)
            return 1

    if args.chart:
        parser.error("--chart is not supported on macOS (xlwings Chart.to_png unimplemented); "
                     "use --render/--render-sheet ranges that cover the chart area")

    if not args.draft:
        parser.error("draft path is required")

    out_dir = args.output_dir or os.path.dirname(os.path.abspath(args.draft))
    os.makedirs(out_dir, exist_ok=True)

    render_specs = list(args.render)
    for sheet_name in args.render_sheet:
        render_specs.append(f"{sheet_name}!A1:{_used_range_end(args.draft, sheet_name)}")

    report = run_gate(args.draft, args.baseline, args.target, render_specs, out_dir, args.timeout)
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("ok") else 1


def _used_range_end(path: str, sheet_name: str) -> str:
    """Pre-recalc used range (openpyxl dimension). For new workbooks this is
    authoritative; after edits, prefer explicit --render ranges derived from
    asp sheet bounds, since recalculation can extend the used range."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    wb = load_workbook(path, read_only=True)
    try:
        ws = wb[sheet_name]
        max_row = ws.max_row or 1
        max_col = ws.max_column or 1
    finally:
        wb.close()
    return f"{get_column_letter(max_col)}{max_row}"


if __name__ == "__main__":
    sys.exit(main())
