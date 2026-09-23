#!/usr/bin/env python3
"""Prepare and replay user-designated, supplied-files-only evidence packs.

Only explicitly mapped facts are accepted. This module does not crawl for numbers or
consult the financial-data-pull store. Hashes establish file identity; each accepted
number also requires a separately recorded review against its locator; the reviewer may be an agent.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".txt", ".md", ".markdown"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _number(token: str) -> float:
    token = _normalise(token).strip()
    negative = token.startswith("(") and token.endswith(")")
    if negative:
        token = token[1:-1].strip()
    token = token.replace(",", "").replace("$", "").replace("%", "").strip()
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", token):
        raise ValueError(f"unsupported numeric token {token!r}")
    value = float(token)
    if negative:
        value = -value
    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric token {token!r}")
    return value


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"head", "script", "style"}:
            self._hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"head", "script", "style"} and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table = -1
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            if self._table >= 0:
                raise ValueError("nested HTML tables need a reviewed passage locator")
            self.tables.append([])
            self._table = len(self.tables) - 1
        elif tag == "tr" and self._table >= 0:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_normalise("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table >= 0:
            self.tables[self._table].append(self._row)
            self._row = None
        elif tag == "table":
            self._table = -1


def _document_text(path: Path, page: int | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise ValueError("PDF support requires the already-installed PyMuPDF (fitz)") from exc
        with fitz.open(path) as document:
            if page is None or page < 1 or page > document.page_count:
                raise ValueError(f"PDF page must be between 1 and {document.page_count}")
            text = document[page - 1].get_text("text")
        if not text.strip():
            raise ValueError(f"PDF page {page} has no extractable text (scanned/unsupported; do not OCR silently)")
        return text
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8")
    if suffix in {".html", ".htm"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"unsupported supplied source format: {suffix or '(no extension)'}")


def _extract(path: Path, locator: dict[str, Any]) -> tuple[float, str, str]:
    """Return value, exact source excerpt, and a canonical human-readable locator."""
    kind = locator.get("kind")
    token = str(locator.get("value_text") or "")
    if not token:
        raise ValueError("locator.value_text must identify the exact numeric token in the source")
    if kind == "html_cell":
        if path.suffix.lower() not in {".html", ".htm"}:
            raise ValueError("html_cell locator requires an HTML source")
        parser = _TableParser()
        parser.feed(path.read_text(encoding="utf-8"))
        table, row, col = (locator.get(key) for key in ("table", "row", "column"))
        if not all(isinstance(value, int) and value >= 0 for value in (table, row, col)):
            raise ValueError("html_cell requires zero-based integer table, row and column")
        try:
            excerpt = parser.tables[table][row][col]
        except IndexError as exc:
            raise ValueError(f"HTML table cell does not exist: table={table}, row={row}, column={col}") from exc
        if _normalise(token) not in excerpt:
            raise ValueError(f"source token {token!r} is not present in cited HTML cell {excerpt!r}")
        locator_text = f"table={table};row={row};cell={col}"
    elif kind in {"pdf_page", "text_passage", "html_passage"}:
        if kind == "pdf_page" and path.suffix.lower() != ".pdf":
            raise ValueError("pdf_page locator requires a PDF source")
        if kind == "text_passage" and path.suffix.lower() not in {".txt", ".md", ".markdown"}:
            raise ValueError("text_passage locator requires plain text or Markdown")
        if kind == "html_passage" and path.suffix.lower() not in {".html", ".htm"}:
            raise ValueError("html_passage locator requires HTML")
        page = locator.get("page") if kind == "pdf_page" else None
        if kind == "pdf_page" and (not isinstance(page, int) or page < 1):
            raise ValueError("pdf_page requires a one-based page number")
        source_text = _document_text(path, page)
        if kind == "html_passage":
            visible = _VisibleTextParser()
            visible.feed(source_text)
            source_text = " ".join(visible.parts)
        quote = str(locator.get("quote") or "")
        if not quote:
            raise ValueError("passage locator requires an exact quote")
        normalized_source = _normalise(source_text)
        normalized_quote = _normalise(quote)
        if not normalized_quote or normalized_quote not in normalized_source:
            raise ValueError("quoted passage does not match the cited original")
        if normalized_source.count(normalized_quote) != 1:
            raise ValueError("quoted passage is ambiguous within the cited page/document")
        if token not in normalized_quote:
            raise ValueError("value_text must occur in the exact quoted passage")
        excerpt = normalized_quote
        if kind == "text_passage":
            lines = source_text.splitlines()
            start, end = locator.get("line_start"), locator.get("line_end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > len(lines):
                raise ValueError("text_passage requires valid one-based line_start and line_end")
            cited = _normalise("\n".join(lines[start - 1:end]))
            if cited != normalized_quote:
                raise ValueError("quoted passage does not exactly match the declared line range")
            locator_text = f"lines={start}-{end}"
        elif kind == "pdf_page":
            locator_text = f"page={page};quote={normalized_quote}"
        else:
            locator_text = f"passage={normalized_quote}"
    else:
        raise ValueError(f"unsupported or missing locator kind: {kind!r}")

    matches = re.findall(r"(?<![\w.])\(?[+-]?(?:\d{1,3}(?:,\d{3})+|\d+|\.\d+)(?:\.\d+)?\)?%?(?![\w]|\.\d)", excerpt)
    exact = [candidate for candidate in matches if _normalise(candidate) == _normalise(token)]
    if len(exact) != 1:
        raise ValueError(f"numeric token {token!r} is not unique in the cited source excerpt")
    return _number(token), excerpt, locator_text


def _validate_document(item: dict[str, Any], root: Path) -> tuple[Path, dict[str, str]]:
    required = ("id", "file", "issuer", "document_type", "document_date")
    if not all(isinstance(item.get(key), str) and item[key].strip() for key in required):
        raise ValueError(f"document requires non-empty {', '.join(required)}")
    source = Path(item["file"])
    source = source if source.is_absolute() else root / source
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"supplied source is not a regular file: {source}")
    try:
        source.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"designated source escapes supplied-files folder: {item['file']}") from exc
    try:
        date.fromisoformat(item["document_date"])
    except ValueError as exc:
        raise ValueError(f"document_date must be ISO YYYY-MM-DD: {item['document_date']}") from exc
    metadata = {key: item[key] for key in required if key != "file"}
    return source, metadata


def prepare_supplied_pack(folder: Path, destination: Path, designation: dict[str, Any]) -> dict[str, Any]:
    """Copy designated originals, verify explicitly mapped facts, and freeze a dated pack.

    `designation` contains `pack_date`, `documents`, `facts`, and optional `gaps`. Each
    fact contains metric/period/units/basis/document_id/locator and a `review` record
    with reviewer, reviewed_at, independently_read_value and notes.
    """
    folder, destination = Path(folder).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f"immutable supplied-evidence pack already exists: {destination}")
    try:
        date.fromisoformat(str(designation.get("pack_date", "")))
    except ValueError as exc:
        raise ValueError("pack_date must be ISO YYYY-MM-DD") from exc
    docs = designation.get("documents")
    facts = designation.get("facts")
    if not isinstance(docs, list) or not docs or not isinstance(facts, list):
        raise ValueError("designation requires a non-empty documents list and a facts list")
    destination.mkdir(parents=True)
    source_dir = destination / "sources"
    source_dir.mkdir()
    documents: dict[str, dict[str, Any]] = {}
    gaps = list(designation.get("gaps", []))
    try:
        for item in docs:
            if not isinstance(item, dict):
                raise ValueError("each document designation must be an object")
            source, metadata = _validate_document(item, folder)
            if item["id"] in documents:
                raise ValueError(f"duplicate supplied document id {item['id']!r}")
            suffix = source.suffix.lower()
            digest = sha256_file(source)
            if suffix not in SUPPORTED_SUFFIXES:
                gaps.append({"source": item["id"], "reason": f"unsupported format {suffix or '(none)'}"})
            elif suffix == ".pdf":
                # Inventory every PDF page; scanned/empty pages are explicit gaps.
                try:
                    import fitz
                    with fitz.open(source) as pdf:
                        for page_index in range(pdf.page_count):
                            if not pdf[page_index].get_text("text").strip():
                                gaps.append({"source": item["id"], "reason": f"page {page_index + 1} has no searchable text"})
                except Exception as exc:
                    gaps.append({"source": item["id"], "reason": f"PDF cannot be inspected: {exc}"})
            stored_name = f"{digest}{suffix}"
            stored_path = source_dir / stored_name
            shutil.copyfile(source, stored_path)
            if sha256_file(stored_path) != digest:
                raise ValueError(f"source changed while being copied: {item['id']}")
            documents[item["id"]] = {**metadata, "original_name": source.name,
                "sha256": digest, "path": f"sources/{stored_name}", "format": suffix}

        output_facts = []
        unavailable_facts = []
        seen = set()
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError("each fact designation must be an object")
            required = ("metric", "period", "units", "basis", "document_id", "locator", "review")
            if not all(key in fact for key in required):
                raise ValueError(f"fact requires fields {', '.join(required)}")
            if not all(isinstance(fact.get(name), str) and fact[name].strip()
                       for name in ("metric", "period", "units", "basis", "document_id")):
                raise ValueError("fact metric, period, units, basis and document_id must be non-empty strings")
            kind = fact.get("kind", "actual")
            if kind not in {"actual", "benchmark"}:
                raise ValueError(f"unsupported supplied fact kind {kind!r}")
            key = (fact["metric"], fact["period"], fact.get("dimension", ""), kind)
            if key in seen:
                raise ValueError(f"duplicate supplied fact identity {key}")
            seen.add(key)
            document = documents.get(fact["document_id"])
            if document is None:
                raise ValueError(f"fact references undesignated document {fact['document_id']!r}")
            source_path = destination / document["path"]
            try:
                value, excerpt, locator_text = _extract(source_path, fact["locator"])
                review = fact["review"]
                if not isinstance(review, dict) or not all(isinstance(review.get(name), str) and review[name].strip()
                        for name in ("reviewer", "reviewed_at", "independently_read_value", "notes")):
                    raise ValueError(f"{fact['metric']} {fact['period']}: review needs reviewer, reviewed_at, independently_read_value and notes")
                try:
                    reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"{fact['metric']} {fact['period']}: reviewed_at must be ISO datetime") from exc
                reviewed_value = _number(review["independently_read_value"])
                if not math.isclose(value, reviewed_value, rel_tol=1e-10, abs_tol=1e-10):
                    raise ValueError(f"{fact['metric']} {fact['period']}: independent review disagrees with original")
                if not (re.fullmatch(r"\d{4}Q[1-4]", fact["period"])
                        or re.fullmatch(r"\d{4}-FY", fact["period"])
                        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", fact["period"])):
                    raise ValueError(f"invalid fact period {fact['period']!r}")
                output_facts.append({**{key: fact.get(key) for key in ("metric", "period", "units", "basis", "dimension")},
                    "value": value, "kind": kind, "document_id": fact["document_id"],
                    "as_of_date": fact.get("as_of_date", document["document_date"] if kind == "benchmark" else ""),
                    "locator": {**fact["locator"], "resolved": locator_text, "quoted_excerpt": excerpt},
                    "review": {**review, "reviewed_at": reviewed_at.isoformat(), "independently_read_value": reviewed_value},
                    "source_sha256": document["sha256"], "lineage_path": document["path"]})
            except (ValueError, TypeError, KeyError) as exc:
                gap = {"metric": fact.get("metric", "unknown"), "period": fact.get("period", "unknown"),
                       "dimension": fact.get("dimension") or "", "kind": kind,
                       "source": fact.get("document_id", "unknown"), "reason": str(exc)}
                gaps.append(gap)
                if kind == "actual" and re.fullmatch(r"\d{4}Q[1-4]|\d{4}-FY", fact["period"]):
                    unavailable_facts.append({**fact, "missing_reason": gap["reason"]})

        manifest = {"schema_version": 1, "mode": "supplied-files-only", "pack_date": designation["pack_date"],
            "documents": documents, "facts": output_facts, "gaps": gaps,
            "verification_coverage": {"accepted_facts": len(output_facts), "reviewed_facts": len(output_facts),
                                      "gaps": len(gaps)}}
        (destination / "supplied_evidence.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        _write_csv(destination / "actuals.csv", [fact for fact in output_facts if fact["kind"] == "actual"],
                   unavailable=unavailable_facts)
        _write_csv(destination / "benchmarks.csv", [fact for fact in output_facts if fact["kind"] == "benchmark"], benchmark=True)
        verification = {**manifest["verification_coverage"], "gap_details": gaps}
        (destination / "verification.json").write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n")
        return manifest
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def _write_csv(path: Path, facts: list[dict[str, Any]], benchmark: bool = False,
               unavailable: list[dict[str, Any]] | None = None) -> None:
    fields = (["metric", "period", "value", "units", "basis", "dimension", "transform", "source", "as_of_date",
               "analyst_count", "range_low", "range_high", "locator", "lineage_scheme", "lineage_path", "lineage_key", "notes"]
              if benchmark else ["metric", "period", "value", "units", "basis", "dimension", "transform", "locator",
               "lineage_scheme", "lineage_path", "lineage_key", "provenance_status", "notes"])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for fact in facts:
            locator = json.dumps(fact["locator"], sort_keys=True, separators=(",", ":"))
            row = {"metric": fact["metric"], "period": fact["period"], "value": fact["value"],
                   "units": fact["units"], "basis": fact["basis"], "dimension": fact.get("dimension") or "",
                   "transform": "direct", "locator": locator, "lineage_scheme": "supplied_document",
                   "lineage_path": fact["lineage_path"],
                   "lineage_key": f"sha256={fact['source_sha256']};reviewer={fact['review']['reviewer']};reviewed_at={fact['review']['reviewed_at']}",
                   "provenance_status": "verified", "notes": fact["review"]["notes"]}
            if benchmark:
                row.update(source=fact["document_id"], as_of_date=fact.get("as_of_date") or fact["period"], analyst_count="", range_low="",
                           range_high="", provenance_status=None)
                row.pop("provenance_status", None)
            writer.writerow({key: row.get(key, "") for key in fields})
        for fact in unavailable or []:
            writer.writerow({"metric": fact["metric"], "period": fact["period"],
                             "units": fact["units"], "basis": fact["basis"],
                             "dimension": fact.get("dimension") or "", "transform": "direct",
                             "provenance_status": "unavailable", "notes": fact["missing_reason"]})


def replay_supplied_evidence(spec: dict, actual_rows: list[dict[str, str]],
                             benchmark_rows: list[dict[str, str]] | None = None) -> dict[str, int]:
    """Re-extract every populated canonical fact and compare its reviewed record and frozen row."""
    boundary = spec.get("source_boundary")
    if not isinstance(boundary, dict) or boundary.get("mode") != "supplied-files-only":
        raise ValueError("source_boundary.mode must be supplied-files-only")
    if any(key in boundary for key in ("snapshots", "tables", "originals")):
        raise ValueError("supplied-files-only source_boundary cannot include pull-data-only pins")
    root_text = boundary.get("root")
    if not isinstance(root_text, str) or not root_text:
        raise ValueError("supplied-files-only source_boundary.root is required")
    root = Path(root_text).resolve(strict=True)
    manifest_path = root / "supplied_evidence.json"
    expected_manifest_hash = boundary.get("manifest_sha256")
    if not isinstance(expected_manifest_hash, str) or sha256_file(manifest_path) != expected_manifest_hash:
        raise ValueError("supplied evidence manifest hash mismatch or missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mode") != "supplied-files-only":
        raise ValueError("supplied evidence manifest mode mismatch")
    documents = manifest.get("documents")
    if not isinstance(documents, dict):
        raise ValueError("supplied evidence manifest documents must be an object")
    for doc_id, document in documents.items():
        relative = Path(str(document.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe preserved document path for {doc_id}")
        path = (root / relative).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"preserved document escapes evidence pack: {doc_id}") from exc
        if sha256_file(path) != document.get("sha256"):
            raise ValueError(f"preserved source hash mismatch: {doc_id} {document.get('sha256')}")
        issuer = str(document.get("issuer") or "").casefold()
        known_issuers = {str(spec.get("ticker") or "").casefold(),
                         str(spec.get("company") or "").casefold()} - {""}
        if issuer not in known_issuers:
            raise ValueError(f"supplied source issuer mismatch: {doc_id} says {document.get('issuer')!r}")
    rows_by_kind = {"actual": actual_rows, "benchmark": benchmark_rows or []}
    expected_facts = [fact for fact in manifest.get("facts", [])]
    expected_keys = set()
    blank_keys = set()
    counts = {"actuals_replayed": 0, "benchmarks_replayed": 0}
    for kind, rows in rows_by_kind.items():
        seen = set()
        for row in rows:
            value = "" if row.get("value") is None else str(row["value"]).strip()
            key = (row.get("metric"), row.get("period"), row.get("dimension") or "", kind)
            if key in seen:
                raise ValueError(f"duplicate frozen supplied fact {key}")
            seen.add(key)
            if not value:
                if kind != "actual" or row.get("provenance_status") != "unavailable" or not row.get("notes"):
                    raise ValueError(f"{key[0]} {key[1]}: blank supplied fact needs unavailable status and reason")
                gaps = [gap for gap in manifest.get("gaps", []) if
                        (gap.get("metric"), gap.get("period"), gap.get("dimension") or "", gap.get("kind")) == key]
                if len(gaps) != 1 or gaps[0].get("reason") != row["notes"]:
                    raise ValueError(f"{key[0]} {key[1]}: unavailable fact lacks a matching documented source gap")
                blank_keys.add(key)
                continue
            expected_keys.add(key)
            candidates = [fact for fact in expected_facts if (fact.get("metric"), fact.get("period"), fact.get("dimension") or "", fact.get("kind", "actual")) == key]
            if len(candidates) != 1:
                raise ValueError(f"{key[0]} {key[1]}: expected one reviewed source fact, found {len(candidates)}")
            fact = candidates[0]
            document = documents.get(fact["document_id"])
            if document is None:
                raise ValueError(f"{key[0]} {key[1]}: source document metadata is missing")
            source_path = root / document["path"]
            extracted, excerpt, locator_text = _extract(source_path, fact["locator"])
            review = fact.get("review") or {}
            if not all(review.get(field) is not None and str(review[field]).strip() for field in
                       ("reviewer", "reviewed_at", "independently_read_value", "notes")):
                raise ValueError(f"{key[0]} {key[1]}: independent review record is incomplete")
            try:
                datetime.fromisoformat(str(review["reviewed_at"]).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"{key[0]} {key[1]}: review timestamp is invalid") from exc
            reviewed = _number(str(review.get("independently_read_value", "")))
            if not math.isclose(extracted, reviewed, rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError(f"{key[0]} {key[1]}: reviewed value does not match preserved original")
            expected_locator = json.dumps({**fact["locator"], "resolved": locator_text,
                                           "quoted_excerpt": excerpt}, sort_keys=True, separators=(",", ":"))
            fields = {"units": fact["units"], "basis": fact["basis"],
                      "dimension": fact.get("dimension") or "", "transform": "direct",
                      "locator": expected_locator, "lineage_scheme": "supplied_document",
                      "lineage_path": fact["lineage_path"], "notes": review["notes"]}
            if kind == "benchmark":
                fields.update(source=fact["document_id"], as_of_date=fact.get("as_of_date") or document["document_date"])
            mismatched = [field for field, expected in fields.items() if str(row.get(field) or "") != str(expected)]
            if mismatched or not math.isclose(float(value), extracted, rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError(f"{key[0]} {key[1]}: frozen supplied fact does not replay ({', '.join(mismatched) or 'value'})")
            expected_lineage_key = (f"sha256={document['sha256']};reviewer={review['reviewer']};"
                                    f"reviewed_at={review['reviewed_at']}")
            if row.get("lineage_key") != expected_lineage_key:
                raise ValueError(f"{key[0]} {key[1]}: frozen review/source lineage does not replay")
            if kind == "actual":
                counts["actuals_replayed"] += 1
            else:
                counts["benchmarks_replayed"] += 1
    for fact in expected_facts:
        kind = fact.get("kind", "actual")
        key = (fact.get("metric"), fact.get("period"), fact.get("dimension") or "", kind)
        if key not in expected_keys:
            raise ValueError(f"{key[0]} {key[1]}: reviewed fact is absent from frozen {kind} evidence")
    for gap in manifest.get("gaps", []):
        if gap.get("kind") == "actual":
            key = (gap.get("metric"), gap.get("period"), gap.get("dimension") or "", "actual")
            if key not in blank_keys:
                raise ValueError(f"{key[0]} {key[1]}: documented unavailable fact is absent from frozen actuals")
    price = spec.get("price")
    if price is not None:
        price_date = str(price.get("date") or "")
        candidates = [row for row in (benchmark_rows or [])
                      if row.get("metric") == "price_dated" and str(row.get("period") or "") == price_date
                      and str(row.get("value") or "").strip()]
        if len(candidates) != 1 or not math.isclose(float(candidates[0]["value"]), float(price["value"]),
                                                    rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError(f"model_spec.price {price_date}: does not match exactly one replayed supplied benchmark")
    counts["gaps"] = len(manifest.get("gaps", []))
    return counts
