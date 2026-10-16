#!/usr/bin/env python3
"""Bounded native dependency scan over fixed, reviewed VPS application paths."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable
from urllib.parse import urlsplit

from core import MonitorError, atomic_json, deliver_transition, locked, read_private_json


HOME = Path("/home/diab")
TRIVY = Path("/usr/bin/trivy")
MAX_CONFIG_BYTES = 32 * 1024
MAX_INPUT_BYTES = 12 * 1024**2
MAX_TRIVY_REPORT_BYTES = 16 * 1024**2
MAX_FINAL_REPORT_BYTES = 8 * 1024**2
MAX_PACKAGES_PER_TARGET = 6000
MAX_PACKAGE_METADATA_TOTAL = 32 * 1024**2
MAX_TARGETS = 5
MAX_PACKAGE_METADATA_BYTES = 256 * 1024
MAX_SCAN_SECONDS = 1500
MAX_TARGET_SECONDS = 300
MAX_DB_AGE_SECONDS = 48 * 3600
MIN_FREE_BYTES = 5 * 1024**3
MAX_RETAINED_BYTES = 256 * 1024**2
MAX_RETAINED_REPORTS = 24
RETENTION_SECONDS = 45 * 24 * 3600
SCRATCH_RETENTION_SECONDS = 24 * 3600

PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
PACKAGE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+!_-]{0,199}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
SEVERITIES = {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
PRIVATE_PING_HOSTS = {"hc-ping.com", "healthchecks.io"}


@dataclass(frozen=True)
class Target:
    application: str
    manager: str
    root: Path
    allowed_base: Path
    manifest: str
    environment: str | None
    lock_kind: str | None
    scope: str
    require_exact_lock: bool = False
    unit: str | None = None
    unit_working_directory: str | None = None
    unit_user: str | None = None
    unit_exec_argv: tuple[str, ...] = ()
    unit_scope: str = "system"
    # Authoritative uid for this target's installed metadata when it differs from
    # the scanner user. Parent sets this when a runtime migrates to a dedicated
    # user; otherwise only the scanner uid is accepted and a foreign owner is
    # reported explicitly rather than silently trusted.
    owner: int | None = None


@dataclass(frozen=True)
class Inventory:
    target: Target
    input_name: str
    input_bytes: bytes
    fingerprint: str
    package_count: int
    binding: dict[str, Any]
    expected_packages: tuple[tuple[str, str], ...] = ()
    expected_class: str = "lang-pkgs"
    expected_type: str = ""


def default_targets(home: Path = HOME) -> tuple[Target, ...]:
    apps, dev = home / "apps", home / "Dev"
    return (
        Target("tfl", "npm", Path("/var/lib/tfl/current"), Path("/var/lib/tfl/releases"),
               "package-lock.json", "node_modules", "npm", "active-release-runtime",
               False, "tfl.service", "/var/lib/tfl/current", "tfl",
               ("/usr/bin/npm", "start", "--", "-H", "127.0.0.1", "-p", "8084")),
        Target("xbot", "python", dev / "xbot", dev, "requirements.lock", ".venv", "requirements",
               "installed-python-environment", True),
        Target("morning-brief", "python", apps / "morning-brief", apps, "requirements-lock.txt",
               ".venv", "requirements", "installed-python-environment"),
        Target("el-machine", "python", apps / "el-machine", apps, "uv.lock", ".venv", "uv",
               "installed-python-environment"),
        Target("houses", "python", apps / "houses" / "pipeline", apps / "houses", "uv.lock",
               ".venv", "uv", "installed-python-environment", False,
               "houses-health.service", str(apps / "houses" / "pipeline"), None, (), "user"),
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inside(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# Ownership and group-writability policy
#
# Installed app metadata in these user venvs is normally mode 0775/0664 with a
# private per-user group. Group-write is permitted only when nobody outside the
# file owner, root and the scanner user is in the owning group; both the primary
# group (via pwd) and explicit supplementary members (via grp) are considered.
# World-write is always refused. No live file is ever chmod-ed or modified.
# --------------------------------------------------------------------------- #
MAX_PASSWD_ENTRIES = 10000
_SCANNER_IDENTITY: tuple[str, int] | None = None
_GROUP_MEMBERS_CACHE: dict[int, frozenset[str]] = {}


def _scanner_identity() -> tuple[str, int]:
    global _SCANNER_IDENTITY
    if _SCANNER_IDENTITY is None:
        _SCANNER_IDENTITY = (pwd.getpwuid(os.getuid()).pw_name, os.getgid())
    return _SCANNER_IDENTITY


def _group_members(gid: int) -> frozenset[str]:
    cached = _GROUP_MEMBERS_CACHE.get(gid)
    if cached is not None:
        return cached
    try:
        members = set(grp.getgrgid(gid).gr_mem)
    except KeyError as exc:
        raise MonitorError("file-group-unknown") from exc
    counted = 0
    for record in pwd.getpwall():
        counted += 1
        if counted > MAX_PASSWD_ENTRIES:
            raise MonitorError("account-database-limit")
        if record.pw_gid == gid:
            members.add(record.pw_name)
    result = frozenset(members)
    _GROUP_MEMBERS_CACHE[gid] = result
    return result


def _group_write_allowed(info: stat.stat_result) -> bool:
    if not info.st_mode & 0o020:
        return True
    try:
        members = _group_members(info.st_gid)
    except MonitorError:
        return False
    allowed = {"root", _scanner_identity()[0]}
    try:
        allowed.add(pwd.getpwuid(info.st_uid).pw_name)
    except KeyError:
        pass
    return not (members - allowed)


def _writable_bits_ok(info: stat.stat_result) -> bool:
    if info.st_mode & 0o002:  # world-writable is never acceptable
        return False
    return _group_write_allowed(info)


def _ancestors_manageable(path: Path, stop: Path) -> None:
    """Check every directory between ``path`` and the trusted app root ``stop``.

    The walk stops at the app root, which _root_binding already validated; walking
    to / would refuse normal sticky world-writable system directories such as /tmp
    and per-user temp roots that are not part of the application trust boundary.
    """
    stop = stop.resolve()
    path = path.resolve()
    if stop not in path.parents:
        raise MonitorError("ancestor-stop-invalid")
    reached = False
    for ancestor in path.parents:
        if ancestor == stop:
            reached = True
            break
        try:
            info = ancestor.lstat()
        except OSError as exc:
            raise MonitorError("ancestor-unavailable") from exc
        if not stat.S_ISDIR(info.st_mode) or not _writable_bits_ok(info):
            raise MonitorError("ancestor-writable-refused")
    if not reached:
        raise MonitorError("ancestor-stop-invalid")


def _safe_regular(path: Path, *, max_bytes: int, owner: int | None = None,
                  reject_writable: bool = False) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise MonitorError("input-unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > max_bytes
                or (owner is not None and info.st_uid != owner)
                or (reject_writable and info.st_mode & 0o022)):
            raise MonitorError("input-type-or-size-refused")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            payload = stream.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise MonitorError("input-size-refused")
        return payload
    finally:
        if fd >= 0:
            os.close(fd)


def _safe_regular_at(directory: Path, name: str, *, max_bytes: int,
                     owner: int | None = None, reject_writable: bool = False) -> bytes:
    if Path(name).name != name or name in {"", ".", ".."}:
        raise MonitorError("input-name-refused")
    dir_fd = _open_absolute_directory(directory)
    fd = -1
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0), dir_fd=dir_fd)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes
                or (owner is not None and info.st_uid != owner)
                or (reject_writable and info.st_mode & 0o022)):
            raise MonitorError("input-type-or-size-refused")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            payload = stream.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise MonitorError("input-size-refused")
        return payload
    except OSError as exc:
        raise MonitorError("input-unavailable") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dir_fd)


def _canonical_package(name: str) -> str:
    if not isinstance(name, str) or not PACKAGE_NAME.fullmatch(name):
        raise MonitorError("package-name-invalid")
    return re.sub(r"[-_.]+", "-", name).lower()


def _canonical_npm_package(name: str) -> str:
    if isinstance(name, str) and name.startswith("@"):
        parts = name.split("/")
        if len(parts) == 2 and parts[0].startswith("@"):
            return "@" + _canonical_package(parts[0][1:]) + "/" + _canonical_package(parts[1])
        raise MonitorError("npm-package-name-invalid")
    return _canonical_package(name)


def _version(value: object) -> str:
    if not isinstance(value, str) or not PACKAGE_VERSION.fullmatch(value):
        raise MonitorError("package-version-invalid")
    return value


def _root_binding(target: Target) -> tuple[Path, str]:
    try:
        root = target.root.resolve(strict=True)
        allowed = target.allowed_base.resolve(strict=True)
        info = target.root.lstat()
    except OSError as exc:
        raise MonitorError("application-root-unavailable") from exc
    if not stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
        raise MonitorError("application-root-type-refused")
    if not root.is_dir() or not _inside(root, allowed):
        raise MonitorError("application-root-binding-refused")
    binding = "release-symlink" if stat.S_ISLNK(info.st_mode) else "fixed-directory"
    return root, binding


def _unit_binding(target: Target, runner=subprocess.run) -> str:
    if target.unit is None:
        return ""
    base = ["/usr/bin/systemctl"] + (["--user"] if target.unit_scope == "user" else [])
    if target.unit_scope not in {"system", "user"}:
        raise MonitorError("service-binding-definition-invalid")
    expected = {"WorkingDirectory": target.unit_working_directory}
    if target.unit_scope == "system":
        expected["User"] = target.unit_user
    for prop, wanted in expected.items():
        if not wanted:
            raise MonitorError("service-binding-definition-invalid")
        try:
            result = runner([*base, "show", "--property=" + prop, "--value", target.unit],
                            capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MonitorError("service-binding-unavailable") from exc
        if (result.returncode != 0 or not isinstance(result.stdout, str)
                or result.stdout.strip() != wanted):
            raise MonitorError("service-binding-mismatch")
    if not target.unit_exec_argv:
        return "systemd-unit-verified"
    try:
        result = runner([*base, "show", "--property=ExecStart", "--value",
                         target.unit], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MonitorError("service-binding-unavailable") from exc
    actual = result.stdout.strip() if isinstance(result.stdout, str) else ""
    match = re.search(r"(?:^|;\s*)argv\[\]=(.*?)(?:\s*;|\s*}\s*$)", actual)
    try:
        actual_argv = tuple(shlex.split(match.group(1))) if match else ()
    except ValueError:
        actual_argv = ()
    if (result.returncode != 0 or not actual or "path=/usr/bin/npm" not in actual
            or actual_argv != target.unit_exec_argv):
        raise MonitorError("service-binding-mismatch")
    return "systemd-unit-verified"


def _read_lock(target: Target, root: Path) -> bytes:
    path = root / target.manifest
    if not _inside(path, root):
        raise MonitorError("manifest-path-refused")
    # Deployment checkouts may be group writable by their release owner; the lock is
    # parsed into a sanitized manifest and re-read after scanning to detect mutation.
    return _safe_regular_at(root, target.manifest, max_bytes=MAX_INPUT_BYTES)


def _parse_requirements(payload: bytes) -> tuple[dict[str, str], bool]:
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise MonitorError("requirements-lock-invalid") from exc
    packages: dict[str, str] = {}
    hash_counts: dict[str, int] = {}
    current_package: str | None = None
    complete = True
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            line = line[:-1].rstrip()
        if line.startswith("--hash="):
            if current_package is None or not re.fullmatch(r"--hash=sha256:[0-9a-fA-F]{64}", line):
                complete = False
            else:
                hash_counts[current_package] = hash_counts.get(current_package, 0) + 1
            continue
        if line.startswith(("--index-url", "--extra-index-url", "--trusted-host", "--no-")):
            continue
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,199})==([A-Za-z0-9][A-Za-z0-9.+!_-]{0,199})(?:\s|$)", line)
        if not match:
            complete = False
            current_package = None
            continue
        name, version = _canonical_package(match.group(1)), _version(match.group(2))
        if name in packages and packages[name] != version:
            raise MonitorError("requirements-lock-duplicate-package")
        packages[name] = version
        current_package = name
        hash_counts.setdefault(name, 0)
        if "--hash=sha256:" in line:
            hash_counts[name] += len(re.findall(r"--hash=sha256:[0-9a-fA-F]{64}", line))
    complete = complete and bool(packages) and all(hash_counts.get(name, 0) > 0 for name in packages)
    return packages, complete


def _parse_uv_lock(payload: bytes) -> tuple[dict[str, str], bool]:
    try:
        lock = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise MonitorError("uv-lock-invalid") from exc
    rows = lock.get("package") if isinstance(lock, dict) else None
    if not isinstance(rows, list) or not rows or len(rows) > MAX_PACKAGES_PER_TARGET:
        raise MonitorError("uv-lock-package-list-invalid")
    packages: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise MonitorError("uv-lock-package-invalid")
        name, version = _canonical_package(row.get("name")), _version(row.get("version"))
        if name in packages and packages[name] != version:
            raise MonitorError("uv-lock-duplicate-package")
        packages[name] = version
    return packages, True


def _python_lock(target: Target, root: Path) -> tuple[dict[str, str], bool]:
    if not target.lock_kind:
        return {}, False
    try:
        payload = _read_lock(target, root)
    except MonitorError:
        return {}, False
    if target.lock_kind == "uv":
        packages, complete = _parse_uv_lock(payload)
    else:
        packages, complete = _parse_requirements(payload)
    return packages, complete


def _site_packages(environment: Path, root: Path) -> Path:
    try:
        env_info = environment.lstat()
        resolved = environment.resolve(strict=True)
    except OSError as exc:
        raise MonitorError("active-environment-unavailable") from exc
    if not stat.S_ISDIR(env_info.st_mode) and not stat.S_ISLNK(env_info.st_mode):
        raise MonitorError("active-environment-type-refused")
    if not resolved.is_dir() or not _inside(resolved, root):
        raise MonitorError("active-environment-binding-refused")
    candidates = sorted(resolved.glob("lib/python*/site-packages"))
    if len(candidates) != 1 or not _inside(candidates[0].resolve(strict=True), resolved):
        raise MonitorError("active-environment-layout-refused")
    site = candidates[0]
    site_info = site.lstat()
    if not stat.S_ISDIR(site_info.st_mode) or stat.S_ISLNK(site_info.st_mode):
        raise MonitorError("site-packages-type-refused")
    if not _writable_bits_ok(site_info):
        raise MonitorError("site-packages-writable-refused")
    _ancestors_manageable(site, root)
    return site


def _open_absolute_directory(path: Path) -> int:
    """Open each canonical path component without following a symlink race."""
    if (not path.is_absolute() or any(part in {".", ".."} for part in path.parts[1:])):
        raise MonitorError("directory-path-invalid")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        os.close(fd)
        raise MonitorError("directory-path-raced-or-unavailable") from exc


def _metadata_package(site: Path, info_name: str, owners: frozenset[int]) -> tuple[str, str, int]:
    if not info_name.endswith((".dist-info", ".egg-info")) or "/" in info_name:
        raise MonitorError("package-metadata-name-invalid")
    names = ("METADATA", "PKG-INFO")
    name = version = None
    size = 0
    site_fd = _open_absolute_directory(site)
    info_fd = -1
    fd = -1
    try:
        info_fd = os.open(info_name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                          | getattr(os, "O_NOFOLLOW", 0), dir_fd=site_fd)
        dir_info = os.fstat(info_fd)
        if not stat.S_ISDIR(dir_info.st_mode):
            raise MonitorError("package-metadata-directory-refused")
        if dir_info.st_uid not in owners:
            raise MonitorError("package-metadata-owner-unsupported")
        if not _writable_bits_ok(dir_info):
            raise MonitorError("package-metadata-directory-refused")
        filename = None
        for candidate in names:
            try:
                fd = os.open(candidate, os.O_RDONLY | os.O_NONBLOCK
                             | getattr(os, "O_NOFOLLOW", 0), dir_fd=info_fd)
                filename = candidate
                break
            except FileNotFoundError:
                continue
        if filename is None:
            raise MonitorError("package-metadata-missing")
        info = os.fstat(fd)
        # Dist-info metadata is commonly hardlinked by uv's cache. A hardlink remains
        # acceptable when the opened inode itself is regular, owned by an authorised
        # owner, bounded, and free of world/foreign group writes. O_NOFOLLOW plus
        # site-relative openat prevents a symlink swap; the descriptor pins the
        # checked inode through the read.
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_PACKAGE_METADATA_BYTES:
            raise MonitorError("package-metadata-type-or-size-refused")
        if info.st_uid not in owners:
            raise MonitorError("package-metadata-owner-unsupported")
        if not _writable_bits_ok(info):
            raise MonitorError("package-metadata-type-or-size-refused")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            while size <= MAX_PACKAGE_METADATA_BYTES:
                raw = stream.readline(4097)
                if not raw:
                    break
                size += len(raw)
                if size > MAX_PACKAGE_METADATA_BYTES or len(raw) > 4096 or not raw.endswith(b"\n"):
                    raise MonitorError("package-metadata-header-size-refused")
                if raw in (b"\n", b"\r\n"):
                    break
                line = raw.decode("utf-8", "strict").rstrip("\r\n")
                if line.startswith("Name: "):
                    if name is not None:
                        raise MonitorError("package-metadata-duplicate-name")
                    name = line[6:].strip()
                elif line.startswith("Version: "):
                    if version is not None:
                        raise MonitorError("package-metadata-duplicate-version")
                    version = line[9:].strip()
                if name is not None and version is not None:
                    break
    except UnicodeError as exc:
        raise MonitorError("package-metadata-invalid") from exc
    except OSError as exc:
        raise MonitorError("package-metadata-unavailable") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if info_fd >= 0:
            os.close(info_fd)
        os.close(site_fd)
    return _canonical_package(name), _version(version), size


def _installed_packages(environment: Path, root: Path, *, owner: int | None = None) -> tuple[Path, dict[str, str]]:
    site = _site_packages(environment, root)
    owners = frozenset({os.getuid()} | ({owner} if owner is not None else set()))
    packages: dict[str, str] = {}
    entries = sorted(site.iterdir(), key=lambda path: path.name)
    if len(entries) > 20_000:
        raise MonitorError("site-packages-entry-limit")
    metadata_dirs = [path for path in entries if path.name.endswith((".dist-info", ".egg-info"))]
    if not metadata_dirs or len(metadata_dirs) > MAX_PACKAGES_PER_TARGET:
        raise MonitorError("installed-package-count-invalid")
    metadata_bytes = 0
    for info_dir in metadata_dirs:
        if info_dir.is_symlink():
            raise MonitorError("package-metadata-link-refused")
        name, version, size = _metadata_package(site, info_dir.name, owners)
        metadata_bytes += size
        if metadata_bytes > MAX_PACKAGE_METADATA_TOTAL:
            raise MonitorError("installed-package-metadata-size-limit")
        if name in packages:
            raise MonitorError("installed-package-duplicate")
        packages[name] = version
    return site, packages


def _npm_manifest(payload: bytes, target: Target) -> tuple[bytes, int, bool]:
    try:
        original = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError("npm-lock-invalid") from exc
    if not isinstance(original, dict) or original.get("lockfileVersion") not in {2, 3}:
        raise MonitorError("npm-lock-schema-invalid")
    packages = original.get("packages")
    if not isinstance(packages, dict) or not packages:
        raise MonitorError("npm-lock-packages-invalid")
    sanitized: dict[str, Any] = {"": {"name": target.application}}
    complete = True
    for path, row in packages.items():
        if path == "":
            continue
        if (not isinstance(path, str) or not path.startswith("node_modules/")
                or "\\" in path or "" in path.split("/") or not _valid_npm_package_path(path)
                or not isinstance(row, dict)):
            raise MonitorError("npm-lock-package-entry-invalid")
        version = row.get("version")
        if not isinstance(version, str) or not PACKAGE_VERSION.fullmatch(version):
            # Workspaces/links have no fixed package version, so this lock is not complete.
            complete = False
            continue
        entry = {"version": version}
        if isinstance(row.get("dev"), bool):
            entry["dev"] = row["dev"]
        if isinstance(row.get("optional"), bool):
            entry["optional"] = row["optional"]
        sanitized[path] = entry
    if len(sanitized) <= 1 or len(sanitized) > MAX_PACKAGES_PER_TARGET:
        raise MonitorError("npm-lock-package-count-invalid")
    result = json.dumps({"name": target.application, "lockfileVersion": original["lockfileVersion"],
                         "requires": True, "packages": sanitized},
                        sort_keys=True, separators=(",", ":")).encode("utf-8")
    return result, len(sanitized) - 1, complete


def _npm_package_name_from_path(path: str) -> str:
    if not _valid_npm_package_path(path):
        raise MonitorError("npm-package-path-invalid")
    parts = path.split("/")
    names = []
    for index, part in enumerate(parts):
        if part != "node_modules":
            continue
        name = parts[index + 1]
        if name.startswith("@"):
            name += "/" + parts[index + 2]
        names.append(name)
    if not names:
        raise MonitorError("npm-package-path-invalid")
    return _canonical_npm_package(names[-1])


def _npm_lock_inventory(payload: bytes, target: Target) -> tuple[dict[str, tuple[str, str]], bool]:
    _npm_manifest(payload, target)
    original = json.loads(payload.decode("utf-8"))
    result: dict[str, tuple[str, str]] = {}
    complete = True
    for path, row in original["packages"].items():
        if path == "":
            continue
        version = row.get("version") if isinstance(row, dict) else None
        if not isinstance(version, str) or not PACKAGE_VERSION.fullmatch(version):
            complete = False
            continue
        derived = _npm_package_name_from_path(path)
        name = _canonical_npm_package(row.get("name", derived))
        if path in result:
            raise MonitorError("npm-lock-duplicate-path")
        result[path] = (name, _version(version))
    return result, complete


MAX_NPM_PACKAGE_JSON_BYTES = 64 * 1024
MAX_NPM_TREE_ENTRIES = 20_000


def _npm_package_metadata(package_dir: Path) -> tuple[str, str]:
    package_fd = _open_absolute_directory(package_dir)
    fd = -1
    try:
        dir_info = os.fstat(package_fd)
        if not stat.S_ISDIR(dir_info.st_mode) or not _writable_bits_ok(dir_info):
            raise MonitorError("npm-package-directory-refused")
        fd = os.open("package.json", os.O_RDONLY | os.O_NONBLOCK
                     | getattr(os, "O_NOFOLLOW", 0), dir_fd=package_fd)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_size > MAX_NPM_PACKAGE_JSON_BYTES
                or not _writable_bits_ok(info)):
            raise MonitorError("npm-package-metadata-refused")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            raw = stream.read(MAX_NPM_PACKAGE_JSON_BYTES + 1)
        if len(raw) > MAX_NPM_PACKAGE_JSON_BYTES:
            raise MonitorError("npm-package-metadata-size-limit")
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(package_fd)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError("npm-package-metadata-invalid") from exc
    if not isinstance(data, dict):
        raise MonitorError("npm-package-metadata-invalid")
    return _canonical_npm_package(data.get("name")), _version(data.get("version"))


def _installed_npm_packages(root: Path, environment: str) -> dict[str, tuple[str, str]]:
    modules = root / environment
    try:
        info = modules.lstat()
    except OSError as exc:
        raise MonitorError("npm-runtime-inventory-unavailable") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise MonitorError("npm-runtime-directory-refused")
    result: dict[str, tuple[str, str]] = {}
    visited = 0
    _ancestors_manageable(modules, root)

    def visit_modules(modules_dir: Path) -> None:
        nonlocal visited
        try:
            directory_info = modules_dir.lstat()
        except OSError as exc:
            raise MonitorError("npm-runtime-directory-unavailable") from exc
        if (not stat.S_ISDIR(directory_info.st_mode) or stat.S_ISLNK(directory_info.st_mode)
                or not _writable_bits_ok(directory_info)):
            raise MonitorError("npm-runtime-directory-refused")
        entries = sorted(modules_dir.iterdir(), key=lambda path: path.name)
        visited += len(entries)
        if visited > MAX_NPM_TREE_ENTRIES:
            raise MonitorError("npm-runtime-entry-limit")
        for entry in entries:
            if entry.name == ".bin":
                continue
            try:
                entry_info = entry.lstat()
            except OSError as exc:
                raise MonitorError("npm-runtime-entry-unavailable") from exc
            if entry.name == ".package-lock.json":
                # npm generates this exact regular file inside node_modules; it is not
                # a package directory. Accept only a bounded, non-symlink regular file
                # that passes the same writability policy, and refuse every other
                # hidden entry rather than guessing.
                if (not stat.S_ISREG(entry_info.st_mode) or stat.S_ISLNK(entry_info.st_mode)
                        or entry_info.st_size > MAX_INPUT_BYTES or not _writable_bits_ok(entry_info)):
                    raise MonitorError("npm-generated-metadata-refused")
                continue
            if entry.name.startswith("@"):
                if not stat.S_ISDIR(entry_info.st_mode) or stat.S_ISLNK(entry_info.st_mode):
                    raise MonitorError("npm-scope-directory-refused")
                scoped = sorted(entry.iterdir(), key=lambda path: path.name)
                visited += len(scoped)
                if visited > MAX_NPM_TREE_ENTRIES:
                    raise MonitorError("npm-runtime-entry-limit")
                candidates = scoped
            else:
                candidates = [entry]
            for package_dir in candidates:
                try:
                    package_info = package_dir.lstat()
                except OSError as exc:
                    raise MonitorError("npm-package-directory-unavailable") from exc
                if not stat.S_ISDIR(package_info.st_mode) or stat.S_ISLNK(package_info.st_mode):
                    raise MonitorError("npm-package-link-or-type-refused")
                relative = package_dir.relative_to(root).as_posix()
                if not relative.startswith("node_modules/"):
                    raise MonitorError("npm-package-containment-refused")
                package_name, version = _npm_package_metadata(package_dir)
                if relative in result:
                    raise MonitorError("npm-package-path-duplicate")
                result[relative] = (package_name, version)
                nested = package_dir / "node_modules"
                try:
                    nested_info = nested.lstat()
                except FileNotFoundError:
                    continue
                if not stat.S_ISDIR(nested_info.st_mode) or stat.S_ISLNK(nested_info.st_mode):
                    raise MonitorError("npm-nested-runtime-directory-refused")
                visit_modules(nested)

    if not _writable_bits_ok(info):
        raise MonitorError("npm-runtime-directory-mode-refused")
    visit_modules(modules)
    if not result or len(result) > MAX_PACKAGES_PER_TARGET:
        raise MonitorError("npm-runtime-package-count-invalid")
    return result


def _npm_runtime_manifest(application: str, packages: dict[str, tuple[str, str]]) -> bytes:
    rows: dict[str, Any] = {"": {"name": application}}
    for path, (name, version) in sorted(packages.items()):
        rows[path] = {"name": name, "version": version}
    return json.dumps({"name": application, "lockfileVersion": 3, "requires": True,
                       "packages": rows}, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _valid_npm_package_path(path: str) -> bool:
    parts = path.split("/")
    index = 0
    while index < len(parts):
        if parts[index] != "node_modules" or index + 1 >= len(parts):
            return False
        name = parts[index + 1]
        if name in {"", ".", "..", "node_modules"}:
            return False
        index += 2
        if name.startswith("@"):
            if index >= len(parts) or parts[index] in {"", ".", "..", "node_modules"}:
                return False
            index += 1
        if index == len(parts):
            return True
    return False


def collect_inventory(target: Target, *, unit_runner=subprocess.run) -> Inventory:
    if not SAFE_ID.fullmatch(target.application):
        raise MonitorError("application-id-invalid")
    root, root_kind = _root_binding(target)
    unit_status = _unit_binding(target, unit_runner)
    lock_bytes = _read_lock(target, root)
    if target.manager == "npm":
        lock_packages, lock_complete = _npm_lock_inventory(lock_bytes, target)
        if not target.environment:
            raise MonitorError("npm-runtime-definition-missing")
        installed = _installed_npm_packages(root, target.environment)
        input_bytes = _npm_runtime_manifest(target.application, installed)
        package_count = len(installed)
        mismatches = sum(1 for package_path, value in installed.items()
                         if lock_packages.get(package_path) != value)
        complete = lock_complete and package_count > 0 and mismatches == 0
        binding = {
            "application": target.application,
            "scope": target.scope,
            "release_binding": root_kind,
            "unit_binding": unit_status,
            "environment_binding": "installed-npm-name-version",
            "lock_binding": "matched" if complete else "mismatch-or-unpinned",
            "coverage_complete": complete,
            "dependency_count": package_count,
        }
        binding["lock_mismatch_count"] = mismatches
        binding["coverage_note"] = ("installed-npm-name-version-matches-active-release-lock"
                                     if complete else "installed-runtime-not-fully-bound-to-lock")
        input_name = "package-lock.json"
        # Trivy reports each name/version once even when nested copies exist.
        # The manifest/fingerprint still binds every installed path and version.
        expected_packages = tuple(sorted(set(installed.values())))
        expected_type = "npm"
    elif target.manager == "python":
        if not target.environment:
            raise MonitorError("python-environment-definition-missing")
        environment = root / target.environment
        site, installed = _installed_packages(environment, root, owner=target.owner)
        if not installed:
            raise MonitorError("installed-package-inventory-empty")
        lock_packages, lock_complete = _python_lock(target, root)
        mismatch = sorted(name for name, version in installed.items()
                          if lock_packages.get(name) != version)
        missing = sorted(name for name in lock_packages if name not in installed)
        lock_matched = lock_complete and not mismatch and (not target.require_exact_lock or not missing)
        binding = {
            "application": target.application,
            "scope": target.scope,
            "release_binding": root_kind,
            **({"unit_binding": unit_status} if unit_status else {}),
            "environment_binding": "active-path-resolved",
            "lock_binding": "matched" if lock_matched else "mismatch-or-unpinned",
            "coverage_complete": lock_matched,
            "dependency_count": len(installed),
        }
        input_name = "requirements.txt"
        lines = [f"{name}=={version}" for name, version in sorted(installed.items())]
        input_bytes = ("\n".join(lines) + "\n").encode("ascii")
        expected_packages = tuple(sorted(installed.items()))
        expected_type = "pip"
        if mismatch or (target.require_exact_lock and missing):
            # Keep names out of reports. A nonempty mismatch count is enough to explain
            # why this scan cannot claim lock-bound coverage.
            binding["lock_mismatch_count"] = len(mismatch) + (len(missing) if target.require_exact_lock else 0)
        if not lock_complete:
            binding["coverage_note"] = "installed-packages-scanned;source-lock-not-fully-pinned"
        elif not lock_matched:
            binding["coverage_note"] = "installed-packages-scanned;installed-set-not-bound-to-lock"
        else:
            binding["coverage_note"] = "installed-metadata-name-version-only;all-installed-packages-in-lock"
        if not _inside(site.resolve(strict=True), root):
            raise MonitorError("site-packages-escaped-application-root")
    else:
        raise MonitorError("package-manager-not-supported")
    if len(input_bytes) > MAX_INPUT_BYTES:
        raise MonitorError("normalized-manifest-size-limit")
    environment_identity = str((root / target.environment).resolve(strict=True)) if target.environment else ""
    identity = _sha((str(root) + "\0" + environment_identity + "\0" + unit_status
                     + "\0" + _sha(lock_bytes) + "\0" + _sha(input_bytes)).encode("utf-8"))
    return Inventory(target, input_name, input_bytes, identity,
                     package_count if target.manager == "npm" else len(installed), binding,
                     expected_packages, "lang-pkgs", expected_type)


def _db_updated_at(path: Path, *, now: int, owner: int) -> int:
    try:
        payload = _safe_regular(path, max_bytes=8192, owner=owner, reject_writable=True)
        metadata = json.loads(payload.decode("utf-8"))
        value = metadata.get("UpdatedAt") if isinstance(metadata, dict) else None
        if not isinstance(value, str):
            raise MonitorError("trivy-db-metadata-invalid")
        updated = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            raise MonitorError("trivy-db-timestamp-invalid")
        timestamp = int(updated.timestamp())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise MonitorError("trivy-db-metadata-invalid") from exc
    if timestamp > now + 300 or now - timestamp > MAX_DB_AGE_SECONDS:
        raise MonitorError("trivy-db-stale")
    return timestamp


def _validate_trivy(report: Any, inventory: Inventory, *, expected_artifact: str) -> list[dict[str, str]]:
    if (not isinstance(report, dict) or report.get("SchemaVersion") != 2
            or not isinstance(report.get("ArtifactName"), str) or not report["ArtifactName"]
            or report["ArtifactName"] != expected_artifact
            or report.get("ArtifactType") != "filesystem"
            # Trivy omits zero-valued Metadata for package-only filesystems.
            or ("Metadata" in report and not isinstance(report["Metadata"], dict))
            or not isinstance(report.get("Results"), list) or not report["Results"]
            or not inventory.expected_packages or not inventory.expected_type):
        raise MonitorError("trivy-filesystem-report-invalid")
    found = []
    observed_packages: list[tuple[str, str]] = []
    for result in report["Results"]:
        if (not isinstance(result, dict) or not isinstance(result.get("Target"), str)
                or not isinstance(result.get("Class"), str) or not result["Class"]
                or not isinstance(result.get("Type"), str) or not result["Type"]
                or Path(result["Target"]).name != inventory.input_name
                or result["Class"] != inventory.expected_class
                or result["Type"].lower() != inventory.expected_type.lower()):
            raise MonitorError("trivy-result-invalid")
        packages = result.get("Packages")
        if not isinstance(packages, list):
            raise MonitorError("trivy-packages-invalid")
        for package in packages:
            if (not isinstance(package, dict) or not isinstance(package.get("Name"), str)
                    or not isinstance(package.get("Version"), str)):
                raise MonitorError("trivy-package-fields-invalid")
            canonicalize = _canonical_npm_package if inventory.expected_type.lower() == "npm" else _canonical_package
            observed_packages.append((canonicalize(package["Name"]), _version(package["Version"])))
        vulnerabilities = result.get("Vulnerabilities")
        if vulnerabilities is None:
            vulnerabilities = []
        if not isinstance(vulnerabilities, list):
            raise MonitorError("trivy-vulnerabilities-invalid")
        for finding in vulnerabilities:
            if not isinstance(finding, dict):
                raise MonitorError("trivy-finding-invalid")
            required = ("VulnerabilityID", "PkgName", "InstalledVersion", "Severity")
            if any(not isinstance(finding.get(key), str) or not finding[key] for key in required):
                raise MonitorError("trivy-finding-fields-invalid")
            severity = finding["Severity"].upper()
            if severity not in SEVERITIES:
                raise MonitorError("trivy-finding-severity-invalid")
            canonicalize = _canonical_npm_package if inventory.expected_type.lower() == "npm" else _canonical_package
            if (canonicalize(finding["PkgName"]), _version(finding["InstalledVersion"])) not in inventory.expected_packages:
                raise MonitorError("trivy-finding-package-foreign")
            found.append({
                "application": inventory.target.application,
                "vulnerability_id": _safe_summary(finding["VulnerabilityID"]),
                "package": _safe_summary(finding["PkgName"]),
                "installed_version": _safe_summary(finding["InstalledVersion"]),
                "fixed_version": _safe_summary(str(finding.get("FixedVersion", ""))),
                "severity": severity,
            })
    if Counter(observed_packages) != Counter(inventory.expected_packages):
        raise MonitorError("trivy-package-coverage-mismatch")
    return sorted(found, key=lambda item: tuple(item[key] for key in (
        "application", "vulnerability_id", "package", "installed_version", "severity")))


def _safe_summary(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._:+-]", "_", value)
    return value[:160]


def _write_input(path: Path, payload: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _disk_guard(path: Path, *, min_free_bytes: int, disk_usage=shutil.disk_usage) -> None:
    if disk_usage(path).free < min_free_bytes:
        raise MonitorError("free-space-hard-floor")


def _prune_reports(config: dict[str, Any], *, now: int) -> None:
    report_dir = config["report_dir"]
    candidates = []
    total = 0
    for path in report_dir.glob("native-scan-*.json"):
        try:
            info = path.lstat()
        except OSError as exc:
            raise MonitorError("report-retention-inspection-failed") from exc
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise MonitorError("report-retention-untrusted-file")
        candidates.append((info.st_mtime, path, info.st_size))
        total += info.st_size
    candidates.sort()
    keep = list(candidates)
    for item in candidates:
        stale = now - item[0] > config["retention_seconds"]
        too_many = len(keep) > config["max_retained_reports"]
        too_large = total > config["max_total_report_bytes"]
        if stale or too_many or too_large:
            item[1].unlink()
            keep.remove(item)
            total -= item[2]
    if total + config["max_report_bytes"] > config["max_total_report_bytes"]:
        raise MonitorError("retained-report-budget-exhausted")


def _prune_scratch(state_dir: Path, *, now: int) -> None:
    leftovers = []
    for path in state_dir.glob("native-scan-*"):
        try:
            info = path.lstat()
        except OSError as exc:
            raise MonitorError("scratch-retention-inspection-failed") from exc
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise MonitorError("scratch-retention-untrusted-directory")
        leftovers.append((info.st_mtime, path))
    for modified, path in leftovers:
        if now - modified > SCRATCH_RETENTION_SECONDS:
            shutil.rmtree(path)
    if sum(1 for modified, _path in leftovers if now - modified <= SCRATCH_RETENTION_SECONDS) > 1:
        raise MonitorError("scratch-retention-count-limit")


def _scan_one(inventory: Inventory, scratch: Path, config: dict[str, Any], *,
              timeout: int, runner=subprocess.run) -> list[dict[str, str]]:
    input_dir = scratch / inventory.target.application
    input_dir.mkdir(mode=0o700)
    input_path = input_dir / inventory.input_name
    output_path = scratch / (inventory.target.application + ".trivy.json")
    _write_input(input_path, inventory.input_bytes)
    command = [
        str(config["trivy_path"]), "--cache-dir", str(config["trivy_cache_dir"]),
        "fs", "--scanners", "vuln", "--format", "json", "--quiet", "--include-dev-deps",
        "--list-all-pkgs",
        "--offline-scan", "--skip-db-update", "--skip-java-db-update", "--skip-check-update",
        "--skip-version-check", "--disable-telemetry", "--parallel", "1",
        "--timeout", f"{timeout}s", "--ignorefile", "/dev/null", "--output", str(output_path),
        str(input_dir),
    ]
    env = {"HOME": str(HOME), "PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
           "TRIVY_DISABLE_TELEMETRY": "true"}
    completed = runner(command, check=False, timeout=timeout, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, env=env)
    if completed.returncode != 0:
        raise MonitorError("trivy-filesystem-exit")
    payload = _safe_regular(output_path, max_bytes=config["max_trivy_report_bytes"], owner=os.getuid(),
                            reject_writable=True)
    try:
        trivy_report = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError("trivy-filesystem-json-invalid") from exc
    return _validate_trivy(trivy_report, inventory, expected_artifact=str(input_dir))


def _summary(report: dict[str, Any], previous: dict[str, Any], scan_id: str) -> tuple[str | None, str | None]:
    old_status = previous.get("status")
    old_findings = previous.get("findings", [])
    if not isinstance(old_findings, list) or any(not isinstance(item, dict) for item in old_findings):
        raise MonitorError("native-notification-state-invalid")
    status = report["status"]
    if status == "error":
        codes = ",".join(sorted({item["code"] for item in report["errors"]})) or "unknown"
        lines = [f"VPS native dependency scan failed; scan_id={scan_id}; errors={codes}."]
        old = {json.dumps(item, sort_keys=True) for item in old_findings}
        current = {json.dumps(item, sort_keys=True) for item in report["findings"]}
        added = current - old
        if added:
            lines.append(f"New findings discovered before scan failure; count={len(added)}.")
            for encoded in sorted(added)[:25]:
                item = json.loads(encoded)
                lines.append("NEW " + " ".join(f"{key}={item[key]}" for key in (
                    "application", "vulnerability_id", "package", "installed_version", "fixed_version", "severity")))
            if len(added) > 25:
                lines.append(f"Additional new findings omitted: {len(added) - 25}.")
        return "scan_error", "\n".join(lines)
    if old_status == "error" and status != "findings":
        return "recovered", f"VPS native dependency scan recovered; status={status}; findings={len(report['findings'])}; scan_id={scan_id}."
    if status == "findings":
        old = {json.dumps(item, sort_keys=True) for item in old_findings}
        current = {json.dumps(item, sort_keys=True) for item in report["findings"]}
        added, removed = current - old, old - current
        if added or removed or old_status != "findings":
            lines = [f"VPS native dependency findings changed; scan_id={scan_id}; total={len(current)}; new_or_changed={len(added)}; resolved={len(removed)}."]
            for encoded in sorted(added)[:25]:
                item = json.loads(encoded)
                lines.append("NEW " + " ".join(f"{key}={item[key]}" for key in (
                    "application", "vulnerability_id", "package", "installed_version", "fixed_version", "severity")))
            if len(added) > 25:
                lines.append(f"Additional new findings omitted: {len(added) - 25}.")
            for encoded in sorted(removed)[:15]:
                item = json.loads(encoded)
                lines.append("RESOLVED " + " ".join(f"{key}={item[key]}" for key in (
                    "application", "vulnerability_id", "package", "installed_version", "severity")))
            if len(removed) > 15:
                lines.append(f"Additional resolved findings omitted: {len(removed) - 15}.")
            return "findings_changed", "\n".join(lines)
    elif old_status == "findings":
        return "findings_cleared", f"VPS native dependency findings cleared; scan_id={scan_id}."
    return None, None


def _email_sender(config: dict[str, Any]) -> Callable[[str], bool]:
    root = Path(config["email_transport_root"])
    for name in ("summary_config.py", "scrape_timeline.py"):
        path = root / name
        try:
            info = path.lstat()
        except OSError as exc:
            raise MonitorError("existing-email-transport-unavailable") from exc
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise MonitorError("existing-email-transport-untrusted")
    sys.path.insert(0, str(root))
    try:
        from summary_config import load_environment
        from scrape_timeline import DEFAULT_CURL_EXPIRY_EMAIL, send_alert_email
        load_environment(root)
        recipient = os.getenv("DIGEST_RECIPIENT_EMAIL", "").strip() or DEFAULT_CURL_EXPIRY_EMAIL
        if not recipient:
            raise MonitorError("existing-email-recipient-unavailable")

        def send(body: str) -> bool:
            try:
                return bool(send_alert_email(recipient, "VPS native dependency vulnerability scan", body))
            except Exception as exc:
                raise MonitorError("existing-email-delivery-failed") from exc
        return send
    except MonitorError:
        raise
    except Exception as exc:
        raise MonitorError("existing-email-transport-initialization-failed") from exc


def _read_state(path: Path, *, max_bytes: int = MAX_FINAL_REPORT_BYTES) -> dict[str, Any]:
    try:
        path.lstat()
    except FileNotFoundError:
        return {}
    value = read_private_json(path, max_bytes=max_bytes)
    if not isinstance(value, dict):
        raise MonitorError("native-state-invalid")
    return value


def run_scan(config: dict[str, Any], *, targets: tuple[Target, ...] | None = None,
             runner=subprocess.run, send_email: Callable[[str], bool] | None = None,
             unit_runner=subprocess.run,
             now: int | None = None, clock: Callable[[], float] = time.time,
             disk_usage=shutil.disk_usage) -> tuple[dict[str, Any], int]:
    started = int(clock()) if now is None else now
    state_dir, report_dir = config["state_dir"], config["report_dir"]
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    report_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    os.chmod(report_dir, 0o700)
    selected = default_targets() if targets is None else targets
    if not selected or len(selected) > MAX_TARGETS or len({target.application for target in selected}) != len(selected):
        raise MonitorError("native-target-set-invalid")
    lock_path = state_dir / "scan.lock"  # Shared with the existing Docker image scanner.
    with locked(lock_path):
        scan_id = datetime.fromtimestamp(started, timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        report: dict[str, Any] = {
            "schema_version": 1,
            "artifact_type": "filesystem",
            "scan_id": scan_id,
            "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
            "status": "error",
            "coverage_status": "partial",
            "targets": [{"application": target.application, "scope": target.scope,
                         "coverage_complete": False, "binding": "not-scanned"}
                        for target in selected],
            "findings": [],
            "errors": [],
        }
        scratch: Path | None = None
        inventories: list[Inventory] = []
        initial_identity: dict[str, str] = {}
        deadline = time.monotonic() + config["overall_timeout_seconds"]
        completed_at = started
        try:
            _prune_scratch(state_dir, now=started)
            scratch = Path(tempfile.mkdtemp(prefix="native-scan-", dir=state_dir))
            os.chmod(scratch, 0o700)
            _disk_guard(report_dir.parent, min_free_bytes=config["min_free_bytes"], disk_usage=disk_usage)
            db_timestamp = _db_updated_at(config["trivy_cache_dir"] / "db" / "metadata.json",
                                          now=started, owner=os.getuid())
            report["trivy_database_updated_at"] = datetime.fromtimestamp(db_timestamp, timezone.utc).isoformat()
            target_rows = {target["application"]: index for index, target in enumerate(report["targets"])}
            for target in selected:
                try:
                    inventory = collect_inventory(target, unit_runner=unit_runner)
                    inventories.append(inventory)
                    initial_identity[target.application] = inventory.fingerprint
                    report["targets"][target_rows[target.application]] = inventory.binding
                except (MonitorError, OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError) as exc:
                    detail = _safe_summary(str(exc)) if isinstance(exc, MonitorError) else "unclassified"
                    report["errors"].append({"application": target.application, "code": "inventory_failed",
                                             "detail": detail})
                    report["targets"][target_rows[target.application]] = {
                        "application": target.application, "scope": target.scope,
                        "coverage_complete": False, "binding": "failed"}
            for inventory in inventories:
                try:
                    _disk_guard(report_dir.parent, min_free_bytes=config["min_free_bytes"], disk_usage=disk_usage)
                    remaining = int(deadline - time.monotonic())
                    if remaining < 1:
                        raise MonitorError("overall-timeout")
                    timeout = min(config["per_target_timeout_seconds"], remaining)
                    if scratch is None:
                        raise MonitorError("private-scratch-unavailable")
                    report["findings"].extend(_scan_one(inventory, scratch, config,
                                                        timeout=timeout, runner=runner))
                except subprocess.TimeoutExpired:
                    report["errors"].append({"application": inventory.target.application, "code": "trivy-timeout"})
                except (MonitorError, OSError, UnicodeError, json.JSONDecodeError):
                    report["errors"].append({"application": inventory.target.application, "code": "trivy-failed"})
            for target in selected:
                if target.application not in initial_identity:
                    continue
                try:
                    final = collect_inventory(target, unit_runner=unit_runner)
                    if final.fingerprint != initial_identity[target.application]:
                        report["errors"].append({"application": target.application,
                                                 "code": "inventory-changed-during-scan"})
                except (MonitorError, OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError):
                    report["errors"].append({"application": target.application,
                                             "code": "inventory-recheck-failed"})
            if any(not target.get("coverage_complete") for target in report["targets"]):
                report["errors"].append({"code": "coverage-incomplete"})
            report["status"] = "error" if report["errors"] else ("findings" if report["findings"] else "clean")
            report["coverage_status"] = "complete" if not report["errors"] else "incomplete"
        except (MonitorError, OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
            report["errors"].append({"code": str(exc) if str(exc) in {
                "free-space-hard-floor", "trivy-db-stale", "trivy-db-metadata-invalid"} else "scan-prerequisite-failed"})
            report["status"] = "error"
            report["coverage_status"] = "incomplete"
        finally:
            completed_at = int(clock())
            try:
                if (scratch is not None and scratch.is_dir() and not scratch.is_symlink()
                        and scratch.parent == state_dir):
                    shutil.rmtree(scratch)
            except OSError:
                report["errors"].append({"code": "private-scratch-cleanup-failed"})
                report["status"] = "error"
                report["coverage_status"] = "incomplete"
        report["completed_at"] = datetime.fromtimestamp(completed_at, timezone.utc).isoformat()
        report["findings"] = sorted(report["findings"], key=lambda item: tuple(item[key] for key in (
            "application", "vulnerability_id", "package", "installed_version", "severity")))
        report["identity"] = _sha(json.dumps({
            "targets": [{"application": item.get("application"),
                         "dependency_count": item.get("dependency_count")} for item in report["targets"]],
            "inventory_hashes": initial_identity,
            "findings": report["findings"], "errors": report["errors"]}, sort_keys=True,
            separators=(",", ":")).encode("utf-8"))
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > config["max_report_bytes"]:
            report["status"] = "error"
            report["coverage_status"] = "incomplete"
            report["findings"] = []
            report["errors"].append({"code": "aggregate-report-size-limit"})
            encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(encoded) > config["max_report_bytes"]:
                raise MonitorError("native-report-error-state-exceeds-bound")
        _prune_reports(config, now=completed_at)
        report_path = report_dir / f"native-scan-{scan_id}.json"
        atomic_json(report_path, report)
        state_path = state_dir / "native-notifications.json"
        state = _read_state(state_path, max_bytes=config["max_report_bytes"])
        event, summary = _summary(report, state, scan_id)
        if event is not None and summary is not None:
            fingerprint = _sha(json.dumps({"event": event, "identity": report["identity"],
                                           "status": report["status"]}, sort_keys=True,
                                          separators=(",", ":")).encode("utf-8"))
            sender = send_email or _email_sender(config)
            deliver_transition(state_path, fingerprint, sender, summary, event=event, now=completed_at,
                               extra={"status": report["status"],
                                      "findings": report["findings"] if report["status"] != "error" else state.get("findings", []),
                                      "last_success_at": completed_at if report["status"] != "error" else state.get("last_success_at")},
                               state_max_bytes=config["max_report_bytes"])
        else:
            state.update({"status": report["status"],
                          "findings": report["findings"] if report["status"] != "error" else state.get("findings", []),
                          "last_success_at": completed_at if report["status"] != "error" else state.get("last_success_at")})
            atomic_json(state_path, state)
        atomic_json(state_dir / "native-run.json", {"completed_at": completed_at,
                                                     "status": report["status"], "scan_id": scan_id,
                                                     "report": report_path.name})
        return report, 1 if report["status"] == "error" else 0


def validate_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MonitorError("native-scan-config-invalid")
    paths = {}
    for key in ("state_dir", "report_dir", "email_transport_root", "trivy_cache_dir"):
        raw = value.get(key)
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise MonitorError("native-scan-path-config-invalid")
        paths[key] = Path(raw)
    expected_paths = {
        "state_dir": HOME / ".local/state/vps-security-scan",
        "report_dir": HOME / ".local/state/vps-security-scan/reports",
        "email_transport_root": HOME / "Dev/xbot",
        "trivy_cache_dir": HOME / ".cache/trivy",
    }
    if any(paths[key] != expected for key, expected in expected_paths.items()):
        raise MonitorError("native-scan-path-config-refused")
    if (paths["report_dir"] != paths["state_dir"] / "reports"
            or paths["state_dir"].is_symlink() or paths["report_dir"].is_symlink()):
        raise MonitorError("native-scan-state-path-refused")
    floor = value.get("min_free_bytes", MIN_FREE_BYTES)
    total = value.get("overall_timeout_seconds", MAX_SCAN_SECONDS)
    per_target = value.get("per_target_timeout_seconds", MAX_TARGET_SECONDS)
    max_report = value.get("max_report_bytes", MAX_FINAL_REPORT_BYTES)
    max_trivy_report = value.get("max_trivy_report_bytes", MAX_TRIVY_REPORT_BYTES)
    if (type(floor) is not int or floor < MIN_FREE_BYTES
            or type(total) is not int or not 120 <= total <= MAX_SCAN_SECONDS
            or type(per_target) is not int or not 30 <= per_target <= MAX_TARGET_SECONDS
            or type(max_report) is not int or not 65536 <= max_report <= MAX_FINAL_REPORT_BYTES
            or type(max_trivy_report) is not int
            or not 65536 <= max_trivy_report <= MAX_TRIVY_REPORT_BYTES):
        raise MonitorError("native-scan-bounds-invalid")
    hc = value.get("healthchecks", {})
    if not isinstance(hc, dict) or type(hc.get("enabled", False)) is not bool:
        raise MonitorError("native-healthchecks-config-invalid")
    for field in ("native_ping_url", "watchdog_ping_url"):
        url = hc.get(field, "")
        if not isinstance(url, str) or len(url) > 256:
            raise MonitorError("native-healthchecks-url-invalid")
        if hc.get("enabled"):
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname not in PRIVATE_PING_HOSTS
                    or not parsed.path.strip("/") or parsed.query or parsed.fragment
                    or parsed.port not in (None, 443) or "@" in url or "\n" in url):
                raise MonitorError("native-healthchecks-url-invalid")
    return {**paths, "min_free_bytes": floor,
            "overall_timeout_seconds": total, "per_target_timeout_seconds": per_target,
            "max_report_bytes": max_report,
            "max_trivy_report_bytes": max_trivy_report,
            "max_retained_reports": MAX_RETAINED_REPORTS,
            "max_total_report_bytes": MAX_RETAINED_BYTES,
            "retention_seconds": RETENTION_SECONDS,
            "healthchecks": hc, "trivy_path": TRIVY}


def ping(base_url: str, status: str, *, timeout: float = 5.0, opener=None) -> bool:
    if status not in {"start", "0", "1"}:
        raise ValueError("unsupported Healthchecks ping status")
    request = urllib.request.Request(base_url.rstrip("/") + "/" + status, data=b"", method="POST")
    try:
        if opener is None:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler()).open
        with opener(request, timeout=timeout) as response:
            response.read(513)
            return 200 <= response.status < 300
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path.home() / ".config/vps-security-scan/native.json")
    args = parser.parse_args()
    ping_base = None
    started = False
    status = 2
    try:
        config = validate_config(read_private_json(args.config, max_bytes=MAX_CONFIG_BYTES))
        hc = config["healthchecks"]
        if hc.get("enabled"):
            ping_base = hc["native_ping_url"]
            started = ping(ping_base, "start")
            if not started:
                print("native Healthchecks start ping failed", file=sys.stderr)
        report, status = run_scan(config)
        print(f"scan_id={report['scan_id']} artifact_type=filesystem status={report['status']} targets={len(report['targets'])} findings={len(report['findings'])} errors={len(report['errors'])}")
    except (MonitorError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"native scanner could not complete: {type(exc).__name__}", file=sys.stderr)
    finally:
        if ping_base:
            if not ping(ping_base, "1" if status != 0 or not started else "0"):
                print("native Healthchecks completion ping failed", file=sys.stderr)
                if status == 0:
                    status = 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
