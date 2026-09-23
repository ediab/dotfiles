import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from evidence import prepare_evidence, replay_frozen_evidence
from supplied_evidence import prepare_supplied_pack, replay_supplied_evidence


class SuppliedFilesEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sources = self.root / "provided"
        self.sources.mkdir()
        self.html = self.sources / "release.html"
        self.html.write_text("<html><table><tr><th>Metric</th><th>Q2 2026</th></tr>"
                             "<tr><td>Revenue</td><td>$1,234.5 million</td></tr></table></html>")
        self.designation = {
            "pack_date": "2026-09-23",
            "documents": [{"id": "release", "file": "release.html", "issuer": "TST",
                           "document_type": "earnings release", "document_date": "2026-07-29"}],
            "facts": [{"metric": "revenue", "period": "2026Q2", "units": "USDm", "basis": "GAAP",
                       "document_id": "release", "locator": {"kind": "html_cell", "table": 0,
                           "row": 1, "column": 1, "value_text": "1,234.5"},
                       "review": {"reviewer": "agent", "reviewed_at": "2026-09-23T12:00:00Z",
                           "independently_read_value": "1234.5", "notes": "Compared the displayed cell and unit label."}}],
        }

    def tearDown(self):
        self.temp.cleanup()

    def _pack(self):
        return prepare_supplied_pack(self.sources, self.root / "pack", self.designation)

    def _spec(self, boundary):
        return {"ticker": "TST", "source_boundary": boundary}

    def _rows(self, pack):
        with (self.root / "pack" / "actuals.csv").open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_prepares_preserved_human_verified_fact_and_replays_it(self):
        manifest = self._pack()
        from evidence import _sha256
        pack_root = self.root / "pack"
        boundary = {"mode": "supplied-files-only", "root": str(pack_root),
                    "manifest_sha256": _sha256(pack_root / "supplied_evidence.json")}
        self.assertEqual(manifest["verification_coverage"],
                         {"accepted_facts": 1, "reviewed_facts": 1, "gaps": 0})
        rows = self._rows(manifest)
        self.assertEqual(rows[0]["value"], "1234.5")
        self.assertEqual(rows[0]["lineage_scheme"], "supplied_document")
        self.assertIn("table=0;row=1;cell=1", rows[0]["locator"])
        result = replay_frozen_evidence(self._spec(boundary), rows, [], None)
        self.assertEqual(result["actuals_replayed"], 1)

    def test_dispatch_never_touches_pull_store_for_supplied_mode(self):
        with patch("evidence._verify_boundary", side_effect=AssertionError("pull store touched")), \
             patch("evidence._ensure_pull_importable", side_effect=AssertionError("pull import attempted")):
            boundary = prepare_evidence(self._spec({"mode": "supplied-files-only"}),
                supplied_folder=self.sources, supplied_destination=self.root / "dispatch-pack",
                designation=self.designation)
            from evidence import _sha256
            boundary["source_boundary"]["manifest_sha256"] = _sha256(
                self.root / "dispatch-pack" / "supplied_evidence.json")
            rows = []
            with (self.root / "dispatch-pack" / "actuals.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            replay_frozen_evidence(self._spec(boundary["source_boundary"]), rows, [], None)

    def test_recorded_review_must_independently_match_original(self):
        self.designation["facts"][0]["review"]["independently_read_value"] = "1234"
        manifest = self._pack()
        self.assertEqual(manifest["facts"], [])
        self.assertIn("independent review disagrees", manifest["gaps"][0]["reason"])

    def test_frozen_source_modification_fails_replay(self):
        self._pack()
        from evidence import _sha256
        pack_root = self.root / "pack"
        boundary = {"mode": "supplied-files-only", "root": str(pack_root),
                    "manifest_sha256": _sha256(pack_root / "supplied_evidence.json")}
        rows = self._rows(None)
        source = next((pack_root / "sources").iterdir())
        source.write_text(source.read_text() + "<!-- altered -->")
        with self.assertRaisesRegex(ValueError, "preserved source hash mismatch"):
            replay_supplied_evidence(self._spec(boundary), rows)

    def test_manifest_tampering_fails_replay(self):
        self._pack()
        from evidence import _sha256
        pack_root = self.root / "pack"
        boundary = {"mode": "supplied-files-only", "root": str(pack_root),
                    "manifest_sha256": _sha256(pack_root / "supplied_evidence.json")}
        rows = self._rows(None)
        path = pack_root / "supplied_evidence.json"
        manifest = json.loads(path.read_text())
        manifest["facts"][0]["value"] = 999
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "manifest hash mismatch"):
            replay_frozen_evidence(self._spec(boundary), rows, [], None)

    def test_duplicate_quote_is_rejected_as_ambiguous(self):
        text = self.sources / "duplicate.md"
        text.write_text("Revenue increased from 90 to 100; prior forecast was 100.\n")
        self.designation["documents"].append({"id": "duplicate", "file": "duplicate.md", "issuer": "TST",
            "document_type": "filing", "document_date": "2026-07-29"})
        fact = self.designation["facts"][0]
        fact.update(document_id="duplicate", locator={"kind": "text_passage", "line_start": 1, "line_end": 1,
                           "quote": "Revenue increased from 90 to 100; prior forecast was 100.", "value_text": "100"})
        fact["review"]["independently_read_value"] = "100"
        manifest = self._pack()
        self.assertEqual(manifest["facts"], [])
        self.assertIn("numeric token '100' is not unique", manifest["gaps"][0]["reason"])

    def test_text_passage_requires_exact_line_location_and_source_token(self):
        text = self.sources / "filing.md"
        text.write_text("Revenue\nReported amount: 321.4 million\nNotes\n")
        self.designation["documents"].append({"id": "filing", "file": "filing.md", "issuer": "TST",
            "document_type": "filing", "document_date": "2026-07-29"})
        fact = self.designation["facts"][0]
        fact.update(document_id="filing", locator={"kind": "text_passage", "line_start": 1,
            "line_end": 2, "quote": "Revenue Reported amount: 321.4 million", "value_text": "321.4"})
        fact["review"]["independently_read_value"] = "321.4"
        manifest = self._pack()
        self.assertEqual(manifest["facts"][0]["value"], 321.4)

    def test_html_passage_locator_uses_unique_visible_text(self):
        self.html.write_text("<html><p>Reported revenue was <b>2,345.6</b> million.</p></html>")
        fact = self.designation["facts"][0]
        fact.update(locator={"kind": "html_passage", "quote": "Reported revenue was 2,345.6 million.",
                             "value_text": "2,345.6"})
        fact["review"]["independently_read_value"] = "2345.6"
        manifest = self._pack()
        self.assertEqual(manifest["facts"][0]["value"], 2345.6)
        self.assertEqual(manifest["facts"][0]["locator"]["resolved"],
                         "passage=Reported revenue was 2,345.6 million.")

    def test_text_searchable_pdf_locator_is_page_and_quote(self):
        import fitz
        pdf = self.sources / "filing.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Consolidated revenue for Q2 2026: 456.7 million")
        doc.save(pdf)
        doc.close()
        self.designation["documents"].append({"id": "pdf", "file": "filing.pdf", "issuer": "TST",
            "document_type": "quarterly filing", "document_date": "2026-07-29"})
        fact = self.designation["facts"][0]
        fact.update(document_id="pdf", locator={"kind": "pdf_page", "page": 1,
            "quote": "Consolidated revenue for Q2 2026: 456.7 million", "value_text": "456.7"})
        fact["review"]["independently_read_value"] = "456.7"
        manifest = self._pack()
        self.assertEqual(manifest["facts"][0]["value"], 456.7)
        self.assertIn("page=1", manifest["facts"][0]["locator"]["resolved"])

    def test_html_passage_does_not_accept_script_text_as_visible_evidence(self):
        self.html.write_text("<script>Revenue was 999</script><p>No numerical disclosure</p>")
        fact = self.designation["facts"][0]
        fact["locator"] = {"kind": "html_passage", "quote": "Revenue was 999", "value_text": "999"}
        fact["review"]["independently_read_value"] = "999"
        manifest = self._pack()
        self.assertEqual(manifest["facts"], [])
        self.assertIn("quoted passage does not match", manifest["gaps"][0]["reason"])

    def test_second_html_table_has_stable_locator(self):
        self.html.write_text("<html><table><tr><th>Amount</th></tr><tr><td>111</td></tr></table>"
                             "<table><tr><th>Revenue</th></tr><tr><td>222</td></tr></table></html>")
        fact = self.designation["facts"][0]
        fact["locator"] = {"kind": "html_cell", "table": 1, "row": 1, "column": 0,
                           "value_text": "222"}
        fact["review"]["independently_read_value"] = "222"
        manifest = self._pack()
        self.assertEqual(manifest["facts"][0]["value"], 222.0)
        self.assertIn("table=1", manifest["facts"][0]["locator"]["resolved"])

    def test_zero_value_replays_even_as_numeric_zero(self):
        self.html.write_text("<table><tr><th>Amount</th></tr><tr><td>0</td></tr></table>")
        fact = self.designation["facts"][0]
        fact["locator"] = {"kind": "html_cell", "table": 0, "row": 1, "column": 0,
                           "value_text": "0"}
        fact["review"]["independently_read_value"] = "0"
        self._pack()
        from evidence import _sha256
        boundary = {"mode": "supplied-files-only", "root": str(self.root / "pack"),
                    "manifest_sha256": _sha256(self.root / "pack" / "supplied_evidence.json")}
        rows = self._rows(None)
        rows[0]["value"] = 0.0
        self.assertEqual(replay_supplied_evidence(self._spec(boundary), rows)["actuals_replayed"], 1)

    def test_rejected_mapped_fact_is_explicit_unavailable_not_missing_or_zero(self):
        self.designation["facts"][0]["locator"]["value_text"] = "999"
        manifest = self._pack()
        rows = self._rows(None)
        self.assertEqual(manifest["facts"], [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], "")
        self.assertEqual(rows[0]["provenance_status"], "unavailable")
        self.assertIn("999", rows[0]["notes"])
        from evidence import _sha256
        boundary = {"mode": "supplied-files-only", "root": str(self.root / "pack"),
                    "manifest_sha256": _sha256(self.root / "pack" / "supplied_evidence.json")}
        self.assertEqual(replay_supplied_evidence(self._spec(boundary), rows)["actuals_replayed"], 0)
        with self.assertRaisesRegex(ValueError, "documented unavailable fact is absent"):
            replay_supplied_evidence(self._spec(boundary), [])

    def test_unsupported_file_is_named_gap(self):
        image = self.sources / "chart.png"
        image.write_bytes(b"not an image parser input")
        self.designation["documents"].append({"id": "chart", "file": "chart.png", "issuer": "TST",
            "document_type": "chart", "document_date": "2026-07-29"})
        manifest = self._pack()
        self.assertTrue(any(gap.get("source") == "chart" and "unsupported format" in gap["reason"]
                            for gap in manifest["gaps"]))

    def test_scanned_pdf_is_recorded_as_gap_not_extracted(self):
        import fitz
        pdf = self.sources / "scan.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf)
        doc.close()
        self.designation["documents"].append({"id": "scan", "file": "scan.pdf", "issuer": "TST",
            "document_type": "scanned filing", "document_date": "2026-07-29"})
        manifest = self._pack()
        self.assertEqual(manifest["facts"][0]["value"], 1234.5)
        self.assertTrue(any("no searchable text" in gap["reason"] for gap in manifest["gaps"]))

    def test_existing_dated_pack_cannot_be_overwritten(self):
        self._pack()
        with self.assertRaises(FileExistsError):
            self._pack()

    def test_unknown_source_mode_fails_without_fallback(self):
        with self.assertRaisesRegex(ValueError, "unsupported evidence source mode"):
            replay_frozen_evidence(self._spec({"mode": "mixed"}), [], [], None)

    def test_mixed_source_boundary_is_rejected(self):
        boundary = {"mode": "supplied-files-only", "root": str(self.root / "pack"),
                    "manifest_sha256": "0" * 64, "snapshots": [], "tables": [], "originals": []}
        with self.assertRaisesRegex(ValueError, "cannot include pull-data-only pins"):
            replay_frozen_evidence(self._spec(boundary), [], [], None)

    def test_pull_only_preparation_does_not_invoke_supplied_folder_reader(self):
        sys.path.insert(0, str(Path(__file__).parent))
        from pull_fixture import create_source, fact_mappings
        spec, facts = create_source(self.root / "pull" / "data", "TST")
        with patch("supplied_evidence.prepare_supplied_pack", side_effect=AssertionError("local source read")):
            result = prepare_evidence(spec, fact_map=fact_mappings(facts), periods=["2026Q2"],
                                      output_dir=self.root / "pull-freeze")
        self.assertEqual(result["verification_coverage"]["accepted_facts"], 2)


if __name__ == "__main__":
    unittest.main()
