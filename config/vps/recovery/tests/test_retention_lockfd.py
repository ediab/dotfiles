#!/usr/bin/env python3
"""Real OS race tests for the retention lock/completion-status primitives.

The job runs as root out of the diab-owned `/home/diab/ops` tree, so the lock
and receipt paths are attacker-controllable. These tests run the shipped
primitives unprivileged against a temporary tree: after root creates the lock
(or the receipt directory exists), the identity renames it and points the
original path at a symlink. No write, replace or unlink may land outside the
directory that was opened, and the foreign directory must be left untouched.

Run: python3 config/vps/recovery/tests/test_retention_lockfd.py
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

RECOVERY = Path(__file__).resolve().parents[1]
SOURCE = RECOVERY / "recovery_retention.py"


def load():
    spec = importlib.util.spec_from_file_location("recovery_retention_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve annotations through sys.modules on import.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RetentionLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="retention-lockfd-")
        self.root = Path(self.temp.name)
        self.ops = self.root / "ops"
        self.ops.mkdir(mode=0o700)
        self.canary = self.root / "canary"
        self.canary.mkdir(mode=0o755)
        self.receipts = self.root / "receipts"
        self.receipts.mkdir(mode=0o700)
        self.m = load()
        self.m.ROOT_UID = os.getuid()
        self.m._diab_uid = lambda: os.getuid()
        self.m.LOCK = self.ops / "r2-rollout-live.lock"
        self.m.BASE = self.receipts

    def tearDown(self):
        self.temp.cleanup()

    def canary_entries(self):
        return sorted(p.name for p in self.canary.iterdir())

    def test_normal_acquire_release_round_trip(self):
        handle = self.m.acquire_lock()
        self.assertTrue((self.m.LOCK / "owner").is_file())
        self.m.release_lock(handle)
        self.assertFalse(self.m.LOCK.exists())

    def test_rename_then_symlink_cannot_redirect_release(self):
        handle = self.m.acquire_lock()
        retained = self.ops / "retained-lock"
        os.rename(self.m.LOCK, retained)
        self.m.LOCK.symlink_to(self.canary)
        self.m.release_lock(handle)
        self.assertEqual(self.canary_entries(), [])
        self.assertTrue(self.m.LOCK.is_symlink())
        self.assertFalse((retained / "owner").exists())

    def test_owner_mismatch_retains_the_lock_and_keeps_the_descriptor(self):
        handle = self.m.acquire_lock()
        (self.m.LOCK / "owner").chmod(0o600)
        (self.m.LOCK / "owner").write_text("someone-else\n")
        with self.assertRaises(self.m.Refusal):
            self.m.release_lock(handle)
        self.assertTrue(self.m.LOCK.exists())
        (self.m.LOCK / "owner").write_text(self.m.OWNER + "\n")
        self.m.release_lock(handle)
        self.assertFalse(self.m.LOCK.exists())

    def test_foreign_root_dir_with_canary_owner_is_left_untouched(self):
        self.m.LOCK.mkdir(mode=0o700)
        owner = self.m.LOCK / "owner"
        owner.write_text("canary-owner\n")
        os.chmod(owner, 0o600)
        with self.assertRaises(self.m.Refusal):
            self.m.acquire_lock()
        self.assertTrue(self.m.LOCK.is_dir())
        self.assertEqual(owner.read_text(), "canary-owner\n")

    def test_precreated_symlink_lock_is_refused(self):
        self.m.LOCK.symlink_to(self.canary)
        with self.assertRaises(self.m.Refusal):
            self.m.acquire_lock()
        self.assertEqual(self.canary_entries(), [])


class RetentionStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="retention-status-")
        self.root = Path(self.temp.name)
        self.canary = self.root / "canary"
        self.canary.mkdir(mode=0o755)
        self.receipts = self.root / "receipts"
        self.receipts.mkdir(mode=0o700)
        self.m = load()
        self.m.ROOT_UID = os.getuid()
        self.m._diab_uid = lambda: os.getuid()
        self.m.BASE = self.receipts

    def tearDown(self):
        self.temp.cleanup()

    def test_completion_status_is_published_with_unchanged_name(self):
        self.m.write_completion_status("a" * 64)
        status = self.receipts / "lean-retention-complete.json"
        self.assertTrue(status.is_file())
        self.assertEqual(stat.S_IMODE(status.stat().st_mode), 0o600)
        body = json.loads(status.read_text())
        self.assertEqual(body["policy"], "seven-day-rolling")
        self.assertEqual(body["manifest_sha256"], "a" * 64)

    def test_substituted_receipt_directory_cannot_redirect_the_status(self):
        retained = self.root / "retained-receipts"
        os.rename(self.receipts, retained)
        self.m.BASE.symlink_to(self.canary)
        with self.assertRaises(self.m.Refusal):
            self.m.write_completion_status("b" * 64)
        self.assertEqual(sorted(p.name for p in self.canary.iterdir()), [])
        self.assertEqual(sorted(p.name for p in retained.iterdir()), [])

    def test_renamed_receipt_directory_still_receives_the_status(self):
        os.rename(self.receipts, self.root / "moved-receipts")
        self.m.BASE = self.root / "moved-receipts"
        self.m.write_completion_status("c" * 64)
        self.assertTrue((self.root / "moved-receipts/lean-retention-complete.json").is_file())


class RetentionCleanupTests(unittest.TestCase):
    """Local point deletion must stay inside the directory that was opened."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="retention-cleanup-")
        self.root = Path(self.temp.name)
        self.points = self.root / "points"
        self.points.mkdir(mode=0o700)
        self.canary = self.root / "canary"
        self.canary.mkdir(mode=0o755)
        self.old = "20260101T000000Z-aaaaaaaa-0000-0000-0000-000000000000"
        self.new = "20260102T000000Z-bbbbbbbb-0000-0000-0000-000000000000"
        (self.points / self.old).mkdir(mode=0o700)
        (self.points / self.old / "nested").mkdir(mode=0o700)
        (self.points / self.old / "nested" / "file.bin").write_text("x")
        (self.points / self.old / "top.bin").write_text("y")
        (self.points / self.new).mkdir(mode=0o700)
        (self.points / self.new / "keep.bin").write_text("z")
        self.m = load()
        self.ts_old = self.m.parse_point_timestamp(self.old)
        self.ts_new = self.m.parse_point_timestamp(self.new)

    def tearDown(self):
        self.temp.cleanup()

    def test_removes_only_superseded_points(self):
        removed = self.m.local_cleanup(self.points, self.ts_old, anchor=self.root,
                                        anchor_uid=os.getuid(),
                                        allowed_owners=(os.getuid(),))
        self.assertEqual(removed, [self.old])
        self.assertFalse((self.points / self.old).exists())
        self.assertTrue((self.points / self.new / "keep.bin").is_file())

    def test_rename_then_symlink_cannot_redirect_the_delete(self):
        retained = self.root / "retained-points"
        os.rename(self.points, retained)
        self.points.symlink_to(self.canary)
        # The retained descriptor deletes inside the real directory only.
        removed = self.m.local_cleanup(retained, self.ts_old, anchor=self.root,
                                        anchor_uid=os.getuid(),
                                        allowed_owners=(os.getuid(),))
        self.assertEqual(removed, [self.old])
        self.assertEqual(sorted(p.name for p in self.canary.iterdir()), [])
        self.assertFalse((retained / self.old).exists())

    def test_symlinked_root_is_refused(self):
        root_link = self.root / "points-link"
        root_link.symlink_to(self.canary)
        with self.assertRaises(self.m.Refusal):
            self.m.local_cleanup(root_link, self.ts_old, anchor=self.root,
                                  anchor_uid=os.getuid(),
                                  allowed_owners=(os.getuid(),))
        self.assertEqual(sorted(p.name for p in self.canary.iterdir()), [])

    def test_nested_symlink_inside_a_point_is_unlinked_not_followed(self):
        link = self.points / self.old / "escape"
        link.symlink_to(self.canary)
        self.m.local_cleanup(self.points, self.ts_old, anchor=self.root,
                              anchor_uid=os.getuid(),
                              allowed_owners=(os.getuid(),))
        self.assertEqual(sorted(p.name for p in self.canary.iterdir()), [])
        self.assertFalse((self.points / self.old).exists())


