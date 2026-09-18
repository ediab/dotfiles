#!/usr/bin/env python3
"""Read-only inspection, comparison and evidence checking for supplied workbooks.

This script never writes to a workbook. It reads OOXML with openpyxl and reports
observations: counts, locations and cached values. An observation is not a
statement about financial correctness, and a cached value does not prove that
the function producing it still works.

Modes
-----
inspect  WORKBOOK  [--out record.json] [--mapping map.json] [--max-items N]
    Inventory sheets, formulas, stored errors, external links, defined names,
    hidden content, calculation mode, provider-function traces and unsupported
    features. Prints a readable summary; writes a bounded JSON record.

checks   WORKBOOK  [--out record.json] [--max-items N]
    Mechanical, reproducible checks on a recalculated copy: error cells with
    their formulas, formulas that break the pattern of their contiguous
    neighbours, formulas carrying numeric literals, and cells that subtract one
    area from another (tie-outs) with their cached values. Findings are
    candidates for analyst judgement - a tie-out that holds is reported as
    clean, and constants in input rows are inputs, not defects.

diff     BEFORE AFTER [--out record.json] [--max-items N]
    Compare two workbooks (typically baseline vs edited copy) at sheet, name,
    formula, cached-value and error level. A->B shows environment drift, B->C
    shows the effect of approved edits.

guard    --workbook COPY --expect SHA256
    Mechanical input-hash check. Exit 1 when the file is not the inspected and
    approved artifact. Run this before every edit.

verify   --workbook WORKBOOK --evidence evidence.json
    Check that figures cited elsewhere (memo, change log) still agree with the
    delivered workbook's cached values. Exit 1 on any mismatch.

Usage: .venv/bin/python scripts/inspect_workbook.py <mode> ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

ERROR_VALUES = {
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
}

# Provider/terminal functions and caches. Heuristic: a hit is a dependency to
# investigate, never proof that the function works now.
PROVIDER_TOKENS = (
    "FDS",
    "FDSCODE",
    "FDSFUNCTION",
    "BDP",
    "BDH",
    "BDS",
    "BDE",
    "EIKON",
    "TR(",
    "CIQ",
    "IQ_",
    "SPGLOBAL",
    "CAPITALIQ",
    "FACTSET",
    "BLOOMBERG",
    "REFINITIV",
    "VISIBLEALPHA",
)
PROVIDER_CACHE_SHEETS = re.compile(r"^__|CACHE", re.IGNORECASE)

# OOXML parts whose presence changes what can be audited from formulas alone.
PART_FEATURES = {
    "xl/vbaProject.bin": "VBA project (macros) - not auditable from formulas",
    "xl/connections.xml": "external data connections",
    "xl/pivotCache/": "pivot caches",
    "xl/pivotTables/": "pivot tables",
    "xl/chartsheets/": "chart sheets",
    "xl/slicers/": "slicers",
    "xl/timelines/": "timelines",
    "customXml/": "custom XML parts",
    "xl/embeddings/": "embedded objects (OLE)",
    "xl/threadedComments/": "threaded comments",
    "xl/externalLinks/": "external links",
    "xl/queryTables/": "query tables",
    "xl/drawings/": "drawings/images",
    "xl/media/": "embedded media",
}


def jsonable(value):
    """Make a cell value JSON-serialisable and comparable without changing meaning.

    Array formulas arrive as objects whose repr contains a memory address, which
    would make two identical cells look different; compare their formula text.
    """
    if isinstance(value, (datetime, date, time, timedelta)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    text = getattr(value, "text", None)
    if isinstance(text, str) and text.startswith("="):
        return text
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_error_value(value) -> bool:
    return isinstance(value, str) and value.strip() in ERROR_VALUES


def zip_parts(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    except zipfile.BadZipFile:
        return []


def raw_part_text(path: Path, wanted: str) -> str:
    """Return the concatenated text of archive members whose name matches."""
    try:
        with zipfile.ZipFile(path) as archive:
            return "\n".join(
                archive.read(name).decode("utf-8", "replace")
                for name in archive.namelist()
                if name.startswith(wanted) and name.endswith(".xml")
            )
    except zipfile.BadZipFile:
        return ""


def workbook_properties(path: Path) -> dict:
    """Read calcPr, sheets, names and external references from the raw XML."""
    text = raw_part_text(path, "xl/workbook.xml")
    calc_match = re.search(r"<calcPr\b([^>]*)/?>", text)
    calc_attrs = {}
    if calc_match:
        calc_attrs = dict(re.findall(r'(\w+)="([^"]*)"', calc_match.group(1)))
    sheets = [
        {"name": m.group(1), "sheet_id": m.group(2), "state": m.group(3) or "visible"}
        for m in re.finditer(
            r'<sheet\b[^>]*name="([^"]*)"[^>]*sheetId="([^"]*)"[^>]*?(?:state="([^"]*)")?[^>]*/>', text
        )
    ]
    names = []
    for block in re.finditer(r"<definedName\b([^>]*)>(.*?)</definedName>", text, re.S):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', block.group(1)))
        names.append(
            {
                "name": attrs.get("name", ""),
                "scope": attrs.get("localSheetId", "workbook"),
                "hidden": attrs.get("hidden", "0") == "1",
                "refers_to": block.group(2),
            }
        )
    return {
        "calculation": {
            "calc_mode": calc_attrs.get("calcMode", "auto"),
            "full_calc_on_load": calc_attrs.get("fullCalcOnLoad", "0") == "1",
            "iterate": calc_attrs.get("iterate", "0") == "1",
            "calc_id": calc_attrs.get("calcId", ""),
        },
        "sheets": sheets,
        "defined_names": names,
        "external_reference_count": len(re.findall(r"<externalReference\b", text)),
    }


def sheet_facts(ws, cached_ws) -> dict:
    formulas = 0
    formula_sample: list[dict] = []
    constants = 0
    stored_errors: list[dict] = []
    provider_hits: set[str] = set()

    for row in ws.iter_rows():
        for cell in row:
            value = cell.value
            if value is None:
                continue
            if isinstance(value, str) and value.startswith("="):
                formulas += 1
                if len(formula_sample) < 25:
                    formula_sample.append({"cell": cell.coordinate, "formula": value})
                upper = value.upper()
                for token in PROVIDER_TOKENS:
                    if token in upper:
                        provider_hits.add(token)
            else:
                constants += 1

    if cached_ws is not None:
        for row in cached_ws.iter_rows():
            for cell in row:
                if is_error_value(cell.value):
                    stored_errors.append({"cell": cell.coordinate, "error": cell.value.strip()})

    hidden_rows = sum(1 for idx, dim in ws.row_dimensions.items() if dim.hidden)
    hidden_cols = sum(1 for dim in ws.column_dimensions.values() if dim.hidden)
    tables = list(getattr(ws, "tables", {}) or {})
    sheet_xml = raw_part_text_of_sheet(ws)
    data_tables = sheet_xml.count("<dataTable")

    return {
        "title": ws.title,
        "state": ws.sheet_state,
        "dimensions": ws.calculate_dimension(),
        "formula_count": formulas,
        "constant_count": constants,
        "formula_sample": formula_sample,
        "stored_error_count": len(stored_errors),
        "stored_errors": stored_errors[:50],
        "hidden_rows": hidden_rows,
        "hidden_columns": hidden_cols,
        "data_validations": len(ws.data_validations.dataValidation),
        "conditional_formats": len(list(ws.conditional_formatting)),
        "charts": len(getattr(ws, "_charts", [])),
        "images": len(getattr(ws, "_images", [])),
        "tables": [getattr(t, "displayName", str(t)) for t in tables],
        "merged_cells": len(ws.merged_cells.ranges),
        "comments": sum(1 for row in ws.iter_rows() for c in row if c.comment),
        "data_table_blocks": data_tables,
        "provider_tokens": sorted(provider_hits),
    }


_SHEET_XML_CACHE: dict[str, str] = {}


def raw_part_text_of_sheet(ws) -> str:
    """Best-effort raw XML for a worksheet, cached per path."""
    parent = getattr(ws, "parent", None)
    path = getattr(parent, "_inv_path", None)
    if path is None:
        return ""
    if path not in _SHEET_XML_CACHE:
        _SHEET_XML_CACHE[path] = raw_part_text(Path(path), "xl/worksheets/")
    return _SHEET_XML_CACHE[path]


# Drawing parts written by Excel can fail strict XML parsing (observed in a
# supplied broker workbook: `<a16:creationId ... xmlns:id="{guid}" />`, where the
# namespace value is a GUID rather than a URI). Excel tolerates it; Expat does
# not, and it aborts the whole workbook read. Formulas, names, values and errors
# are unaffected, so the drawing/image part is skipped and *reported* rather than
# failing the inspection.
PARSE_WARNINGS: list[str] = []


def load_workbook_tolerant(path: Path, data_only: bool):
    from openpyxl.reader import excel as excel_reader

    original = excel_reader.find_images

    def skip_unparsable_drawings(archive, target):
        try:
            return original(archive, target)
        except ET.ParseError as exc:
            PARSE_WARNINGS.append(
                f"drawing part {target} is not namespace-well-formed ({exc}); "
                "images/shapes not inspected"
            )
            return [], []

    excel_reader.find_images = skip_unparsable_drawings
    try:
        return load_workbook(path, data_only=data_only)
    finally:
        excel_reader.find_images = original


def load_pair(path: Path):
    formulas_wb = load_workbook_tolerant(path, data_only=False)
    cached_wb = load_workbook_tolerant(path, data_only=True)
    # openpyxl does not expose the source path; keep it for raw-part lookups.
    formulas_wb._inv_path = str(path)
    cached_wb._inv_path = str(path)
    return formulas_wb, cached_wb


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.workbook).resolve()
    if not path.exists():
        print(f"workbook not found: {path}", file=sys.stderr)
        return 2
    parts = zip_parts(path)
    record: dict = {
        "mode": "inspect",
        "workbook": path.name,
        "path": str(path),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "sheet_count": None,
        "features": [],
        "unsupported_features": [],
    }
    record["features"] = sorted(
        {label for prefix, label in PART_FEATURES.items() if any(p.startswith(prefix) for p in parts)}
    )
    record["unsupported_features"] = [
        label for label in record["features"] if label != "external links"
    ]
    record["parts"] = {
        "vba_project": any(p == "xl/vbaProject.bin" for p in parts),
        "custom_xml": any(p.startswith("customXml/") for p in parts),
        "pivot_caches": sum(1 for p in parts if p.startswith("xl/pivotCache/")),
        "external_link_parts": sum(1 for p in parts if p.startswith("xl/externalLinks/")),
    }
    record.update(workbook_properties(path))

    formulas_wb, cached_wb = load_pair(path)
    record["parse_warnings"] = sorted(set(PARSE_WARNINGS))
    record["sheet_count"] = len(formulas_wb.worksheets)
    record["hidden_sheets"] = [ws.title for ws in formulas_wb.worksheets if ws.sheet_state != "visible"]
    record["provider_cache_sheets"] = [
        ws.title for ws in formulas_wb.worksheets if PROVIDER_CACHE_SHEETS.search(ws.title)
    ]
    external_targets = []
    for link in getattr(formulas_wb, "_external_links", []) or []:
        target = getattr(getattr(link, "file_link", None), "Target", None)
        if target:
            external_targets.append(target)
    record["external_link_targets"] = external_targets

    sheets = []
    for ws in formulas_wb.worksheets:
        cached_ws = cached_wb[ws.title] if ws.title in cached_wb.sheetnames else None
        facts = sheet_facts(ws, cached_ws)
        if facts["formula_sample"] and len(facts["formula_sample"]) > args.max_items:
            facts["formula_sample"] = facts["formula_sample"][: args.max_items]
            facts["formula_sample_truncated"] = True
        if len(facts["stored_errors"]) > args.max_items:
            facts["stored_errors"] = facts["stored_errors"][: args.max_items]
            facts["stored_errors_truncated"] = True
        sheets.append(facts)
    record["sheets"] = sheets
    record["totals"] = {
        "formulas": sum(s["formula_count"] for s in sheets),
        "constants": sum(s["constant_count"] for s in sheets),
        "stored_errors": sum(s["stored_error_count"] for s in sheets),
        "data_table_blocks": sum(s["data_table_blocks"] for s in sheets),
    }
    # Defined names are summarised before truncation: a workbook can carry
    # thousands of inherited names, and the count matters more than the list.
    record["defined_names_total"] = len(record["defined_names"])
    record["defined_names_summary"] = {
        "total": len(record["defined_names"]),
        "broken_ref": sum(1 for n in record["defined_names"] if "#REF" in n["refers_to"]),
        "points_at_other_workbook": sum(
            1 for n in record["defined_names"] if re.search(r"\[\d+\]", n["refers_to"])
        ),
        "hidden": sum(1 for n in record["defined_names"] if n["hidden"]),
    }
    if record["defined_names_total"] > args.max_items:
        record["defined_names_truncated"] = record["defined_names_total"] - args.max_items
        record["defined_names"] = record["defined_names"][: args.max_items]
    if args.mapping:
        record["assignment_mapping"] = json.loads(Path(args.mapping).read_text())
        record["assignment_mapping_file"] = Path(args.mapping).name

    if args.out:
        Path(args.out).write_text(json.dumps(record, indent=2, default=str) + "\n")
        print(f"record written: {args.out}")

    calc = record["calculation"]
    print(f"workbook: {record['workbook']}  sha256={record['sha256'][:16]}...")
    for warning in record["parse_warnings"]:
        print(f"WARNING  {warning}")
    print(f"sheets: {record['sheet_count']}  hidden: {record['hidden_sheets'] or 'none'}")
    print(
        f"calculation: {calc['calc_mode']}"
        f"{' fullCalcOnLoad' if calc['full_calc_on_load'] else ''}"
        f"{' iterate(circular)' if calc['iterate'] else ''}"
    )
    print(
        f"totals: {record['totals']['formulas']} formulas, "
        f"{record['totals']['constants']} constants, "
        f"{record['totals']['stored_errors']} stored error cells, "
        f"{record['totals']['data_table_blocks']} data-table blocks"
    )
    names_summary = record["defined_names_summary"]
    print(
        f"defined names: {names_summary['total']}"
        f" (broken #REF!: {names_summary['broken_ref']},"
        f" pointing at other workbooks: {names_summary['points_at_other_workbook']},"
        f" hidden: {names_summary['hidden']})"
        f"  external links: {len(external_targets)}"
    )
    if external_targets:
        for target in external_targets[:10]:
            print(f"  link -> {target}")
    if record["provider_cache_sheets"]:
        print(f"provider cache sheets: {record['provider_cache_sheets']}")
    provider_tokens = sorted({t for s in sheets for t in s["provider_tokens"]})
    if provider_tokens:
        print(f"provider function tokens in formulas: {provider_tokens}")
    if record["features"]:
        print(f"notable parts: {record['features']}")
    for sheet in sheets:
        print(
            f"  [{sheet['title']}] {sheet['formula_count']} formulas, "
            f"{sheet['constant_count']} constants, {sheet['stored_error_count']} errors, "
            f"hidden rows {sheet['hidden_rows']}/cols {sheet['hidden_columns']}, "
            f"dv {sheet['data_validations']}, cf {sheet['conditional_formats']}, "
            f"charts {sheet['charts']}"
        )
        for err in sheet["stored_errors"][:5]:
            print(f"      error {sheet['title']}!{err['cell']} = {err['error']}")
    print("counts are observations, not a correctness judgement")
    return 0


def cell_map(path: Path) -> tuple[dict, dict]:
    """Return (formulas, cached_values) keyed sheet!cell."""
    formulas_wb, cached_wb = load_pair(path)
    fmap: dict[str, str] = {}
    vmap: dict[str, object] = {}
    for ws in formulas_wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    fmap[f"{ws.title}!{cell.coordinate}"] = jsonable(cell.value)
    for ws in cached_wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    vmap[f"{ws.title}!{cell.coordinate}"] = jsonable(cell.value)
    return fmap, vmap


REF_RE = re.compile(r"(?<![A-Za-z0-9_$!])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])")
LITERAL_RE = re.compile(r"(?<![A-Za-z0-9_$.])(\d+(?:\.\d+)?)(?![A-Za-z0-9_])")
TIE_OUT_RE = re.compile(
    r"^=\s*\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?\s*-\s*"
    r"(SUM\([^)]*\)|\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)"
    r"(\s*\*\s*[\d.]+)?$",
    re.IGNORECASE,
)


def normalize_formula(formula: str, row: int, col: int) -> str:
    """Replace A1 references by their position relative to the cell.

    Two cells whose formulas differ only by the row they sit on normalise to the
    same string, so a run of neighbours that share one operation can be told
    apart from a cell that breaks the pattern. Absolute references stay absolute.
    """

    def repl(match: re.Match) -> str:
        abs_col, col_letters, abs_row, row_digits = match.groups()
        col_index = column_index_from_string(col_letters)
        if abs_col and abs_row:
            return "$ABS$"
        if abs_col:
            return f"$C{col_letters}{int(row_digits) - row:+d}"
        if abs_row:
            return f"$R{row_digits}C{col_index - col:+d}"
        return f"R{int(row_digits) - row:+d}C{col_index - col:+d}"

    return REF_RE.sub(repl, formula)


def cmd_checks(args: argparse.Namespace) -> int:
    path = Path(args.workbook).resolve()
    if not path.exists():
        print(f"workbook not found: {path}", file=sys.stderr)
        return 2
    formulas_wb, cached_wb = load_pair(path)
    findings: list[dict] = []

    for ws in formulas_wb.worksheets:
        cached_ws = cached_wb[ws.title] if ws.title in cached_wb.sheetnames else None
        formula_cells: dict[int, list[tuple[int, str]]] = {}
        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                if not (isinstance(value, str) and value.startswith("=")):
                    continue
                cached = cached_ws[cell.coordinate].value if cached_ws is not None else None
                if is_error_value(cached):
                    findings.append(
                        {
                            "category": "error",
                            "sheet": ws.title,
                            "cell": cell.coordinate,
                            "formula": value,
                            "value": cached,
                        }
                    )
                for literal in LITERAL_RE.findall(value):
                    if literal not in {"0", "1", "2", "100"}:
                        findings.append(
                            {
                                "category": "formula_literal",
                                "sheet": ws.title,
                                "cell": cell.coordinate,
                                "formula": value,
                                "literal": literal,
                                "note": "numeric literal inside a formula - confirm it is a convention, not an input",
                            }
                        )
                if TIE_OUT_RE.match(value):
                    status = "unknown"
                    if cached is not None and not is_error_value(cached):
                        try:
                            status = "ok" if abs(float(cached)) < 1e-9 else "failed"
                        except (TypeError, ValueError):
                            status = "unknown"
                    findings.append(
                        {
                            "category": "tie_out",
                            "sheet": ws.title,
                            "cell": cell.coordinate,
                            "formula": value,
                            "value": cached,
                            "status": status,
                        }
                    )
                formula_cells.setdefault(cell.column, []).append((cell.row, value))

        for col, entries in sorted(formula_cells.items()):
            entries.sort()
            run: list[tuple[int, str]] = []
            for entry in entries + [(None, None)]:
                if run and (entry[0] is None or entry[0] != run[-1][0] + 1):
                    if len(run) >= 3:
                        shapes = [
                            normalize_formula(formula, row, col) for row, formula in run
                        ]
                        dominant = max(set(shapes), key=shapes.count)
                        if shapes.count(dominant) < len(shapes):
                            for (row, formula), shape in zip(run, shapes):
                                if shape != dominant:
                                    findings.append(
                                        {
                                            "category": "inconsistent_formula",
                                            "sheet": ws.title,
                                            "cell": f"{get_column_letter(col)}{row}",
                                            "formula": formula,
                                            "neighbour_pattern": dominant,
                                            "note": "breaks the pattern of its contiguous neighbours in this column",
                                        }
                                    )
                    run = []
                if entry[0] is not None:
                    run.append(entry)

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["category"]] = counts.get(finding["category"], 0) + 1
    record = {
        "mode": "checks",
        "workbook": path.name,
        "path": str(path),
        "sha256": sha256(path),
        "counts": counts,
        "findings": findings[: args.max_items],
    }
    if len(findings) > len(record["findings"]):
        record["findings_truncated"] = len(findings) - len(record["findings"])
    if args.out:
        Path(args.out).write_text(json.dumps(record, indent=2, default=str) + "\n")
        print(f"record written: {args.out}")

    print(f"workbook: {path.name}  sha256={record['sha256'][:16]}...")
    if not findings:
        print("no mechanical findings (not a clean bill of health - see audit skill step 4)")
    for finding in record["findings"]:
        sheet, cell = finding["sheet"], finding["cell"]
        if finding["category"] == "error":
            print(f"  ERROR        {sheet}!{cell}  {finding['value']}  {finding['formula']}")
        elif finding["category"] == "tie_out":
            print(
                f"  TIE-OUT {finding['status']:<7} {sheet}!{cell}  value={finding['value']}  {finding['formula']}"
            )
        elif finding["category"] == "inconsistent_formula":
            print(
                f"  INCONSISTENT {sheet}!{cell}  {finding['formula']}"
                f"  (neighbours: {finding['neighbour_pattern']})"
            )
        else:
            print(f"  LITERAL      {sheet}!{cell}  literal={finding['literal']}  {finding['formula']}")
    if record.get("findings_truncated"):
        print(f"  ... {record['findings_truncated']} further findings not listed")
    print(f"counts: {counts or '{}'}")
    print("mechanical candidates only: confirm each against the model before reporting severity")
    return 1 if counts.get("error") else 0


def cmd_diff(args: argparse.Namespace) -> int:
    before = Path(args.before).resolve()
    after = Path(args.after).resolve()
    b_formulas, b_values = cell_map(before)
    a_formulas, a_values = cell_map(after)
    b_props = workbook_properties(before)
    a_props = workbook_properties(after)

    def stored_kind(before_content, after_content) -> str:
        """Classify a change in what a cell stores: formula text, constant, or both."""
        before_formula = isinstance(before_content, str) and before_content.startswith("=")
        after_formula = isinstance(after_content, str) and after_content.startswith("=")
        if before_formula and after_formula:
            return "formula"
        if before_formula and not after_formula:
            return "formula_to_constant"
        if after_formula and not before_formula:
            return "constant_to_formula"
        return "constant"

    changes: list[dict] = []
    for key in sorted(set(b_formulas) | set(a_formulas)):
        before_content = b_formulas.get(key)
        after_content = a_formulas.get(key)
        if before_content != after_content:
            changes.append(
                {
                    "sheet_cell": key,
                    "kind": stored_kind(before_content, after_content),
                    "before": before_content,
                    "after": after_content,
                }
            )
    for key in sorted(set(b_values) | set(a_values)):
        before_value = b_values.get(key)
        after_value = a_values.get(key)
        if before_value != after_value:
            changes.append({"sheet_cell": key, "kind": "value", "before": before_value, "after": after_value})

    errors_before = {k: v for k, v in b_values.items() if is_error_value(v)}
    errors_after = {k: v for k, v in a_values.items() if is_error_value(v)}
    names_before = {n["name"]: n["refers_to"] for n in b_props["defined_names"]}
    names_after = {n["name"]: n["refers_to"] for n in a_props["defined_names"]}
    sheets_before = {s["name"]: s["state"] for s in b_props["sheets"]}
    sheets_after = {s["name"]: s["state"] for s in a_props["sheets"]}

    record = {
        "mode": "diff",
        "before": {"path": str(before), "sha256": sha256(before)},
        "after": {"path": str(after), "sha256": sha256(after)},
        "sheet_states": {
            "added": sorted(set(sheets_after) - set(sheets_before)),
            "removed": sorted(set(sheets_before) - set(sheets_after)),
            "state_changed": {
                s: {"before": sheets_before[s], "after": sheets_after[s]}
                for s in sorted(set(sheets_before) & set(sheets_after))
                if sheets_before[s] != sheets_after[s]
            },
        },
        "names": {
            "added": sorted(set(names_after) - set(names_before)),
            "removed": sorted(set(names_before) - set(names_after)),
            "changed": {
                n: {"before": names_before[n], "after": names_after[n]}
                for n in sorted(set(names_before) & set(names_after))
                if names_before[n] != names_after[n]
            },
        },
        "calculation": {"before": b_props["calculation"], "after": a_props["calculation"]},
        "errors": {
            "before_count": len(errors_before),
            "after_count": len(errors_after),
            "new": sorted(set(errors_after) - set(errors_before)),
            "resolved": sorted(set(errors_before) - set(errors_after)),
        },
        "counts": {
            "formula_changes": sum(1 for c in changes if c["kind"] == "formula"),
            "constant_changes": sum(1 for c in changes if c["kind"] == "constant"),
            "formula_replacement_changes": sum(
                1 for c in changes if c["kind"] in {"formula_to_constant", "constant_to_formula"}
            ),
            "value_changes": sum(1 for c in changes if c["kind"] == "value"),
            "cells_compared_before": len(b_formulas),
            "cells_compared_after": len(a_formulas),
        },
    }
    listed = changes[: args.max_items]
    record["changes"] = listed
    if len(changes) > len(listed):
        record["changes_truncated"] = len(changes) - len(listed)

    if args.out:
        Path(args.out).write_text(json.dumps(record, indent=2, default=str) + "\n")
        print(f"record written: {args.out}")

    print(f"before: {before.name} ({record['before']['sha256'][:16]}...)")
    print(f"after:  {after.name} ({record['after']['sha256'][:16]}...)")
    print(
        f"formula text changes: {record['counts']['formula_changes']}  "
        f"constant changes: {record['counts']['constant_changes']}  "
        f"formula<->constant: {record['counts']['formula_replacement_changes']}  "
        f"cached value changes: {record['counts']['value_changes']}"
    )
    print(
        f"stored errors: {record['errors']['before_count']} -> {record['errors']['after_count']}"
        f"  new: {len(record['errors']['new'])}  resolved: {len(record['errors']['resolved'])}"
    )
    if record["sheet_states"]["added"] or record["sheet_states"]["removed"]:
        print(f"sheets: +{record['sheet_states']['added']} -{record['sheet_states']['removed']}")
    if record["sheet_states"]["state_changed"]:
        print(f"sheet state changes: {record['sheet_states']['state_changed']}")
    if record["names"]["added"] or record["names"]["removed"] or record["names"]["changed"]:
        print(
            f"names: +{record['names']['added']} -{record['names']['removed']} "
            f"changed {sorted(record['names']['changed'])}"
        )
    for change in listed[:20]:
        print(
            f"  {change['kind']:8s} {change['sheet_cell']}: "
            f"{str(change['before'])[:60]!r} -> {str(change['after'])[:60]!r}"
        )
    if record.get("changes_truncated"):
        print(f"  ... {record['changes_truncated']} further changes not listed")
    return 0


def cmd_guard(args: argparse.Namespace) -> int:
    path = Path(args.workbook).resolve()
    if not path.exists():
        print(f"FAIL workbook not found: {path}")
        return 2
    actual = sha256(path)
    if actual == args.expect.strip().lower():
        print(f"PASS {path.name} matches the inspected artifact")
        print(f"     sha256={actual}")
        return 0
    print(f"FAIL {path.name} does not match the inspected artifact")
    print(f"     expected {args.expect.strip().lower()}")
    print(f"     actual   {actual}")
    print("     re-inspect and re-approve before editing this file")
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.workbook).resolve()
    evidence = json.loads(Path(args.evidence).read_text())
    _, values = cell_map(path)
    failures = 0
    checked = 0

    claimed_hash = evidence.get("workbook_sha256")
    if claimed_hash:
        actual = sha256(path)
        if actual != claimed_hash.strip().lower():
            print(f"FAIL workbook hash mismatch: evidence says {claimed_hash[:16]}..., file is {actual[:16]}...")
            failures += 1
        else:
            print(f"PASS workbook hash {actual[:16]}... matches the evidence record")

    for item in evidence.get("items", []):
        key = f"{item.get('sheet')}!{item.get('cell')}"
        expected = item.get("expected")
        actual = values.get(key)
        checked += 1
        label = item.get("label", key)
        if actual is None:
            print(f"FAIL {label} ({key}): no cached value in the workbook")
            failures += 1
            continue
        if is_error_value(actual):
            print(f"FAIL {label} ({key}): workbook holds {actual}")
            failures += 1
            continue
        tolerance = item.get("tolerance")
        if tolerance is None:
            tolerance = max(abs(float(expected)) * 1e-9, 1e-9)
        try:
            difference = abs(float(actual) - float(expected))
        except (TypeError, ValueError):
            print(f"FAIL {label} ({key}): not numeric (workbook {actual!r}, expected {expected!r})")
            failures += 1
            continue
        if difference <= float(tolerance):
            print(f"PASS {label} ({key}): {actual} ({item.get('units', '')})".rstrip())
        else:
            print(
                f"FAIL {label} ({key}): workbook {actual} ({item.get('units', '')})".rstrip()
                + f" vs stated {expected}, difference {difference:g} > tolerance {tolerance}"
            )
            failures += 1

    print(f"{checked} evidence items checked, {failures} failure(s)")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("workbook")
    p_inspect.add_argument("--out")
    p_inspect.add_argument("--mapping")
    p_inspect.add_argument("--max-items", type=int, default=25)
    p_inspect.set_defaults(func=cmd_inspect)

    p_checks = sub.add_parser("checks")
    p_checks.add_argument("workbook")
    p_checks.add_argument("--out")
    p_checks.add_argument("--max-items", type=int, default=500)
    p_checks.set_defaults(func=cmd_checks)

    p_diff = sub.add_parser("diff")
    p_diff.add_argument("before")
    p_diff.add_argument("after")
    p_diff.add_argument("--out")
    p_diff.add_argument("--max-items", type=int, default=200)
    p_diff.set_defaults(func=cmd_diff)

    p_guard = sub.add_parser("guard")
    p_guard.add_argument("--workbook", required=True)
    p_guard.add_argument("--expect", required=True)
    p_guard.set_defaults(func=cmd_guard)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--workbook", required=True)
    p_verify.add_argument("--evidence", required=True)
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"not found: {exc}", file=sys.stderr)
        return 2
    except InvalidFileException as exc:
        print(f"not a readable workbook: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
