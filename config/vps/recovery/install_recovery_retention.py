#!/usr/bin/env python3
"""Controlled installer/rollback for the rolling seven-day recovery retention job.

Trust rules:

* The source file must match an exact, reviewed sha256 supplied by the operator
  (``--expected-source-sha256``); optionally it must also be a clean, committed
  Git blob (``--source-repo``/``--source-relpath``). A self-computed hash is
  never accepted as proof.
* A live file whose content is neither the pinned frozen baseline nor the
  reviewed revision refuses. Symlinks (including dangling) refuse.
* Root-owned directories and ancestors are validated in real mode; writes are
  atomic and the installed bytes are re-hashed.
* Rollback is driven by the recorded ``last-backup.json`` receipt, verifies the
  backup hash and refuses when the live file drifted from the recorded
  ``replaced_with_sha256``.
* ``--apply``/``--rollback`` require the operator quiescence assertion
  (``--operator-quiesced``) and the shared rollout lock must be absent.

``--test-paths`` exists only for guard tests against a temporary root; it cannot
reach the real system paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid

DEFAULT_LIVE = Path("/usr/local/libexec/vps-recovery/lean-recovery-retention.py")
DEFAULT_ROLLBACK = Path("/var/backups/vps-recovery")
DEFAULT_LOCK = Path("/home/diab/ops/r2-rollout-live.lock")
FROZEN_BASELINE_SHA256 = "dbcada01236b45c97faec60d0348f953520ebec23bf70a3a1f7d3439d56385ef"


class InstallRefusal(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def classify_current(current: bytes | None, *, baseline_sha: str, new_sha: str) -> str:
    if current is None:
        return "fresh"
    digest = sha256_bytes(current)
    if digest == baseline_sha:
        return "adopt"
    if digest == new_sha:
        return "idempotent"
    return "refuse"


def assert_trusted_ancestors(path: Path, *, owner: int = 0) -> None:
    for ancestor in [path.parent, *path.parents]:
        if ancestor == Path("/"):
            continue
        try:
            info = ancestor.lstat()
        except OSError as exc:
            raise InstallRefusal("ancestor unavailable") from exc
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != owner
                or info.st_mode & 0o022):
            raise InstallRefusal("untrusted ancestor: " + str(ancestor))


def read_live(live: Path) -> bytes | None:
    if os.path.islink(live):  # covers dangling links too
        raise InstallRefusal("live script is a symlink")
    if not live.exists():
        return None
    info = live.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise InstallRefusal("live script is not a regular file")
    return live.read_bytes()


def _atomic_write(path: Path, payload: bytes, *, mode: int, owner: int | None) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = path.parent / ("." + path.name + "." + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if owner is not None and os.geteuid() == 0:
            os.chown(temporary, owner, owner)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def install(*, source: Path, live: Path, rollback_dir: Path, expected_source_sha: str,
            baseline_sha: str, enforce_trust: bool, owner: int = 0) -> str:
    if source.is_symlink() or not source.is_file():
        raise InstallRefusal("source is not a regular file")
    payload = source.read_bytes()  # read once; these exact bytes are installed
    if sha256_bytes(payload) != expected_source_sha:
        raise InstallRefusal("source does not match the reviewed hash")
    if enforce_trust:
        assert_trusted_ancestors(live, owner=owner)
        assert_trusted_ancestors(rollback_dir, owner=owner)
    current = read_live(live)
    action = classify_current(current, baseline_sha=baseline_sha, new_sha=expected_source_sha)
    if action == "refuse":
        raise InstallRefusal("unrecognised live retention script")
    if action == "idempotent":
        if sha256_file(live) != expected_source_sha:
            raise InstallRefusal("idempotent live hash mismatch")
        return action
    rollback_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(rollback_dir, 0o700)
    if current is not None:
        backup_name = f"{live.name}.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.{uuid.uuid4().hex[:8]}"
        _atomic_write(rollback_dir / backup_name, current, mode=0o755, owner=owner)
        _atomic_write(rollback_dir / f"{live.name}.last-backup.json",
                      json.dumps({"backup": backup_name, "sha256": sha256_bytes(current),
                                  "replaced_with_sha256": expected_source_sha,
                                  "at": time.time()}).encode(), mode=0o600, owner=owner)
    _atomic_write(live, payload, mode=0o755, owner=owner)
    if sha256_file(live) != expected_source_sha:
        raise InstallRefusal("installed live hash mismatch")
    return action


def rollback(*, live: Path, rollback_dir: Path, enforce_trust: bool, owner: int = 0) -> str:
    if enforce_trust:
        assert_trusted_ancestors(live, owner=owner)
        assert_trusted_ancestors(rollback_dir, owner=owner)
    receipt_path = rollback_dir / f"{live.name}.last-backup.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise InstallRefusal("no recorded rollback receipt")
    receipt = json.loads(receipt_path.read_bytes())
    backup_name = receipt.get("backup")
    if not isinstance(backup_name, str) or Path(backup_name).name != backup_name:
        raise InstallRefusal("rollback receipt invalid")
    backup = rollback_dir / backup_name
    if backup.is_symlink() or not backup.is_file():
        raise InstallRefusal("recorded rollback backup missing")
    payload = backup.read_bytes()
    if sha256_bytes(payload) != receipt.get("sha256"):
        raise InstallRefusal("rollback backup hash mismatch")
    current = read_live(live)
    if current is None or sha256_bytes(current) != receipt.get("replaced_with_sha256"):
        raise InstallRefusal("live content drifted since install; refusing rollback")
    _atomic_write(live, payload, mode=0o755, owner=owner)
    return sha256_bytes(payload)


def assert_git_lineage(repo: Path, relpath: str, expected_sha: str) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(["/usr/bin/git", "-C", str(repo), *args],
                                capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            raise InstallRefusal("git lineage check failed")
        return result.stdout.strip()
    if git("status", "--porcelain", "--", relpath):
        raise InstallRefusal("reviewed source has uncommitted changes")
    if git("hash-object", relpath) != git("rev-parse", "HEAD:" + relpath):
        raise InstallRefusal("reviewed source differs from the committed blob")
    if sha256_file(repo / relpath) != expected_sha:
        raise InstallRefusal("reviewed source hash mismatch")


def _guard_test_paths(args) -> None:
    if not args.test_root:
        raise InstallRefusal("--test-paths requires --test-root")
    root = Path(args.test_root).resolve()
    for path in (args.live_script, args.rollback_dir):
        if not is_relative_to(path.resolve(), root):
            raise InstallRefusal("test path outside the test root")
    if (args.live_script.resolve() == DEFAULT_LIVE.resolve()
            or args.rollback_dir.resolve() == DEFAULT_ROLLBACK.resolve()):
        raise InstallRefusal("test paths cannot reach real targets")


def _guard_quiescence(args, *, enforce_trust: bool) -> None:
    if not enforce_trust:
        return
    if not args.operator_quiesced:
        raise InstallRefusal("operator quiescence assertion required")
    if Path(args.lock_path).exists():
        raise InstallRefusal("shared rollout lock present; refusing to mutate")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent / "recovery_retention.py")
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--live-script", type=Path, default=DEFAULT_LIVE)
    parser.add_argument("--rollback-dir", type=Path, default=DEFAULT_ROLLBACK)
    parser.add_argument("--baseline-sha256", default=None)
    parser.add_argument("--source-repo", type=Path, default=None)
    parser.add_argument("--source-relpath", default="config/vps/recovery/recovery_retention.py")
    parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--operator-quiesced", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--test-paths", action="store_true")
    parser.add_argument("--test-root", type=Path, default=None)
    args = parser.parse_args(argv)

    enforce_trust = not args.test_paths
    if enforce_trust and os.geteuid() != 0:
        raise InstallRefusal("root required")
    if args.test_paths:
        _guard_test_paths(args)
    baseline = FROZEN_BASELINE_SHA256
    if args.baseline_sha256 is not None:
        if not args.test_paths:
            raise InstallRefusal("baseline hash override is test-only")
        baseline = args.baseline_sha256
    if args.source_repo is not None:
        assert_git_lineage(args.source_repo, args.source_relpath, args.expected_source_sha256)

    if args.rollback:
        _guard_quiescence(args, enforce_trust=enforce_trust)
        digest = rollback(live=args.live_script, rollback_dir=args.rollback_dir,
                          enforce_trust=enforce_trust)
        print(f"rollback=complete sha256={digest}")
        return 0

    current = read_live(args.live_script)
    action = classify_current(current, baseline_sha=baseline, new_sha=args.expected_source_sha256)
    if args.verify_only:
        print(f"verify action={action} source_sha256={args.expected_source_sha256}")
        return 0 if action != "refuse" else 2
    if not args.apply:
        print(f"plan action={action} (pass --apply to install)")
        return 0
    _guard_quiescence(args, enforce_trust=enforce_trust)
    result = install(source=args.source, live=args.live_script, rollback_dir=args.rollback_dir,
                     expected_source_sha=args.expected_source_sha256, baseline_sha=baseline,
                     enforce_trust=enforce_trust)
    print(f"install={result} live={args.live_script} sha256={sha256_file(args.live_script)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except InstallRefusal as exc:
        print(f"installer refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # fail closed
        print(f"installer failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
