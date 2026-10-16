#!/usr/bin/env python3
"""Rolling seven-day off-host recovery retention with verified-point protection.

This supersedes the frozen single-point baseline
(`baseline/lean-recovery-retention.frozen.py`, sha256 recorded in
`provenance/frozen-baseline.json`). It keeps a rolling week of *verified*
recovery points while always preserving the newest verified point in each
family, regardless of age.

Safety model (fail closed):

* Each mandatory family must have a newest receipt whose full proof passes; a
  missing mandatory proof refuses the whole run rather than silently preserving
  everything and reporting success.
* A point may be deleted only when it is positively bound to a passing receipt,
  lies strictly outside the rolling seven-day window, and is strictly older than
  the newest verified point of its family. Equal timestamps or fractional-second
  ties are never deleted.
* The newest verified point is never deleted, however old it is.
* Newer, in-progress, ambiguous and unparsable names are never deleted.
* Immediately before the first mutation the plan is recomputed and every
  candidate is re-validated against freshly loaded receipts; any policy, proof
  or protected-point drift refuses the run before a single delete is issued.
* Deletion commands themselves are irreversible once issued; correctness relies
  on validation before mutation, not on post-hoc atomicity.

Installed location: ``/usr/local/libexec/vps-recovery/lean-recovery-retention.py``
(the deployed unit calls that path; the source file name differs only for
importability in tests).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from typing import Any, Iterable

# Trusted, root-owned dependency and inputs. The rclone binary is installed by
# install_rclone_trusted.py; the private config is a root-owned snapshot created
# by the parent (other jobs keep their existing diab-owned config).
RCLONE = Path("/usr/local/libexec/vps-recovery/bin/rclone")
CONFIG = Path("/etc/vps-recovery/rclone.conf")
BASE = Path("/home/diab/ops/r2-recovery/receipts")
MORNING = Path("/var/lib/vps-native-backup/morning-brief/receipts")
LOCK = Path("/home/diab/ops/r2-rollout-live.lock")
# Owner uid the lock/receipt primitives must verify. Production is root; the
# module constant exists so the OS race tests can run unprivileged.
ROOT_UID = 0
MANIFEST_DIR = Path("/var/lib/vps-recovery/manifests")
STATUS_DIR = Path("/var/lib/vps-recovery")
CRON_CONFIG = Path("/home/diab/.config/vps-backups/monitor-recovery.json")
NOTE_LOCAL = Path("/var/backups/note-sx/current-coolify-captures")
HOUSES_LOCAL = Path("/home/diab/ops/r2-recovery/points/houses")

OWNER = "lean-recovery-retention"
RCLONE_VERSION = "rclone v1.75.2"
RETENTION_SECONDS = 7 * 24 * 3600
CLOCK_SKEW_SECONDS = 300
MAX_RECEIPTS = 10000
MAX_RECEIPT_BYTES = 262144
MAX_LISTING_ROWS = 10000
MAX_REMOTE_BYTES = 2 * 1024 * 1024
DEADLINE_SECONDS = 480

STAMP = re.compile(r"^20\d{6}T\d{6}(?:\d+)?Z[-.]")
POINT = re.compile(r"^(?P<stamp>20\d{6}T\d{6})(?:\d+)?Z[-.][^\s/]+$")

NOTE_SX = "r2crypt:note-sx/state"
CRATCH = "r2crypt:cratch/state"
FOUSEKIS = "r2crypt:fousekis/state"
REDACT = "r2crypt:redact/state"
MORNING_STATE = "r2crypt:morning-brief/state"
MORNING_CONFIG = "r2crypt:morning-brief/config"
HOUSES_DAILY = "r2crypt:houses/recovery/daily-source-closure/db"

# Frozen-baseline object-count default for app state points.
APP_DEFAULT_OBJECT_COUNT = 3


class Refusal(RuntimeError):
    """A fail-closed condition; the run must not prune what it cannot prove."""


@dataclass(frozen=True)
class VerifiedPoint:
    name: str
    timestamp: int
    shape: str                      # "listing-count" or "size"
    expected_count: int | None      # exact object count for "listing-count"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    is_dir: bool
    loader: str


SPECS: tuple[FamilySpec, ...] = (
    FamilySpec(NOTE_SX, True, "note-sx"),
    FamilySpec(CRATCH, True, "app"),
    FamilySpec(FOUSEKIS, True, "app"),
    FamilySpec(REDACT, True, "app"),
    FamilySpec(MORNING_STATE, True, "morning-state"),
    FamilySpec(MORNING_CONFIG, False, "morning-config"),
    FamilySpec(HOUSES_DAILY, True, "houses-daily"),
)

APP_RECEIPTS = (
    ("cratch", "cratch-neon-state-*-complete.json", CRATCH),
    ("fousekis", "fousekis-state-*.json", FOUSEKIS),
    ("redact", "redact-state-*.json", REDACT),
)

_START = time.monotonic()
_TRUSTED_INPUTS_CHECKED = False


# --------------------------------------------------------------------------- #
# Strict identity parsing
# --------------------------------------------------------------------------- #
def parse_point_timestamp(name: str) -> int | None:
    """Return the point's own UTC timestamp, or None when it is not a strict,
    whole-name ``YYYYMMDDThhmmss[frac]Z[-.]...`` identity."""
    if not isinstance(name, str):
        return None
    match = POINT.fullmatch(name)
    if match is None:
        return None
    try:
        parsed = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    return int(parsed.replace(tzinfo=timezone.utc).timestamp())


def is_stamped_name(name: str) -> bool:
    return isinstance(name, str) and STAMP.match(name) is not None


# --------------------------------------------------------------------------- #
# Trusted inputs
# --------------------------------------------------------------------------- #
def assert_trusted_file(path: Path, *, owner: int = 0, private: bool = True) -> None:
    """Require a root-owned private regular file under root-owned ancestors."""
    try:
        info = path.lstat()
    except OSError as exc:
        raise Refusal("trusted input unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner
            or info.st_mode & (0o077 if private else 0o022)):
        raise Refusal("trusted input ownership or mode refused")
    for ancestor in path.parents:
        if ancestor == Path("/"):
            continue
        try:
            ancestor_info = ancestor.lstat()
        except OSError as exc:
            raise Refusal("trusted ancestor unavailable") from exc
        if (not stat.S_ISDIR(ancestor_info.st_mode) or ancestor_info.st_uid != owner
                or ancestor_info.st_mode & 0o022):
            raise Refusal("trusted ancestor ownership or mode refused")


def assert_trusted_inputs() -> None:
    global _TRUSTED_INPUTS_CHECKED
    assert_trusted_file(RCLONE, private=False)
    assert_trusted_file(CONFIG)
    _TRUSTED_INPUTS_CHECKED = True


# --------------------------------------------------------------------------- #
# Bounded rclone access
# --------------------------------------------------------------------------- #
def command(*args: str) -> bytes:
    if not _TRUSTED_INPUTS_CHECKED:
        raise Refusal("trusted inputs unchecked")
    remaining = DEADLINE_SECONDS - (time.monotonic() - _START)
    if remaining <= 0:
        raise Refusal("retention deadline")
    result = subprocess.run(
        [str(RCLONE), *args, "--config", str(CONFIG), "--timeout", "20s",
         "--retries", "1", "--low-level-retries", "1"],
        capture_output=True, timeout=min(remaining, 180))
    if result.returncode or len(result.stdout) > MAX_REMOTE_BYTES:
        raise Refusal("bounded rclone operation refused")
    return result.stdout


def list_json(*args: str) -> list[dict[str, Any]]:
    rows = json.loads(command("lsjson", *args))
    if not isinstance(rows, list) or len(rows) > MAX_LISTING_ROWS:
        raise Refusal("remote listing refused")
    return rows


def remote_children(family: str, is_dir: bool) -> list[str]:
    rows = list_json(family, "--dirs-only" if is_dir else "--files-only")
    names = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("Path"), str):
            raise Refusal("remote listing row invalid")
        name = row["Path"].rstrip("/")
        if "/" in name or name in {"", ".", ".."}:
            # Nested or ambiguous entries are preserved, never planned for deletion.
            continue
        names.append(name)
    return names


def assert_remote_point(family: str, point: VerifiedPoint) -> None:
    """Positively bind the preserved point to the remote namespace and shape."""
    target = f"{family}/{point.name}"
    if point.shape == "size":
        result = json.loads(command("size", target, "--json"))
        if (not isinstance(result, dict) or not isinstance(result.get("count"), int)
                or result["count"] < 1 or not isinstance(result.get("bytes"), int)
                or result["bytes"] < 1):
            raise Refusal("protected remote object missing")
        return
    if point.shape not in {"listing-count", "recursive-listing-count"}:
        raise Refusal("protected remote shape unknown")
    flags = ["--files-only"]
    if point.shape == "recursive-listing-count":
        flags.append("--recursive")
    rows = list_json(target, *flags)
    if not rows:
        raise Refusal("protected remote set empty")
    if point.expected_count is not None and len(rows) != point.expected_count:
        raise Refusal("protected remote set count mismatch")
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("Size"), int)
                or row["Size"] < 0):
            raise Refusal("protected remote object type mismatch")


# --------------------------------------------------------------------------- #
# Private receipt reading
# --------------------------------------------------------------------------- #
def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise Refusal("short write")
        view = view[written:]


def read_fd_bytes(fd: int, size: int, label: str) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = os.read(fd, min(remaining, 1 << 20))
        if not chunk:
            raise Refusal(label + " changed during read")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(fd, 1):
        raise Refusal(label + " grew during read")
    return b"".join(chunks)


def read_private_bytes(path: Path, maximum: int, label: str) -> bytes:
    """Descriptor read of a private file; a FIFO or device refuses immediately.

    Receipts and monitor configs live under directories the agent identity can
    write, so the path can be replaced between checks. O_NONBLOCK stops a
    substituted FIFO from blocking root, and the descriptor shape is checked
    before any byte is read.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise Refusal(label + " unavailable") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise Refusal("unsafe " + label)
        chunks = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1 << 20))
            if not chunk:
                raise Refusal(label + " changed during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise Refusal(label + " grew during read")
        return b"".join(chunks)
    finally:
        os.close(fd)


def document(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
    except OSError as exc:
        raise Refusal("receipt unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
            or info.st_size > MAX_RECEIPT_BYTES):
        raise Refusal("unsafe receipt")
    value = json.loads(read_private_bytes(path, MAX_RECEIPT_BYTES, "receipt"))
    if not isinstance(value, dict):
        raise Refusal("receipt shape invalid")
    return value


def receipts(root: Path, pattern: str) -> list[Path]:
    found = sorted(root.glob(pattern))
    if len(found) > MAX_RECEIPTS:
        raise Refusal("receipt inventory")
    return found


def _family_child(remote: object, family: str) -> str:
    if not isinstance(remote, str) or not remote.startswith(family + "/"):
        raise Refusal("receipt namespace binding")
    child = remote[len(family) + 1:]
    if not child or "/" in child or child in {".", ".."} or POINT.fullmatch(child) is None:
        raise Refusal("receipt namespace binding")
    return child


def _newest_receipt_refuses_without_proof(best: tuple[int, str, bool] | None, family: str) -> None:
    if best is None:
        raise Refusal(f"{family} receipt inventory missing")
    if not best[2]:
        raise Refusal(f"{family} newest receipt proof missing")


def load_note_sx() -> dict[str, VerifiedPoint]:
    paths = receipts(BASE, "note-sx-state-*.json")
    best: tuple[int, str, bool] | None = None
    points: dict[str, VerifiedPoint] = {}
    for path in paths:
        data = document(path)
        child = _family_child(data.get("remote_prefix"), NOTE_SX)
        # The producer assigns separate local-capture and remote-point IDs.
        # Bind the receipt to its capture; retain/delete by its verified remote ID.
        capture = data.get("capture_id")
        if (parse_point_timestamp(capture) is None
                or path.name != f"note-sx-state-{capture}.json"):
            raise Refusal("note-sx receipt identity mismatch")
        timestamp = parse_point_timestamp(child)
        if timestamp is None:
            raise Refusal("note-sx receipt identity invalid")
        passing = (data.get("readback") == "exact-set-and-sha256-pass"
                   and data.get("restore") == "pass"
                   and data.get("database_check") == "pass"
                   and data.get("consumer", {}).get("recovered_html") == "pass")
        if passing:
            count = data.get("readback_file_count")
            if type(count) is not int or count < 1:
                raise Refusal("note-sx receipt set count invalid")
            points[child] = VerifiedPoint(child, timestamp, "listing-count", count)
        if best is None or (timestamp, child) > (best[0], best[1]):
            best = (timestamp, child, passing)
    _newest_receipt_refuses_without_proof(best, "note-sx")
    if not points:
        raise Refusal("note-sx verified point set empty")
    return points


def load_app(glob: str, family: str) -> dict[str, VerifiedPoint]:
    paths = receipts(BASE, glob)
    best: tuple[int, str, bool] | None = None
    points: dict[str, VerifiedPoint] = {}
    for path in paths:
        data = document(path)
        child = _family_child(data.get("r2_prefix"), family)
        timestamp = parse_point_timestamp(child)
        if timestamp is None:
            raise Refusal("app receipt identity invalid")
        proof = data.get("proof")
        passing = isinstance(proof, dict) and proof.get("fresh_exact_set_readback") is True
        if family == CRATCH:
            passing = passing and proof.get("schema_row_sequence_closure") is True
        if passing:
            count = data.get("object_count", APP_DEFAULT_OBJECT_COUNT)
            if type(count) is not int or count < 1:
                raise Refusal("app receipt set count invalid")
            points[child] = VerifiedPoint(child, timestamp, "listing-count", count)
        if best is None or (timestamp, child) > (best[0], best[1]):
            best = (timestamp, child, passing)
    _newest_receipt_refuses_without_proof(best, family)
    if not points:
        raise Refusal("app verified point set empty")
    return points


def load_morning() -> tuple[dict[str, VerifiedPoint], dict[str, VerifiedPoint]]:
    """Return verified state and config points.

    The newest complete receipt must be ``verified`` and both of its linked
    subreceipts must themselves be ``verified`` with an identity-bound remote
    binding. The linked-receipt schema was inspected read-only on 2026-10-14 and
    carries ``verified: true`` plus ``stamp``/``completed``; parent confirms.
    """
    paths = receipts(MORNING, "*-complete.json")
    best: tuple[int, str, bool] | None = None
    state: dict[str, VerifiedPoint] = {}
    config: dict[str, VerifiedPoint] = {}
    for path in paths:
        data = document(path)
        stamp = data.get("stamp")
        if not isinstance(stamp, str) or POINT.fullmatch(stamp) is None:
            raise Refusal("morning complete receipt identity invalid")
        timestamp = parse_point_timestamp(stamp)
        if timestamp is None:
            raise Refusal("morning complete receipt identity invalid")
        passing = data.get("verified") is True
        local_state: dict[str, VerifiedPoint] = {}
        local_config: dict[str, VerifiedPoint] = {}
        for key, family, field, target in (
            ("metadata_receipt", MORNING_STATE, "remote_prefix", local_state),
            ("config_receipt", MORNING_CONFIG, "remote_object", local_config),
        ):
            linked = data.get(key)
            if not isinstance(linked, str) or Path(linked).name != linked:
                raise Refusal("morning receipt link escape")
            sub = document(MORNING / linked)
            if sub.get("verified") is not True:
                passing = False
                continue
            sub_stamp = sub.get("stamp")
            if not isinstance(sub_stamp, str):
                raise Refusal("morning receipt identity invalid")
            child = _family_child(sub.get(field), family)
            if not (child == sub_stamp or child.startswith(sub_stamp + ".")):
                raise Refusal("morning receipt identity mismatch")
            child_timestamp = parse_point_timestamp(child)
            if child_timestamp is None:
                raise Refusal("morning receipt identity invalid")
            target[child] = VerifiedPoint(child, child_timestamp, "size", None)
        if passing and local_state and local_config:
            state.update(local_state)
            config.update(local_config)
        elif passing:
            passing = False
        if best is None or (timestamp, stamp) > (best[0], best[1]):
            best = (timestamp, stamp, passing)
    _newest_receipt_refuses_without_proof(best, "morning-brief")
    if not state or not config:
        raise Refusal("morning verified point set empty")
    return state, config


def load_houses_daily() -> dict[str, VerifiedPoint]:
    best = None
    points = {}
    for path in receipts(BASE, "houses-daily-*.json"):
        data = document(path)
        child = _family_child(data.get("remote"), HOUSES_DAILY)
        timestamp = parse_point_timestamp(child)
        if (timestamp is None or data.get("backup_id") != child
                or path.name != f"houses-daily-{child}.json"):
            raise Refusal("Houses daily receipt identity mismatch")
        files = data.get("files")
        passing = (data.get("status") == "complete"
                   and all(data.get(field) is True for field in (
                       "conditional_create", "independent_download_verified",
                       "all_file_hashes_match", "manual_table_digests_equal",
                       "sequences_verified", "container_cleanup")))
        if passing:
            count = data.get("object_count")
            if (type(count) is not int or not 2 <= count <= 100
                    or not isinstance(files, list) or len(files) != count):
                raise Refusal("Houses daily file set invalid")
            seen = set()
            for entry in files:
                name = entry.get("path") if isinstance(entry, dict) else None
                if (not isinstance(name, str) or name.startswith("/") or "\\" in name
                        or any(part in {"", ".", ".."} for part in name.split("/"))
                        or name in seen or type(entry.get("bytes")) is not int
                        or entry["bytes"] < 0 or not isinstance(entry.get("sha256"), str)
                        or re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is None):
                    raise Refusal("Houses daily file manifest invalid")
                seen.add(name)
            if not {"manifest.json", "notebook.dump"}.issubset(seen):
                raise Refusal("Houses daily required files missing")
            points[child] = VerifiedPoint(child, timestamp, "recursive-listing-count", count)
        if best is None or (timestamp, child) > (best[0], best[1]):
            best = (timestamp, child, passing)
    _newest_receipt_refuses_without_proof(best, "Houses daily")
    return points


def load_verified(spec: FamilySpec) -> dict[str, VerifiedPoint]:
    if spec.loader == "note-sx":
        return load_note_sx()
    if spec.loader == "app":
        for _app, glob, family in APP_RECEIPTS:
            if family == spec.family:
                return load_app(glob, family)
        raise Refusal("family specification unknown")
    if spec.loader == "morning-state":
        return load_morning()[0]
    if spec.loader == "morning-config":
        return load_morning()[1]
    if spec.loader == "houses-daily":
        return load_houses_daily()
    raise Refusal("family specification unknown")


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def _entry(point: VerifiedPoint | None, name: str, verified: dict[str, VerifiedPoint],
           newest: str | None, newest_ts: int | None, decision: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "timestamp": (datetime.fromtimestamp(point.timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                      if point is not None else None),
        "verified": name in verified,
        "newest_verified": name == newest,
        "decision": decision,
        "reason": reason,
    }


def plan_family(spec: FamilySpec, verified: dict[str, VerifiedPoint], remote: Iterable[str],
                *, now: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not verified:
        raise Refusal("verified point set empty for " + spec.family)
    newest = max(verified, key=lambda name: (verified[name].timestamp, name))
    newest_ts = verified[newest].timestamp
    cutoff = now - RETENTION_SECONDS
    remote_set = set(remote)
    if newest not in remote_set:
        raise Refusal("newest verified point missing from remote namespace")
    for name in sorted(remote_set):
        timestamp = parse_point_timestamp(name)
        if timestamp is None:
            entries.append(_entry(None, name, verified, newest, newest_ts,
                                  "keep", "name-not-a-strict-timestamp"))
        elif timestamp > now + CLOCK_SKEW_SECONDS:
            entries.append(_entry(VerifiedPoint(name, timestamp, "listing-count", None), name, verified,
                                  newest, newest_ts, "keep", "timestamp-in-the-future-or-in-progress"))
        elif name == newest:
            entries.append(_entry(verified[name], name, verified, newest, newest_ts,
                                  "keep", "newest-verified-point-always-preserved"))
        elif name not in verified:
            entries.append(_entry(None, name, verified, newest, newest_ts,
                                  "keep", "no-passing-receipt"))
        elif timestamp >= newest_ts:
            entries.append(_entry(verified[name], name, verified, newest, newest_ts,
                                  "keep", "not-strictly-older-than-newest-verified"))
        elif timestamp >= cutoff:
            entries.append(_entry(verified[name], name, verified, newest, newest_ts,
                                  "keep", "inside-seven-day-window"))
        else:
            entries.append(_entry(verified[name], name, verified, newest, newest_ts,
                                  "delete", "verified-superseded-and-older-than-seven-days"))
    return entries


def protected_identity(verified: dict[str, VerifiedPoint]) -> dict[str, Any]:
    newest = max(verified, key=lambda name: (verified[name].timestamp, name))
    point = verified[newest]
    return {"name": newest, "timestamp": point.timestamp,
            "shape": point.shape, "expected_count": point.expected_count}


def build_manifest(families: list[dict[str, Any]], *, now: int) -> dict[str, Any]:
    deletes = sum(1 for family in families for entry in family["points"]
                  if entry["decision"] == "delete")
    keeps = sum(1 for family in families for entry in family["points"]
                if entry["decision"] == "keep")
    return {
        "schema": "vps-recovery-retention-manifest/v1",
        "policy": {
            "retention_seconds": RETENTION_SECONDS,
            "retention_days": RETENTION_SECONDS // 86400,
            "always_keep_newest_verified": True,
            "delete_requires_passing_receipt": True,
            "delete_requires_strictly_older_than_protected": True,
            "delete_requires_strictly_outside_window": True,
            "boundary": "delete only when point age is strictly greater than the window",
        },
        "generated_at_epoch": now,
        "families": families,
        "summary": {"families": len(families), "delete": deletes, "keep": keeps},
    }


def manifest_digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def delete_sets(manifest: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for family in manifest["families"]:
        result[family["family"]] = sorted(
            entry["name"] for entry in family["points"] if entry["decision"] == "delete")
    return result


def protected_set(manifest: dict[str, Any]) -> dict[str, Any]:
    return {family["family"]: family.get("protected") for family in manifest["families"]}


def build_plan(*, now: int) -> dict[str, Any]:
    families = []
    for spec in SPECS:
        verified = load_verified(spec)
        remote = remote_children(spec.family, spec.is_dir)
        families.append({
            "family": spec.family,
            "is_dir": spec.is_dir,
            "verified_points": len(verified),
            "protected": protected_identity(verified),
            "points": plan_family(spec, verified, remote, now=now),
        })
    return build_manifest(families, now=now)


def apply_plan(manifest: dict[str, Any], *, now: int) -> None:
    planned = delete_sets(manifest)
    # Phase 1 (validation before mutation): freshly reload every family, require
    # the newest receipt proof, positively re-bind the protected point with its
    # exact protected set shape, and re-validate each candidate against the
    # fresh receipts. Any drift refuses before the first delete is issued.
    fresh: dict[str, dict[str, VerifiedPoint]] = {}
    newest_points: dict[str, VerifiedPoint] = {}
    for spec in SPECS:
        verified = load_verified(spec)
        protected = protected_identity(verified)
        expected = protected_set(manifest).get(spec.family)
        if expected is not None and (protected["name"] != expected.get("name")
                                     or protected["timestamp"] != expected.get("timestamp")
                                     or protected["shape"] != expected.get("shape")
                                     or protected["expected_count"] != expected.get("expected_count")):
            raise Refusal("protected-point drift for " + spec.family)
        point = verified[protected["name"]]
        assert_remote_point(spec.family, point)
        for name in planned.get(spec.family, []):
            candidate = verified.get(name)
            if candidate is None or manifest_entry(manifest, spec.family, name) is None:
                raise Refusal("planned point no longer verified")
            if not candidate.timestamp < point.timestamp:
                raise Refusal("planned point not strictly older than protected")
            if not (now - candidate.timestamp > RETENTION_SECONDS):
                raise Refusal("planned point inside the rolling window")
        fresh[spec.family] = verified
        newest_points[spec.family] = point
    # Phase 2: delete only the planned, freshly re-bound points. Network deletes
    # are irreversible once issued.
    for spec in SPECS:
        for name in planned.get(spec.family, []):
            command("purge" if spec.is_dir else "deletefile", spec.family + "/" + name)
    note_verified = fresh.get(NOTE_SX)
    if note_verified:
        newest_note = max(note_verified, key=lambda name: (note_verified[name].timestamp, name))
        local_cleanup(NOTE_LOCAL, note_verified[newest_note].timestamp)
    newest_houses = None
    for receipt_path in receipts(BASE, "houses-currentdb-*.json"):
        data = document(receipt_path)
        point_id = data.get("point_id")
        timestamp = parse_point_timestamp(point_id) if isinstance(point_id, str) else None
        if timestamp is not None:
            newest_houses = timestamp if newest_houses is None else max(newest_houses, timestamp)
    if newest_houses is not None:
        local_cleanup(HOUSES_LOCAL, newest_houses)
    # Re-check the same precise identity after cleanup.
    for spec in SPECS:
        if spec.family in fresh:
            assert_remote_point(spec.family, newest_points[spec.family])
    observe_cron()


def manifest_entry(manifest: dict[str, Any], family: str, name: str) -> dict[str, Any] | None:
    for item in manifest["families"]:
        if item["family"] != family:
            continue
        for entry in item["points"]:
            if entry["name"] == name and entry["decision"] == "delete":
                return entry
    return None


# --------------------------------------------------------------------------- #
# Local space policy (unchanged in spirit: no seven local snapshots retained)
# --------------------------------------------------------------------------- #
# The unprivileged identity can create entries under its own trees, so a
# recursive cleanup must be bounded and must fail closed rather than walk a
# hostile tree indefinitely.
CLEANUP_MAX_DEPTH = 64
CLEANUP_MAX_ENTRIES = 200_000


def _cleanup_allowed_owners() -> tuple[int, ...]:
    owners = [ROOT_UID]
    try:
        owners.append(pwd.getpwnam("diab").pw_uid)
    except KeyError:
        pass
    return tuple(owners)


def _trusted_anchor(path: Path) -> Path:
    """Deepest ancestor of ``path`` whose whole chain is root-owned and non-writable."""
    anchor = None
    for candidate in reversed(path.parents):
        try:
            st = candidate.lstat()
        except OSError:
            break
        if (stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode)
                and st.st_uid == ROOT_UID and not st.st_mode & 0o022):
            anchor = candidate
        else:
            break
    if anchor is None:
        raise Refusal("no trusted cleanup anchor")
    return anchor


def _open_chain(root: Path, *, anchor: Path, anchor_uid: int,
                allowed_owners: tuple[int, ...]):
    """Open ``root`` by walking every component from a trusted anchor.

    Each component is opened relative to the previous retained descriptor with
    ``O_NOFOLLOW``, so an intermediate symlink (or a final one) is refused
    instead of followed. A missing component returns ``None``; nothing is ever
    created. The opened directory is verified from its descriptor before any
    entry is touched.
    """
    try:
        relative = root.relative_to(anchor)
    except ValueError:
        raise Refusal("cleanup root outside trusted anchor") from None
    if not relative.parts:
        raise Refusal("cleanup root must be below the anchor")
    try:
        fd = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise Refusal("cleanup anchor unavailable") from None
    try:
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != anchor_uid
                or st.st_mode & 0o022):
            raise Refusal("untrusted cleanup anchor")
        for index, part in enumerate(relative.parts):
            last = index == len(relative.parts) - 1
            try:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=fd)
            except FileNotFoundError:
                os.close(fd)
                return None
            except OSError:
                raise Refusal("unsafe cleanup component") from None
            os.close(fd)
            fd = next_fd
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise Refusal("unsafe cleanup component")
            if last:
                if info.st_uid not in allowed_owners or info.st_mode & 0o022:
                    raise Refusal("untrusted cleanup root")
            elif info.st_mode & 0o022:
                raise Refusal("writable cleanup ancestor")
        return fd
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _remove_entry_at(dir_fd: int, name: str, *, depth: int = 0,
                     budget=None) -> None:
    """Recursive removal relative to a retained descriptor, bounded."""
    if budget is None:
        budget = [CLEANUP_MAX_ENTRIES]
    if depth > CLEANUP_MAX_DEPTH:
        raise Refusal("local cleanup depth refused")
    budget[0] -= 1
    if budget[0] < 0:
        raise Refusal("local cleanup count refused")
    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    if stat.S_ISDIR(info.st_mode):
        child_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=dir_fd)
        try:
            for entry in os.listdir(child_fd):
                _remove_entry_at(child_fd, entry, depth=depth + 1, budget=budget)
        finally:
            os.close(child_fd)
        os.rmdir(name, dir_fd=dir_fd)
    else:
        os.unlink(name, dir_fd=dir_fd)


def local_cleanup(root: Path, newest_verified_ts, *, anchor=None,
                  anchor_uid: int = ROOT_UID, allowed_owners=None) -> list[str]:
    """Delete superseded local point dirs through an all-component FD walk.

    The roots live under directories the agent identity can write, so the path
    itself is not trusted: every component is opened with ``O_NOFOLLOW`` from a
    root-owned anchor, the opened directory is verified from its descriptor
    before any change, and a missing root is a no-op rather than a
    ``parents=True`` creation. Filenames, skip rules (newer/in-progress data and
    non-timestamp entries are preserved) and the returned list are unchanged.
    """
    removed: list[str] = []
    if newest_verified_ts is None:
        return removed
    if allowed_owners is None:
        allowed_owners = _cleanup_allowed_owners()
    if anchor is None:
        anchor = _trusted_anchor(root)
    dir_fd = _open_chain(root, anchor=anchor, anchor_uid=anchor_uid,
                         allowed_owners=allowed_owners)
    if dir_fd is None:
        return removed
    try:
        for name in sorted(os.listdir(dir_fd)):
            child = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            if stat.S_ISLNK(child.st_mode):
                continue
            timestamp = parse_point_timestamp(name)
            if timestamp is None or timestamp > newest_verified_ts:
                continue  # newer/in-progress/ambiguous local data is preserved
            _remove_entry_at(dir_fd, name)
            removed.append(name)
    except Refusal:
        raise
    except OSError as exc:
        raise Refusal("local cleanup refused") from exc
    finally:
        os.close(dir_fd)
    return removed


def morning_timer_present() -> bool:
    timer = "morning-brief-backup.timer"
    return all(subprocess.run(["/usr/bin/systemctl", verb, "--quiet", timer],
                              capture_output=True, timeout=5).returncode == 0
               for verb in ("is-enabled", "is-active"))


def observe_cron() -> None:
    # Preserve the existing metadata schema while observing the replacement
    # root-managed timer. The app-owned crontab is no longer the producer.
    present = morning_timer_present()
    parent = STATUS_DIR
    try:
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)  # metadata only: timestamp plus schedule-presence boolean
    except FileExistsError:
        pass
    st = parent.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        raise Refusal("untrusted cron status root")
    temp = parent / (".cron-observation-" + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    os.fchmod(fd, 0o644)
    with os.fdopen(fd, "w") as handle:
        json.dump({"observed_at": time.time(), "morning_backup_present": present}, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, parent / "cron-observation.json")


def write_manifest(manifest: dict[str, Any], *, directory: Path = MANIFEST_DIR) -> tuple[Path, str]:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    digest = manifest_digest(manifest)
    stamp = datetime.fromtimestamp(manifest["generated_at_epoch"], timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"retention-manifest-{stamp}-{digest[:12]}.json"
    temp = directory / ("." + path.name + "." + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(manifest, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    return path, digest


def _diab_uid() -> int:
    return pwd.getpwnam("diab").pw_uid


def _open_owned_dir(path: Path, *, uid: int, mode, code: str) -> tuple[int, tuple[int, int]]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise Refusal(code)
    info = os.fstat(fd)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
            or (mode is not None and stat.S_IMODE(info.st_mode) != mode)):
        os.close(fd)
        raise Refusal(code)
    return fd, (info.st_dev, info.st_ino)


def _drop_lock_dir(fd, identity, owner_identity=None, owned: bool = False) -> None:
    """Remove only what this process created; never a foreign entry or directory."""
    if owned and owner_identity is not None:
        try:
            st = os.stat("owner", dir_fd=fd, follow_symlinks=False)
            if (st.st_dev, st.st_ino) == owner_identity:
                os.unlink("owner", dir_fd=fd)
        except OSError:
            pass
    os.close(fd)
    if not owned:
        return
    try:
        st = os.lstat(LOCK)
    except OSError:
        return
    if (stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode)
            and (st.st_dev, st.st_ino) == identity):
        try:
            os.rmdir(LOCK)
        except OSError:
            pass


def acquire_lock() -> tuple[int, tuple[int, int], tuple[int, int] | None, bool]:
    """Create and own the shared lock, proving we created what we clean up.

    The parent is diab-owned, so the name can be swapped between `mkdir` and the
    later open. A freshly created lock must be empty: if the directory we open
    already holds an entry it is not ours, so we refuse and leave it untouched
    rather than deleting a foreign root-owned owner file. Only the owner entry
    this process created (tracked by dev/ino) is ever removed.
    """
    parent_fd = -1
    fd = -1
    identity = None
    owner_identity = None
    owned = False
    try:
        try:
            parent_fd = os.open(LOCK.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            raise Refusal("lock parent unavailable") from None
        try:
            os.mkdir(LOCK.name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            raise Refusal("busy-or-stale") from None
        except OSError:
            raise Refusal("lock-unavailable") from None
        try:
            created = os.stat(LOCK.name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError:
            raise Refusal("new-lock-directory-unsafe") from None
        if (not stat.S_ISDIR(created.st_mode) or stat.S_ISLNK(created.st_mode)
                or created.st_uid != ROOT_UID or stat.S_IMODE(created.st_mode) != 0o700):
            raise Refusal("new-lock-directory-unsafe")
        try:
            fd = os.open(LOCK.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError:
            raise Refusal("new-lock-directory-unsafe") from None
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (created.st_dev, created.st_ino):
            raise Refusal("new-lock-directory-swapped")
        identity = (info.st_dev, info.st_ino)
        if os.listdir(fd):
            raise Refusal("new-lock-directory-not-empty")
        owned = True
        owner_fd = os.open("owner", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                           0o600, dir_fd=fd)
        with os.fdopen(owner_fd, "w") as handle:
            owner_st = os.fstat(handle.fileno())
            if (not stat.S_ISREG(owner_st.st_mode) or owner_st.st_uid != ROOT_UID
                    or stat.S_IMODE(owner_st.st_mode) != 0o600):
                raise Refusal("owner-file-unsafe")
            owner_identity = (owner_st.st_dev, owner_st.st_ino)
            handle.write(OWNER + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Refusal:
        if fd >= 0:
            _drop_lock_dir(fd, identity, owner_identity, owned)
            fd = -1
        raise
    except OSError:
        if fd >= 0:
            _drop_lock_dir(fd, identity, owner_identity, owned)
            fd = -1
        raise Refusal("owner-write-failed") from None
    finally:
        if parent_fd >= 0:
            os.close(parent_fd)
    return fd, identity, owner_identity, owned


def release_lock(owner) -> None:
    fd, identity, owner_identity, _owned = owner
    try:
        if sorted(os.listdir(fd)) != ["owner"]:
            raise Refusal("lock ownership changed; retained")
        owner_fd = os.open("owner", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(owner_fd, "r") as handle:
            owner_st = os.fstat(handle.fileno())
            if (not stat.S_ISREG(owner_st.st_mode) or owner_st.st_uid != ROOT_UID
                    or stat.S_IMODE(owner_st.st_mode) != 0o600
                    or handle.read(256).strip() != OWNER):
                raise Refusal("lock ownership changed; retained")
            if owner_identity is not None and (owner_st.st_dev, owner_st.st_ino) != owner_identity:
                raise Refusal("lock ownership changed; retained")
        os.unlink("owner", dir_fd=fd)
    except Refusal:
        raise
    except OSError as exc:
        raise Refusal("lock release failed; retained") from exc
    os.close(fd)
    try:
        st = os.lstat(LOCK)
    except OSError:
        return
    if (stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode)
            and (st.st_dev, st.st_ino) == identity):
        try:
            os.rmdir(LOCK)
        except OSError:
            pass


def write_completion_status(digest: str) -> None:
    """Publish the completion status bound to the exact descriptor we wrote."""
    payload = {"completed": time.time(), "policy": "seven-day-rolling",
               "manifest_sha256": digest, "latest_verified_points_preserved": True}
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    content_digest = hashlib.sha256(raw).hexdigest()
    dir_fd = -1
    fd = -1
    temporary_name = ".lean-retention-" + uuid.uuid4().hex
    final_name = "lean-retention-complete.json"
    try:
        dir_fd, _ = _open_owned_dir(BASE, uid=_diab_uid(), mode=None,
                                    code="receipt-directory-unsafe")
        fd = os.open(temporary_name,
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=dir_fd)
        _write_all(fd, raw)
        os.fsync(fd)
        written = os.fstat(fd)
        recorded = (written.st_dev, written.st_ino, written.st_size)
        os.close(fd)
        fd = -1
        os.replace(temporary_name, final_name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        final_st = os.stat(final_name, dir_fd=dir_fd, follow_symlinks=False)
        if ((final_st.st_dev, final_st.st_ino, final_st.st_size) != recorded
                or final_st.st_nlink != 1 or final_st.st_uid != ROOT_UID
                or stat.S_IMODE(final_st.st_mode) != 0o600):
            raise Refusal("receipt status identity refused")
        check_fd = os.open(final_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        try:
            if hashlib.sha256(read_fd_bytes(check_fd, recorded[2], "receipt status")).hexdigest() != content_digest:
                raise Refusal("receipt status content refused")
        finally:
            os.close(check_fd)
        os.fsync(dir_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        if dir_fd >= 0:
            try:
                os.unlink(temporary_name, dir_fd=dir_fd)
            except OSError:
                pass
            os.close(dir_fd)


def load_approved_deletes(path: Path) -> set[tuple[str, str]]:
    value = json.loads(read_private_bytes(path, 4 * 1024 * 1024, "approved manifest"))
    if not isinstance(value, dict) or value.get("schema") != "vps-recovery-retention-manifest/v1":
        raise Refusal("approved manifest invalid")
    approved = set()
    for family in value.get("families", []):
        for entry in family.get("points", []):
            if entry.get("decision") == "delete":
                approved.add((family["family"], entry["name"]))
    return approved


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="require the freshly recomputed delete set to equal this reviewed manifest")
    parser.add_argument("--manifest-dir", type=Path, default=MANIFEST_DIR)
    args = parser.parse_args()

    if os.geteuid() != 0 or any(key.startswith("RCLONE_") for key in os.environ):
        raise Refusal("trusted root invocation required")
    assert_trusted_inputs()
    if command("version").splitlines()[0].decode("ascii", "replace") != RCLONE_VERSION:
        raise Refusal("client version mismatch")

    owner = acquire_lock()
    try:
        preview = build_plan(now=int(time.time()))
        path, digest = write_manifest(preview, directory=args.manifest_dir)
        print(json.dumps({"manifest": str(path), "sha256": digest,
                          "summary": preview["summary"], "apply": bool(args.apply)}))
        if not args.apply:
            return 0
        # Recompute and rebind immediately before the first mutation.
        fresh_now = int(time.time())
        fresh = build_plan(now=fresh_now)
        if protected_set(fresh) != protected_set(preview):
            raise Refusal("protected-point drift between preview and apply")
        if delete_sets(fresh) != delete_sets(preview):
            raise Refusal("delete-set drift between preview and apply")
        if args.manifest is not None:
            if load_approved_deletes(args.manifest) != {
                    (family, name) for family, names in delete_sets(fresh).items() for name in names}:
                raise Refusal("approved manifest drift; refusing to delete")
        assert_trusted_inputs()  # re-validate before mutation
        apply_plan(fresh, now=fresh_now)
        write_completion_status(digest)
        print("retention=complete rolling_days=7 latest_verified_points_preserved")
        return 0
    finally:
        release_lock(owner)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Refusal as exc:
        print("retention=refused class=Refusal detail=" + str(exc))
        raise SystemExit(1)
    except Exception as exc:  # fail closed, never continue past an unexpected error
        print("retention=refused class=" + type(exc).__name__)
        raise SystemExit(1)
