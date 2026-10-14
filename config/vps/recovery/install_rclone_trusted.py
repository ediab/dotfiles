#!/usr/bin/env python3
"""Install the retention job's rclone dependency under trusted root ownership.

The live retention job executes rclone as root. This installer replaces a
user-writable dependency with a root-owned copy whose sha256 matches the
official rclone v1.75.2 linux-amd64 release, so an unprivileged account cannot
modify the binary root executes.

TOCTOU rule: the artifact is opened once with ``O_NOFOLLOW``, its bytes are read
once into an immutable payload, and *those bytes* are hashed, installed and
re-hashed on the installed target before the version check runs. Nothing is
re-read from the source path after the initial read, and no download occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid
import zipfile

RCLONE_VERSION = "rclone v1.75.2"
RCLONE_BINARY_SHA256 = "ed7ab1f17876bb006c3df3949a3044959671afd9112362dacaa5dd1647735bc1"
RCLONE_ZIP_SHA256 = "349ac8fba6ff65d6247043f1750cdcb518ec5d500ef91463a10d37c0ccdf3702"
DEFAULT_TARGET = Path("/usr/local/libexec/vps-recovery/bin/rclone")
DEFAULT_ROLLBACK = Path("/var/backups/vps-recovery/rclone")
MAX_ARTIFACT_BYTES = 200 * 1024 * 1024


class RcloneRefusal(RuntimeError):
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


def assert_trusted_ancestors(path: Path, *, owner: int = 0) -> None:
    for ancestor in [path.parent, *path.parents]:
        if ancestor == Path("/"):
            continue
        try:
            info = ancestor.lstat()
        except OSError as exc:
            raise RcloneRefusal("ancestor unavailable") from exc
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != owner
                or info.st_mode & 0o022):
            raise RcloneRefusal("untrusted ancestor: " + str(ancestor))


def payload_from_artifact(artifact: Path, *, expected_sha: str, enforce_trust: bool,
                          owner: int = 0) -> bytes:
    if artifact.is_symlink():
        raise RcloneRefusal("artifact is a symlink")
    try:
        fd = os.open(artifact, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise RcloneRefusal("artifact unavailable") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT_BYTES:
            raise RcloneRefusal("artifact type or size refused")
        if enforce_trust and (info.st_uid != owner or info.st_mode & 0o022):
            raise RcloneRefusal("artifact is user-writable or foreign-owned")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            payload = handle.read(MAX_ARTIFACT_BYTES + 1)
        if len(payload) > MAX_ARTIFACT_BYTES:
            raise RcloneRefusal("artifact exceeds size bound")
    finally:
        if fd >= 0:
            os.close(fd)
    if artifact.suffix == ".zip":
        if sha256_bytes(payload) != RCLONE_ZIP_SHA256:
            raise RcloneRefusal("rclone zip hash mismatch")
        payload = extract_binary(payload)
    if sha256_bytes(payload) != expected_sha:
        raise RcloneRefusal("rclone binary hash mismatch")
    return payload


def extract_binary(zip_payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(zip_payload)) as bundle:
        members = [name for name in bundle.namelist()
                   if name.rstrip("/").endswith("/rclone") and "/" in name.rstrip("/")]
        if len(members) != 1:
            raise RcloneRefusal("rclone zip layout unexpected")
        data = bundle.read(members[0])
    if not data:
        raise RcloneRefusal("rclone zip member empty")
    return data


def verify_version(target: Path, *, runner=subprocess.run) -> None:
    result = runner([str(target), "version"], capture_output=True, timeout=15, check=False)
    first = result.stdout.splitlines()[0].decode("ascii", "replace") if result.stdout else ""
    if result.returncode != 0 or first != RCLONE_VERSION:
        raise RcloneRefusal("rclone version mismatch after install")


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


def install(*, payload: bytes, target: Path, rollback_dir: Path, expected_sha: str,
            enforce_trust: bool, owner: int = 0, runner=subprocess.run) -> str:
    if sha256_bytes(payload) != expected_sha:
        raise RcloneRefusal("payload does not match the pinned hash")
    if enforce_trust:
        assert_trusted_ancestors(target, owner=owner)
        assert_trusted_ancestors(rollback_dir, owner=owner)
    if os.path.islink(target):
        raise RcloneRefusal("target is a symlink")
    current = None
    if target.exists():
        info = target.lstat()
        if enforce_trust:
            assert_target_trusted(info, owner=owner)
        elif not stat.S_ISREG(info.st_mode):
            raise RcloneRefusal("target is not a regular file")
        current = target.read_bytes()
        if sha256_bytes(current) == expected_sha:
            verify_version(target, runner=runner)
            return "idempotent"
    rollback_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(rollback_dir, 0o700)
    if current is not None:
        backup_name = f"rclone.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.{uuid.uuid4().hex[:8]}"
        _atomic_write(rollback_dir / backup_name, current, mode=0o755, owner=owner)
        _atomic_write(rollback_dir / "rclone.last-backup.json",
                      json.dumps({"backup": backup_name, "sha256": sha256_bytes(current),
                                  "replaced_with_sha256": expected_sha, "at": time.time()}).encode(),
                      mode=0o600, owner=owner)
    _atomic_write(target, payload, mode=0o755, owner=owner)
    if sha256_file(target) != expected_sha:
        raise RcloneRefusal("installed target hash mismatch")
    verify_version(target, runner=runner)
    return "installed"


def assert_target_trusted(info, *, owner: int = 0) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise RcloneRefusal("target is not a regular file")
    if info.st_uid != owner or info.st_mode & 0o022:
        raise RcloneRefusal("existing target is user-writable or foreign-owned")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True,
                        help="local rclone binary or official release zip")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--rollback-dir", type=Path, default=DEFAULT_ROLLBACK)
    parser.add_argument("--expected-sha256", default=None)
    parser.add_argument("--lock-path", type=Path, default=Path("/home/diab/ops/r2-rollout-live.lock"))
    parser.add_argument("--operator-quiesced", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--test-paths", action="store_true")
    parser.add_argument("--test-root", type=Path, default=None)
    args = parser.parse_args(argv)

    enforce_trust = not args.test_paths
    if enforce_trust and os.geteuid() != 0:
        raise RcloneRefusal("root required")
    if args.test_paths:
        if not args.test_root:
            raise RcloneRefusal("--test-paths requires --test-root")
        root = Path(args.test_root).resolve()
        for path in (args.artifact, args.target, args.rollback_dir):
            if not is_relative_to(path.resolve(), root):
                raise RcloneRefusal("test path outside the test root")
        if args.target.resolve() == DEFAULT_TARGET.resolve():
            raise RcloneRefusal("test paths cannot reach the real target")
    expected = RCLONE_BINARY_SHA256
    if args.expected_sha256 is not None:
        if not args.test_paths:
            raise RcloneRefusal("expected-hash override is test-only")
        expected = args.expected_sha256

    payload = payload_from_artifact(args.artifact, expected_sha=expected,
                                    enforce_trust=enforce_trust)
    if not args.apply:
        print(f"verify ok sha256={expected} target={args.target} (pass --apply to install)")
        return 0
    if enforce_trust:
        if not args.operator_quiesced:
            raise RcloneRefusal("operator quiescence assertion required")
        if Path(args.lock_path).exists():
            raise RcloneRefusal("shared rollout lock present; refusing to mutate")
    result = install(payload=payload, target=args.target, rollback_dir=args.rollback_dir,
                     expected_sha=expected, enforce_trust=enforce_trust)
    print(f"rclone={result} target={args.target} sha256={expected}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except RcloneRefusal as exc:
        print(f"rclone installer refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"rclone installer failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
