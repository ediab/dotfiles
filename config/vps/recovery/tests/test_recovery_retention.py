"""Tests for the rolling seven-day recovery retention planner and installers.

Run with Python 3.12:

    python3.12 -m unittest discover -s config/vps/recovery/tests -v

The planner is exercised with synthetic verified-point sets; the installers are
exercised against temporary roots only. No rclone, sudo, VPS or live path is
touched.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve()
SOURCE = HERE.parents[1] / "recovery_retention.py"
INSTALLER_SOURCE = HERE.parents[1] / "install_recovery_retention.py"
RCLONE_SOURCE = HERE.parents[1] / "install_rclone_trusted.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rr = load("recovery_retention", SOURCE)
installer = load("install_recovery_retention", INSTALLER_SOURCE)
rclone_installer = load("install_rclone_trusted", RCLONE_SOURCE)

DAY = 86400
NOW = 1_800_000_000  # 2027-01-15T08:00:00Z


def stamp(epoch: int, suffix: str = "aaaaaaaaaaaaaaaa") -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + suffix


def vp(name: str, ts: int, count: int | None = 3, shape: str = "listing-count") -> "rr.VerifiedPoint":
    return rr.VerifiedPoint(name, ts, shape, count)


def family_entry(family, protected_name, protected_ts, points, *, is_dir=True, count=3):
    return {"family": family, "is_dir": is_dir, "verified_points": max(2, len(points)),
            "protected": {"name": protected_name, "timestamp": protected_ts,
                          "shape": "listing-count", "expected_count": count},
            "points": points}


class PointParsingTests(unittest.TestCase):
    def test_strict_parse_accepts_real_identities(self):
        self.assertEqual(rr.parse_point_timestamp("20261014T033001Z-8d5e630819ec4ee980dfe019999aeda2"),
                         int(datetime(2026, 10, 14, 3, 30, 1, tzinfo=timezone.utc).timestamp()))
        self.assertIsNotNone(rr.parse_point_timestamp("20261014T052505Z-54bafa728a0b456d97dcda6625f01742.tar"))
        self.assertEqual(rr.parse_point_timestamp("20261013T220012425597Z-3cc9bfa0fb944a709671d481a96c3b8e"),
                         int(datetime(2026, 10, 13, 22, 0, 12, tzinfo=timezone.utc).timestamp()))

    def test_strict_parse_rejects_malformed_and_lexicographic_surprises(self):
        for bad in ("", "not-a-point", "20261314T000000Z-x", "20261014T256000Z-x",
                    "20261014T033001Z-sub/dir", "20261014T033001-x", "20261014T033001Z"):
            with self.subTest(bad=bad):
                self.assertIsNone(rr.parse_point_timestamp(bad))
        a = rr.parse_point_timestamp("20261014T033001123Z-aaaaaaaaaaaaaaaa")
        b = rr.parse_point_timestamp("20261014T033001Z-bbbbbbbbbbbbbbbb")
        self.assertEqual(a, b)


class PlanBoundaryTests(unittest.TestCase):
    spec = rr.FamilySpec(rr.NOTE_SX, True, "note-sx")

    def plan(self, verified, remote, *, now: int = NOW):
        return rr.plan_family(self.spec, verified, remote, now=now)

    def decisions(self, entries):
        return {entry["name"]: entry["decision"] for entry in entries}

    def reasons(self, entries):
        return {entry["name"]: entry["reason"] for entry in entries}

    def test_seven_day_boundary_is_deterministic(self):
        exactly = stamp(NOW - 7 * DAY)
        older = stamp(NOW - 7 * DAY - 1)
        newer = stamp(NOW - 7 * DAY + 1)
        verified = {exactly: vp(exactly, NOW - 7 * DAY), older: vp(older, NOW - 7 * DAY - 1),
                    newer: vp(newer, NOW - 7 * DAY + 1)}
        decisions = self.decisions(self.plan(verified, [exactly, older, newer]))
        self.assertEqual(decisions[exactly], "keep")
        self.assertEqual(decisions[newer], "keep")
        self.assertEqual(decisions[older], "delete")

    def test_old_latest_verified_point_is_never_deleted(self):
        newest = stamp(NOW - 40 * DAY, "newest")
        old = stamp(NOW - 50 * DAY, "older")
        verified = {newest: vp(newest, NOW - 40 * DAY), old: vp(old, NOW - 50 * DAY)}
        entries = self.plan(verified, [newest, old])
        self.assertEqual(self.decisions(entries)[newest], "keep")
        self.assertEqual(self.reasons(entries)[newest], "newest-verified-point-always-preserved")
        self.assertEqual(self.decisions(entries)[old], "delete")

    def test_timestamp_tie_and_fraction_tie_are_never_deleted(self):
        newest = stamp(NOW - 30 * DAY, "newest")
        tied = stamp(NOW - 30 * DAY, "tie")                 # equal whole second

        # Build a fractional-tie name: same whole second, extra digits before Z.
        frac_name = datetime.fromtimestamp(NOW - 30 * DAY, timezone.utc).strftime("%Y%m%dT%H%M%S") + "123Z-tiefrac"
        verified = {newest: vp(newest, NOW - 30 * DAY), tied: vp(tied, NOW - 30 * DAY),
                    frac_name: vp(frac_name, NOW - 30 * DAY)}
        decisions = self.decisions(self.plan(verified, [newest, tied, frac_name]))
        self.assertEqual(decisions[tied], "keep")
        self.assertEqual(decisions[frac_name], "keep")
        self.assertTrue(decisions[newest] == "keep")

    def test_unverified_newer_and_in_progress_are_preserved(self):
        newest = stamp(NOW - 30 * DAY, "verified")
        unverified_old = stamp(NOW - 20 * DAY, "noreceipt")
        unverified_new = stamp(NOW - 1 * DAY, "inprogress")
        future = stamp(NOW + 5 * DAY, "clock-skew")
        verified = {newest: vp(newest, NOW - 30 * DAY)}
        entries = self.plan(verified, [newest, unverified_old, unverified_new, future])
        decisions = self.decisions(entries)
        self.assertEqual(decisions[newest], "keep")
        self.assertEqual(decisions[unverified_old], "keep")
        self.assertEqual(decisions[unverified_new], "keep")
        self.assertEqual(decisions[future], "keep")
        self.assertEqual(self.reasons(entries)[unverified_old], "no-passing-receipt")

    def test_malformed_and_nested_names_are_preserved(self):
        newest = stamp(NOW - 1 * DAY, "verified")
        entries = self.plan({newest: vp(newest, NOW - 1 * DAY)},
                            [newest, "README", "20261014T033001Z", "2026-bad-name"])
        for name in ("README", "20261014T033001Z", "2026-bad-name"):
            self.assertEqual(self.decisions(entries)[name], "keep")

    def test_mixed_timestamps_do_not_prematurely_delete(self):
        in_window_a = stamp(NOW - 2 * DAY, "a")
        in_window_b = stamp(NOW - 6 * DAY, "b")
        old_a = stamp(NOW - 8 * DAY, "c")
        old_b = stamp(NOW - 30 * DAY, "d")
        verified = {n: vp(n, rr.parse_point_timestamp(n)) for n in (in_window_a, in_window_b, old_a, old_b)}
        decisions = self.decisions(self.plan(verified, [old_b, in_window_b, old_a, in_window_a]))
        self.assertEqual(decisions[in_window_a], "keep")
        self.assertEqual(decisions[in_window_b], "keep")
        self.assertEqual(decisions[old_a], "delete")
        self.assertEqual(decisions[old_b], "delete")

    def test_empty_verified_set_is_a_refusal_not_a_silent_skip(self):
        with self.assertRaisesRegex(rr.Refusal, "verified point set empty"):
            self.plan({}, [stamp(NOW - 100 * DAY)])

    def test_missing_newest_verified_point_refuses(self):
        newest = stamp(NOW - 30 * DAY, "gone")
        with self.assertRaisesRegex(rr.Refusal, "newest verified point missing"):
            self.plan({newest: vp(newest, NOW - 30 * DAY)}, [stamp(NOW - 40 * DAY)])

    def test_manifest_digest_is_stable_and_delete_set_is_explicit(self):
        newest = stamp(NOW - 1 * DAY, "verified")
        old = stamp(NOW - 30 * DAY, "old")
        families = [family_entry(rr.NOTE_SX, newest, NOW - DAY,
                                 self.plan({newest: vp(newest, NOW - DAY), old: vp(old, NOW - 30 * DAY)},
                                           [newest, old]))]
        manifest = rr.build_manifest(families, now=NOW)
        self.assertEqual(rr.manifest_digest(manifest), rr.manifest_digest(manifest))
        self.assertEqual(rr.delete_sets(manifest)[rr.NOTE_SX], [old])
        self.assertEqual(manifest["summary"]["delete"], 1)
        self.assertTrue(manifest["policy"]["delete_requires_strictly_older_than_protected"])
        self.assertTrue(manifest["policy"]["delete_requires_strictly_outside_window"])


class RemoteShapeTests(unittest.TestCase):
    def test_listing_count_rejects_missing_extra_and_type_mismatch(self):
        point = vp("20261001T000000Z-x", 1, count=3)
        calls = []

        def fake_command(*args):
            calls.append(args)
            return json.dumps([{"Path": "a", "Size": 1}, {"Path": "b", "Size": 2},
                               {"Path": "c", "Size": 3}]).encode()
        with mock.patch.object(rr, "command", side_effect=fake_command):
            rr.assert_remote_point(rr.NOTE_SX, point)
        self.assertIn("--files-only", calls[0])

        def extra(*_args):
            return json.dumps([{"Path": "a", "Size": 1}]).encode()
        with mock.patch.object(rr, "command", side_effect=extra):
            with self.assertRaisesRegex(rr.Refusal, "count mismatch"):
                rr.assert_remote_point(rr.NOTE_SX, point)

        def bad_type(*_args):
            return json.dumps([{"Path": "a", "Size": "1"}, {"Path": "b", "Size": 2},
                               {"Path": "c", "Size": 3}]).encode()
        with mock.patch.object(rr, "command", side_effect=bad_type):
            with self.assertRaisesRegex(rr.Refusal, "type mismatch"):
                rr.assert_remote_point(rr.NOTE_SX, point)

    def test_size_shape_rejects_empty_or_zero_bytes(self):
        point = rr.VerifiedPoint("20261001T000000Z-x.tar", 1, "size", None)
        with mock.patch.object(rr, "command", return_value=json.dumps({"count": 1, "bytes": 0}).encode()):
            with self.assertRaisesRegex(rr.Refusal, "object missing"):
                rr.assert_remote_point(rr.MORNING_CONFIG, point)
        with mock.patch.object(rr, "command", return_value=json.dumps({"count": 1, "bytes": 9}).encode()):
            rr.assert_remote_point(rr.MORNING_CONFIG, point)


class ReceiptLoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "receipts"
        self.morning = Path(self.tmp.name) / "morning"
        self.base.mkdir()
        self.morning.mkdir()
        self._old_base, self._old_morning = rr.BASE, rr.MORNING
        rr.BASE, rr.MORNING = self.base, self.morning

    def tearDown(self):
        rr.BASE, rr.MORNING = self._old_base, self._old_morning
        self.tmp.cleanup()

    def write(self, root: Path, name: str, payload: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def note(self, point: str, *, passing=True, count=3):
        self.write(self.base, f"note-sx-state-{point}.json", {
            "capture_id": point, "remote_prefix": f"{rr.NOTE_SX}/{point}",
            "readback": "exact-set-and-sha256-pass" if passing else "failed",
            "restore": "pass", "database_check": "pass",
            "consumer": {"recovered_html": "pass"}, "readback_file_count": count})

    def test_note_sx_requires_full_proof_and_exact_identity(self):
        good = stamp(NOW - DAY)
        self.note(good, count=3)
        bad = stamp(NOW - 2 * DAY, "bad")
        self.write(self.base, f"note-sx-state-{bad}.json", {
            "capture_id": bad, "remote_prefix": f"{rr.NOTE_SX}/{bad}",
            "readback": "failed", "restore": "pass", "database_check": "pass",
            "consumer": {"recovered_html": "pass"}, "readback_file_count": 3})
        verified = rr.load_note_sx()
        self.assertEqual(list(verified), [good])
        self.assertEqual(verified[good].expected_count, 3)

    def test_note_sx_newest_failed_proof_refuses(self):
        good = stamp(NOW - 2 * DAY, "good")
        self.note(good, count=3)
        failed = stamp(NOW - DAY, "failed")
        self.note(failed, passing=False, count=3)
        with self.assertRaisesRegex(rr.Refusal, "newest receipt proof missing"):
            rr.load_note_sx()

    def test_note_sx_capture_and_remote_point_have_independent_identities(self):
        point = stamp(NOW - DAY, "remote")
        capture = stamp(NOW - DAY + 1, "capture")
        self.write(self.base, f"note-sx-state-{capture}.json", {
            "schema": "note-sx-r2-recovery/v1", "app": "note-sx",
            "capture_id": capture, "remote_prefix": f"{rr.NOTE_SX}/{point}",
            "readback": "exact-set-and-sha256-pass", "restore": "pass",
            "database_check": "pass", "consumer": {"recovered_html": "pass"},
            "readback_file_count": 3})
        verified = rr.load_note_sx()
        self.assertEqual(list(verified), [point])
        self.assertEqual(verified[point].timestamp, NOW - DAY)

    def test_note_sx_receipt_filename_must_bind_its_capture(self):
        point = stamp(NOW - DAY, "capture")
        self.note(point)
        (self.base / f"note-sx-state-{point}.json").rename(
            self.base / f"note-sx-state-{stamp(NOW, 'wrong')}.json")
        with self.assertRaisesRegex(rr.Refusal, "identity mismatch"):
            rr.load_note_sx()

    def test_note_sx_missing_inventory_refuses(self):
        with self.assertRaisesRegex(rr.Refusal, "receipt inventory missing"):
            rr.load_note_sx()

    def test_cratch_requires_schema_closure_and_object_count(self):
        point = stamp(NOW - DAY)
        self.write(self.base, f"cratch-neon-state-{point}-complete.json", {
            "r2_prefix": f"{rr.CRATCH}/{point}", "object_count": 4,
            "proof": {"fresh_exact_set_readback": True, "schema_row_sequence_closure": True}})
        verified = rr.load_app("cratch-neon-state-*-complete.json", rr.CRATCH)
        self.assertEqual(verified[point].expected_count, 4)

        broken = stamp(NOW - DAY, "broken")
        self.write(self.base, f"cratch-neon-state-{broken}-complete.json", {
            "r2_prefix": f"{rr.CRATCH}/{broken}",
            "proof": {"fresh_exact_set_readback": True, "schema_row_sequence_closure": False}})
        with self.assertRaisesRegex(rr.Refusal, "newest receipt proof missing"):
            rr.load_app("cratch-neon-state-*-complete.json", rr.CRATCH)

    def test_morning_binds_linked_identity_and_requires_verified(self):
        state_point = stamp(NOW - DAY, "state")
        config_point = stamp(NOW - DAY, "config")
        complete = stamp(NOW - DAY, "complete")
        self.write(self.morning, f"{complete}-complete.json", {
            "verified": True, "stamp": complete,
            "metadata_receipt": f"{state_point}-backup.json",
            "config_receipt": f"{config_point}-config.json"})
        self.write(self.morning, f"{state_point}-backup.json", {
            "verified": True, "stamp": state_point,
            "remote_prefix": f"{rr.MORNING_STATE}/{state_point}"})
        self.write(self.morning, f"{config_point}-config.json", {
            "verified": True, "stamp": config_point,
            "remote_object": f"{rr.MORNING_CONFIG}/{config_point}.tar"})
        state, config = rr.load_morning()
        self.assertEqual(list(state), [state_point])
        self.assertEqual(list(config), [config_point + ".tar"])
        self.assertEqual(state[state_point].shape, "size")

    def test_morning_unverified_link_refuses(self):
        complete = stamp(NOW - DAY, "complete")
        self.write(self.morning, f"{complete}-complete.json", {
            "verified": True, "stamp": complete,
            "metadata_receipt": f"{complete}-backup.json",
            "config_receipt": f"{complete}-config.json"})
        self.write(self.morning, f"{complete}-backup.json", {
            "verified": False, "stamp": complete,
            "remote_prefix": f"{rr.MORNING_STATE}/{complete}"})
        self.write(self.morning, f"{complete}-config.json", {
            "verified": True, "stamp": complete,
            "remote_object": f"{rr.MORNING_CONFIG}/{complete}.tar"})
        with self.assertRaisesRegex(rr.Refusal, "newest receipt proof missing"):
            rr.load_morning()

    def test_morning_path_escape_refuses(self):
        complete = stamp(NOW - DAY, "complete")
        self.write(self.morning, f"{complete}-complete.json", {
            "verified": True, "stamp": complete,
            "metadata_receipt": "../escape.json", "config_receipt": "../escape.json"})
        with self.assertRaisesRegex(rr.Refusal, "link escape"):
            rr.load_morning()


class ApplyPlanSafetyTests(unittest.TestCase):
    def test_protected_drift_refuses_with_zero_purge(self):
        # Preview protects `newest`; a fresh load now protects `old`, which the
        # preview had planned to delete. Nothing may be purged.
        old = stamp(NOW - 40 * DAY, "old")
        newest = stamp(NOW - 1 * DAY, "newest")
        manifest = rr.build_manifest([family_entry(
            rr.NOTE_SX, newest, NOW - DAY,
            [{"name": newest, "decision": "keep"},
             {"name": old, "decision": "delete"}])], now=NOW)
        calls: list[tuple] = []

        def fake_command(*args):
            calls.append(args)
            return b"{}"

        fresh = {old: vp(old, NOW - 40 * DAY), newest: vp(newest, NOW - DAY, count=3)}
        # Promote `old` (previously planned for deletion) to the protected point.
        fresh[old] = vp(old, NOW - 60, count=3)
        with mock.patch.object(rr, "SPECS", (rr.FamilySpec(rr.NOTE_SX, True, "note-sx"),)), \
             mock.patch.object(rr, "load_verified", return_value=fresh), \
             mock.patch.object(rr, "assert_remote_point", lambda *a, **k: None), \
             mock.patch.object(rr, "command", side_effect=fake_command), \
             mock.patch.object(rr, "local_cleanup", lambda *a, **k: []), \
             mock.patch.object(rr, "receipts", lambda *a, **k: []), \
             mock.patch.object(rr, "observe_cron", lambda: None):
            with self.assertRaisesRegex(rr.Refusal, "protected-point drift"):
                rr.apply_plan(manifest, now=NOW)
        self.assertEqual([c for c in calls if c and c[0] in {"purge", "deletefile"}], [])

    def test_candidate_no_longer_verified_refuses_with_zero_purge(self):
        newest = stamp(NOW - 1 * DAY, "newest")
        old = stamp(NOW - 40 * DAY, "old")
        manifest = rr.build_manifest([family_entry(
            rr.NOTE_SX, newest, NOW - DAY,
            [{"name": newest, "decision": "keep"},
             {"name": old, "decision": "delete"}])], now=NOW)
        calls: list[tuple] = []
        fresh = {newest: vp(newest, NOW - DAY, count=3)}  # `old` vanished from receipts

        with mock.patch.object(rr, "SPECS", (rr.FamilySpec(rr.NOTE_SX, True, "note-sx"),)), \
             mock.patch.object(rr, "load_verified", return_value=fresh), \
             mock.patch.object(rr, "assert_remote_point", lambda *a, **k: None), \
             mock.patch.object(rr, "command", side_effect=lambda *a: calls.append(a) or b"{}"), \
             mock.patch.object(rr, "local_cleanup", lambda *a, **k: []), \
             mock.patch.object(rr, "receipts", lambda *a, **k: []), \
             mock.patch.object(rr, "observe_cron", lambda: None):
            with self.assertRaisesRegex(rr.Refusal, "no longer verified"):
                rr.apply_plan(manifest, now=NOW)
        self.assertEqual([c for c in calls if c and c[0] in {"purge", "deletefile"}], [])

    def test_valid_candidate_is_purged_after_binding(self):
        newest = stamp(NOW - 1 * DAY, "newest")
        old = stamp(NOW - 40 * DAY, "old")
        manifest = rr.build_manifest([family_entry(
            rr.NOTE_SX, newest, NOW - DAY,
            [{"name": newest, "decision": "keep"},
             {"name": old, "decision": "delete"}])], now=NOW)
        calls: list[tuple] = []
        fresh = {newest: vp(newest, NOW - DAY, count=3), old: vp(old, NOW - 40 * DAY, count=3)}
        with mock.patch.object(rr, "SPECS", (rr.FamilySpec(rr.NOTE_SX, True, "note-sx"),)), \
             mock.patch.object(rr, "load_verified", return_value=fresh), \
             mock.patch.object(rr, "assert_remote_point", lambda *a, **k: None), \
             mock.patch.object(rr, "command", side_effect=lambda *a: calls.append(a) or b"{}"), \
             mock.patch.object(rr, "local_cleanup", lambda *a, **k: []), \
             mock.patch.object(rr, "receipts", lambda *a, **k: []), \
             mock.patch.object(rr, "observe_cron", lambda: None):
            rr.apply_plan(manifest, now=NOW)
        self.assertIn(("purge", f"{rr.NOTE_SX}/{old}"), calls)


class LocalCleanupTests(unittest.TestCase):
    def test_local_policy_keeps_newer_and_ambiguous_and_removes_superseded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "captures"
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
            old = root / stamp(NOW - 30 * DAY, "old")
            newest = root / stamp(NOW - DAY, "newest")
            inprogress = root / stamp(NOW + 60, "inprogress")
            junk = root / "not-a-stamp"
            for path in (old, newest, inprogress, junk):
                path.mkdir()
            removed = rr.local_cleanup(root, NOW - DAY, anchor=Path(tmp),
                                        anchor_uid=os.getuid(),
                                        allowed_owners=(os.getuid(),))
            self.assertIn(old.name, removed)
            self.assertIn(newest.name, removed)
            self.assertTrue(inprogress.exists())
            self.assertTrue(junk.exists())

    def test_local_cleanup_without_verified_point_removes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "captures"
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
            child = root / stamp(NOW - 30 * DAY, "old")
            child.mkdir()
            self.assertEqual(rr.local_cleanup(root, None, anchor=Path(tmp),
                                              anchor_uid=os.getuid(),
                                              allowed_owners=(os.getuid(),)), [])
            self.assertTrue(child.exists())


class RecoveryInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "unit").mkdir()
        (self.root / "rollback").mkdir()
        self.baseline = b"#!/usr/bin/env python3\n# frozen baseline\n"
        self.baseline_sha = installer.sha256_bytes(self.baseline)
        self.source = self.root / "recovery_retention.py"
        self.source.write_bytes(b"#!/usr/bin/env python3\n# seven day policy\n")
        os.chmod(self.source, 0o644)
        self.source_sha = installer.sha256_bytes(self.source.read_bytes())
        self.live = self.root / "unit" / "lean-recovery-retention.py"

    def tearDown(self):
        self.tmp.cleanup()

    def run_installer(self, *args: str):
        argv = ["--source", str(self.source), "--live-script", str(self.live),
                "--rollback-dir", str(self.root / "rollback"),
                "--expected-source-sha256", self.source_sha,
                "--baseline-sha256", self.baseline_sha,
                "--lock-path", str(self.root / "no.lock"),
                "--operator-quiesced", "--test-paths", "--test-root", str(self.root), *args]
        return installer.main(argv)

    def test_fresh_install_creates_script(self):
        self.assertEqual(self.run_installer("--apply"), 0)
        self.assertEqual(self.live.read_bytes(), self.source.read_bytes())

    def test_tampered_source_is_refused_even_with_matching_filename(self):
        self.source.write_bytes(b"#!/usr/bin/env python3\n# attacker bytes\n")
        with self.assertRaisesRegex(installer.InstallRefusal, "reviewed hash"):
            self.run_installer("--apply")
        self.assertFalse(self.live.exists())

    def test_unknown_live_content_refuses_without_touching_it(self):
        self.live.write_bytes(b"#!/usr/bin/env python3\n# hand-edited live file\n")
        with self.assertRaisesRegex(installer.InstallRefusal, "unrecognised"):
            self.run_installer("--apply")
        self.assertEqual(self.live.read_bytes(), b"#!/usr/bin/env python3\n# hand-edited live file\n")

    def test_symlink_and_dangling_symlink_live_files_refuse(self):
        for target in ("missing", str(self.root / "unit" / "other.py")):
            with self.subTest(target=target):
                if self.live.is_symlink() or self.live.exists():
                    self.live.unlink()
                self.live.symlink_to(target)
                with self.assertRaisesRegex(installer.InstallRefusal, "symlink"):
                    self.run_installer("--apply")

    def test_adoption_of_frozen_baseline_backs_up_then_replaces(self):
        self.live.write_bytes(self.baseline)
        os.chmod(self.live, 0o755)
        self.assertEqual(self.run_installer("--apply"), 0)
        receipt = json.loads((self.root / "rollback" / "lean-recovery-retention.py.last-backup.json").read_text())
        self.assertEqual(receipt["replaced_with_sha256"], self.source_sha)
        backup = self.root / "rollback" / receipt["backup"]
        self.assertEqual(backup.read_bytes(), self.baseline)
        self.assertEqual(installer.sha256_bytes(self.baseline), receipt["sha256"])

    def test_idempotent_and_rollback_restores_exact_backup(self):
        self.live.write_bytes(self.baseline)
        os.chmod(self.live, 0o755)
        self.assertEqual(self.run_installer("--apply"), 0)
        self.assertEqual(self.run_installer("--apply"), 0)
        self.assertEqual(self.run_installer("--rollback"), 0)
        self.assertEqual(self.live.read_bytes(), self.baseline)

    def test_rollback_drift_refuses_when_live_changed(self):
        self.live.write_bytes(self.baseline)
        os.chmod(self.live, 0o755)
        self.assertEqual(self.run_installer("--apply"), 0)
        self.live.write_bytes(b"drifted content")
        with self.assertRaisesRegex(installer.InstallRefusal, "drifted"):
            self.run_installer("--rollback")

    def test_rollback_without_receipt_refuses(self):
        with self.assertRaisesRegex(installer.InstallRefusal, "no recorded rollback receipt"):
            self.run_installer("--rollback")

    def test_rollback_rejects_tampered_backup(self):
        self.live.write_bytes(self.baseline)
        os.chmod(self.live, 0o755)
        self.assertEqual(self.run_installer("--apply"), 0)
        receipt = json.loads((self.root / "rollback" / "lean-recovery-retention.py.last-backup.json").read_text())
        (self.root / "rollback" / receipt["backup"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(installer.InstallRefusal, "backup hash mismatch"):
            self.run_installer("--rollback")

    def test_test_paths_cannot_reach_real_targets(self):
        argv = ["--source", str(self.source), "--expected-source-sha256", self.source_sha,
                "--live-script", str(installer.DEFAULT_LIVE),
                "--rollback-dir", str(self.root / "rollback"),
                "--test-paths", "--test-root", str(self.root), "--apply"]
        with self.assertRaisesRegex(installer.InstallRefusal, "outside the test root"):
            installer.main(argv)

    def test_baseline_override_and_quiescence_are_real_mode_refused(self):
        argv = ["--source", str(self.source), "--expected-source-sha256", self.source_sha,
                "--live-script", str(self.live), "--rollback-dir", str(self.root / "rollback"),
                "--baseline-sha256", self.baseline_sha, "--verify-only"]
        with mock.patch.object(installer.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(installer.InstallRefusal, "test-only"):
                installer.main(argv)
            del argv[argv.index("--baseline-sha256") + 1]
            argv.remove("--baseline-sha256")
            argv.remove("--verify-only")
            argv.append("--apply")
            with self.assertRaisesRegex(installer.InstallRefusal, "quiescence"):
                installer.main(argv)

    def test_git_lineage_check_accepts_clean_and_rejects_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["/usr/bin/git", "init", "-q", str(repo)], check=True)
            subprocess.run(["/usr/bin/git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
            subprocess.run(["/usr/bin/git", "-C", str(repo), "config", "user.name", "t"], check=True)
            rel = "recovery_retention.py"
            (repo / rel).write_bytes(self.source.read_bytes())
            subprocess.run(["/usr/bin/git", "-C", str(repo), "add", rel], check=True)
            subprocess.run(["/usr/bin/git", "-C", str(repo), "commit", "-qm", "x"], check=True)
            installer.assert_git_lineage(repo, rel, self.source_sha)
            (repo / rel).write_bytes(b"dirty")
            with self.assertRaises(installer.InstallRefusal):
                installer.assert_git_lineage(repo, rel, self.source_sha)


class RcloneTrustedInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.payload = b"#!/bin/sh\necho 'rclone v1.75.2'\n"
        self.payload_sha = rclone_installer.sha256_bytes(self.payload)
        self.artifact = self.root / "rclone"
        self.artifact.write_bytes(self.payload)
        os.chmod(self.artifact, 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def fake_runner(self, *_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=b"rclone v1.75.2\n", stderr=b"")

    def test_user_writable_artifact_refused_under_trust(self):
        os.chmod(self.artifact, 0o666)
        with self.assertRaisesRegex(rclone_installer.RcloneRefusal, "user-writable"):
            rclone_installer.payload_from_artifact(self.artifact, expected_sha=self.payload_sha,
                                                   enforce_trust=True, owner=os.getuid())

    def test_artifact_hash_mismatch_refused(self):
        with self.assertRaisesRegex(rclone_installer.RcloneRefusal, "hash mismatch"):
            rclone_installer.payload_from_artifact(self.artifact, expected_sha="0" * 64,
                                                   enforce_trust=False)

    def test_payload_is_read_once_and_install_ignores_later_source_change(self):
        payload = rclone_installer.payload_from_artifact(self.artifact, expected_sha=self.payload_sha,
                                                         enforce_trust=False)
        self.artifact.write_bytes(b"#!/bin/sh\necho attacker\n")
        target = self.root / "bin/rclone"
        result = rclone_installer.install(payload=payload, target=target,
                                          rollback_dir=self.root / "rollback",
                                          expected_sha=self.payload_sha, enforce_trust=False,
                                          runner=self.fake_runner)
        self.assertEqual(result, "installed")
        self.assertEqual(target.read_bytes(), self.payload)

    def test_existing_writable_or_foreign_target_refused(self):
        with self.assertRaisesRegex(rclone_installer.RcloneRefusal, "foreign"):
            rclone_installer.assert_target_trusted(SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=1234), owner=0)
        with self.assertRaisesRegex(rclone_installer.RcloneRefusal, "user-writable"):
            rclone_installer.assert_target_trusted(SimpleNamespace(st_mode=stat.S_IFREG | 0o777, st_uid=0), owner=0)
        rclone_installer.assert_target_trusted(SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0), owner=0)

    def test_install_backs_up_and_is_idempotent(self):
        target = self.root / "bin/rclone"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"old binary")
        result = rclone_installer.install(payload=self.payload, target=target,
                                          rollback_dir=self.root / "rollback",
                                          expected_sha=self.payload_sha, enforce_trust=False,
                                          runner=self.fake_runner)
        self.assertEqual(result, "installed")
        receipt = json.loads((self.root / "rollback" / "rclone.last-backup.json").read_text())
        self.assertEqual((self.root / "rollback" / receipt["backup"]).read_bytes(), b"old binary")
        self.assertEqual(rclone_installer.install(payload=self.payload, target=target,
                                                  rollback_dir=self.root / "rollback",
                                                  expected_sha=self.payload_sha, enforce_trust=False,
                                                  runner=self.fake_runner), "idempotent")

    def test_test_paths_and_expected_override_are_guarded(self):
        argv = ["--artifact", str(self.artifact), "--target", str(rclone_installer.DEFAULT_TARGET),
                "--rollback-dir", str(self.root / "rollback"), "--test-paths",
                "--test-root", str(self.root), "--verify-only"]
        with self.assertRaisesRegex(rclone_installer.RcloneRefusal, "outside the test root"):
            rclone_installer.main(argv)
        argv[1] = str(self.artifact)
        with mock.patch.object(rclone_installer.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(rclone_installer.RcloneRefusal, "test-only"):
                rclone_installer.main(["--artifact", str(self.artifact), "--target",
                                       str(self.root / "bin/rclone"), "--rollback-dir",
                                       str(self.root / "rollback"), "--expected-sha256",
                                       self.payload_sha, "--verify-only"])


class GitLineageGuardTests(unittest.TestCase):
    """Root must refuse before any Git launch; the unprivileged path is unchanged."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="retention-git-guard-")
        self.root = Path(self.temp.name)
        self.relpath = "config/vps/recovery/recovery_retention.py"
        source = self.root / self.relpath
        source.parent.mkdir(mode=0o700, parents=True)
        source.write_text("# reviewed\n")
        import hashlib
        self.digest = hashlib.sha256(source.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    class _OsShim:
        def __init__(self, euid):
            self._euid = euid

        def geteuid(self):
            return self._euid

        def __getattr__(self, name):
            return getattr(os, name)

    class _SubprocessShim:
        def __init__(self):
            self.calls = []

        def run(self, argv, **kwargs):
            self.calls.append(argv)

            class Result:
                returncode = 0
                stdout = "" if "status" in argv else "deadbeef"

            return Result()

    def test_root_refuses_before_any_git_launch(self):
        subprocess_shim = self._SubprocessShim()
        original_os, original_subprocess = installer.os, installer.subprocess
        installer.os, installer.subprocess = self._OsShim(0), subprocess_shim
        try:
            with self.assertRaises(installer.InstallRefusal) as caught:
                installer.assert_git_lineage(self.root, self.relpath, self.digest)
        finally:
            installer.os, installer.subprocess = original_os, original_subprocess
        self.assertIn("unprivileged", str(caught.exception))
        self.assertEqual(subprocess_shim.calls, [], "root must not launch git at all")

    def test_unprivileged_lineage_check_is_unchanged(self):
        subprocess_shim = self._SubprocessShim()
        original_os, original_subprocess = installer.os, installer.subprocess
        installer.os, installer.subprocess = self._OsShim(1000), subprocess_shim
        try:
            installer.assert_git_lineage(self.root, self.relpath, self.digest)
        finally:
            installer.os, installer.subprocess = original_os, original_subprocess
        self.assertEqual(len(subprocess_shim.calls), 3)


if __name__ == "__main__":
    unittest.main()


class EndToEndPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "receipts"
        self.morning = Path(self.tmp.name) / "morning"
        self.base.mkdir()
        self.morning.mkdir()
        self._old_base, self._old_morning = rr.BASE, rr.MORNING
        rr.BASE, rr.MORNING = self.base, self.morning
        self.points = {
            rr.NOTE_SX: [stamp(NOW - DAY, "note-new"), stamp(NOW - 30 * DAY, "note-old")],
            rr.CRATCH: [stamp(NOW - DAY, "cratch-new"), stamp(NOW - 30 * DAY, "cratch-old")],
            rr.FOUSEKIS: [stamp(NOW - DAY, "fous-new"), stamp(NOW - 30 * DAY, "fous-old")],
            rr.REDACT: [stamp(NOW - DAY, "redact-new"), stamp(NOW - 30 * DAY, "redact-old")],
            rr.MORNING_STATE: [stamp(NOW - DAY, "state-new"), stamp(NOW - 30 * DAY, "state-old")],
            rr.MORNING_CONFIG: [stamp(NOW - DAY, "conf-new") + ".tar",
                                stamp(NOW - 30 * DAY, "conf-old") + ".tar"],
            rr.HOUSES_DAILY: [stamp(NOW - DAY, "houses-new"),
                              stamp(NOW - 30 * DAY, "houses-old")],
        }
        self._write_receipts()

    def tearDown(self):
        rr.BASE, rr.MORNING = self._old_base, self._old_morning
        self.tmp.cleanup()

    def write(self, root: Path, name: str, payload: dict) -> None:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(path, 0o600)

    def _write_receipts(self):
        for point in self.points[rr.NOTE_SX]:
            self.write(self.base, f"note-sx-state-{point}.json", {
                "capture_id": point, "remote_prefix": f"{rr.NOTE_SX}/{point}",
                "readback": "exact-set-and-sha256-pass", "restore": "pass",
                "database_check": "pass", "consumer": {"recovered_html": "pass"},
                "readback_file_count": 3})
        app_files = (
            (rr.CRATCH, "cratch-neon-state-{p}-complete.json"),
            (rr.FOUSEKIS, "fousekis-state-{p}.json"),
            (rr.REDACT, "redact-state-{p}.json"),
        )
        for family, template in app_files:
            for point in self.points[family]:
                self.write(self.base, template.format(p=point), {
                    "r2_prefix": f"{family}/{point}", "object_count": 3,
                    "proof": {"fresh_exact_set_readback": True,
                              "schema_row_sequence_closure": True}})
        for point in self.points[rr.HOUSES_DAILY]:
            self.write(self.base, f"houses-daily-{point}.json", {
                "backup_id": point, "remote": f"{rr.HOUSES_DAILY}/{point}",
                "status": "complete", "object_count": 3,
                **{key: True for key in (
                    "conditional_create", "independent_download_verified",
                    "all_file_hashes_match", "manual_table_digests_equal",
                    "sequences_verified", "container_cleanup")},
                "files": [{"path": name, "bytes": 1, "sha256": "0" * 64}
                          for name in ("manifest.json", "notebook.dump", "rows.json")]})
        for index, _ in enumerate(("new", "old")):
            state = self.points[rr.MORNING_STATE][index]
            config = self.points[rr.MORNING_CONFIG][index]
            complete = stamp(NOW - DAY + index * 60, f"complete-{index}")
            self.write(self.morning, f"{complete}-complete.json", {
                "verified": True, "stamp": complete,
                "metadata_receipt": f"{state}-backup.json",
                "config_receipt": f"{config[:-4]}-config.json"})
            self.write(self.morning, f"{state}-backup.json", {
                "verified": True, "stamp": state,
                "remote_prefix": f"{rr.MORNING_STATE}/{state}"})
            self.write(self.morning, f"{config[:-4]}-config.json", {
                "verified": True, "stamp": config[:-4],
                "remote_object": f"{rr.MORNING_CONFIG}/{config}"})

    def fake_command(self, *args):
        if args[0] in {"purge", "deletefile"}:
            self.purged.append(args[1])
            return b""
        if args[0] == "size":
            return json.dumps({"count": 1, "bytes": 9}).encode()
        if args[0] == "lsjson":
            remote = args[1]
            if remote in self.points:
                return json.dumps([{"Path": name} for name in self.points[remote]]).encode()
            return json.dumps([{"Path": "file", "Size": 1} for _ in range(3)]).encode()
        raise AssertionError("unexpected command " + str(args))

    def test_houses_latest_receipt_must_have_complete_typed_proof(self):
        point = self.points[rr.HOUSES_DAILY][0]
        path = self.base / f"houses-daily-{point}.json"
        original = json.loads(path.read_text())
        bad_files = [{"path": "../outside", "bytes": 1, "sha256": "0" * 64}] * 3
        for change in ({"status": "failed"}, {"all_file_hashes_match": False},
                       {"object_count": True}, {"files": bad_files}):
            with self.subTest(change=tuple(change)):
                self.write(self.base, path.name, {**original, **change})
                with self.assertRaises(rr.Refusal):
                    rr.load_houses_daily()
        self.write(self.base, path.name, original)
        self.assertEqual(len(rr.load_houses_daily()), 2)

    def test_full_plan_and_apply_over_all_seven_families(self):
        self.purged = []
        with mock.patch.object(rr, "command", side_effect=self.fake_command), \
             mock.patch.object(rr, "local_cleanup", lambda *a, **k: []), \
             mock.patch.object(rr, "observe_cron", lambda: None):
            manifest = rr.build_plan(now=NOW)
            self.assertEqual(manifest["summary"]["families"], 7)
            expected = {name for family in self.points.values() for name in family if "old" in name}
            deleted = {name for names in rr.delete_sets(manifest).values() for name in names}
            self.assertEqual(deleted, expected)
            rr.apply_plan(manifest, now=NOW)
        self.assertEqual(len(self.purged), len(expected))
        for value in self.purged:
            self.assertTrue(value.endswith(tuple(expected)))




class TrustedInputModeTests(unittest.TestCase):
    def test_installed_executable_is_public_readable_but_config_stays_private(self):
        binary = Path("/usr/local/libexec/vps-recovery/bin/rclone")
        config = Path("/etc/vps-recovery/rclone.conf")
        def info(path):
            if path == binary:
                return SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0)
            if path == config:
                return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0)
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        with mock.patch.object(Path, "lstat", info), mock.patch.object(rr, "RCLONE", binary), mock.patch.object(rr, "CONFIG", config):
            rr.assert_trusted_inputs()
        with mock.patch.object(Path, "lstat", lambda path: SimpleNamespace(st_mode=(stat.S_IFREG | 0o644) if path == config else (stat.S_IFDIR | 0o755), st_uid=0)):
            with self.assertRaises(rr.Refusal):
                rr.assert_trusted_file(config)