class IntermediateLinkTests(unittest.TestCase):
    """Every path component is opened no-follow from a trusted anchor."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="retention-intermediate-")
        self.root = Path(self.temp.name)
        self.m = load()
        self.calls = dict(anchor=self.root, anchor_uid=os.getuid(),
                          allowed_owners=(os.getuid(),))

    def tearDown(self):
        self.temp.cleanup()

    def test_intermediate_symlink_cannot_delete_outside_files(self):
        logical = self.root / "recovery"
        logical.mkdir(mode=0o700)
        outside = self.root / "outside-private"
        point = outside / "houses" / "20200101T000000Z-canary"
        point.mkdir(mode=0o700, parents=True)
        canary = point / "keep.bin"
        canary.write_bytes(b"outside data")
        (logical / "points").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(self.m.Refusal):
            self.m.local_cleanup(logical / "points" / "houses", 1580515200, **self.calls)
        self.assertTrue(canary.exists())
        self.assertEqual(canary.read_bytes(), b"outside data")

    def test_final_symlink_is_refused(self):
        outside = self.root / "outside"
        outside.mkdir(mode=0o700)
        link = self.root / "houses"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(self.m.Refusal):
            self.m.local_cleanup(link, 1580515200, **self.calls)

    def test_missing_cleanup_root_is_a_no_op_and_is_not_created(self):
        missing = self.root / "absent" / "houses"
        self.assertEqual(self.m.local_cleanup(missing, 1580515200, **self.calls), [])
        self.assertFalse(missing.exists())
        self.assertFalse(missing.parent.exists())

    def test_deep_tree_is_refused_by_the_depth_bound(self):
        root = self.root / "captures"
        old = root / "20200101T000000Z-deep"
        deep = old
        for index in range(self.m.CLEANUP_MAX_DEPTH + 5):
            deep = deep / ("d" + str(index))
        deep.mkdir(mode=0o700, parents=True)
        with self.assertRaises(self.m.Refusal):
            self.m.local_cleanup(root, 1580515200, **self.calls)
        self.assertTrue(old.exists())


class PublishedArtifactCompletenessTests(unittest.TestCase):
    """Exercise the shipped artifact, with no external worker checkout dependency."""

    def test_required_live_callbacks_and_receipt_helpers_exist(self):
        module = load()
        for name in ("load_houses_daily", "morning_timer_present", "observe_cron",
                     "write_manifest", "write_completion_status", "_write_all",
                     "read_fd_bytes", "read_private_bytes", "_diab_uid"):
            self.assertTrue(callable(getattr(module, name, None)), name)
        self.assertTrue(module.HOUSES_DAILY)
        self.assertIn("recursive-listing-count", SOURCE.read_text())

    def test_no_undefined_global_references_in_any_scope(self):
        import builtins
        import symtable
        table = symtable.symtable(SOURCE.read_text(), str(SOURCE), "exec")
        globals_bound = {symbol.get_name() for symbol in table.get_symbols()
                         if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()}
        globals_bound.update(dir(builtins))
        globals_bound.update(("__file__", "__name__", "__package__", "__spec__", "__builtins__"))

        def check(scope):
            for symbol in scope.get_symbols():
                if symbol.is_referenced() and symbol.is_global():
                    self.assertIn(symbol.get_name(), globals_bound,
                                  f"{scope.get_name()}: undefined {symbol.get_name()}")
            for child in scope.get_children():
                check(child)

        check(table)


if __name__ == "__main__":
    unittest.main()
