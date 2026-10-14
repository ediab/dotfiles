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
MORNING = Path("/home/diab/apps/morning-brief/data/state-backup-receipts")
LOCK = Path("/home/diab/ops/r2-rollout-live.lock")
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
    if point.shape != "listing-count":
        raise Refusal("protected remote shape unknown")
    rows = list_json(target, "--files-only")
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
def document(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
    except OSError as exc:
        raise Refusal("receipt unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
            or info.st_size > MAX_RECEIPT_BYTES):
        raise Refusal("unsafe receipt")
    value = json.loads(path.read_bytes())
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
        if data.get("capture_id") != child:
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
def local_cleanup(root: Path, newest_verified_ts: int | None) -> list[str]:
    removed: list[str] = []
    if newest_verified_ts is None:
        return removed
    if not root.exists():
        root.mkdir(parents=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise Refusal("unsafe local recovery root")
    for child in sorted(root.iterdir()):
        if child.is_symlink():
            continue
        timestamp = parse_point_timestamp(child.name)
        if timestamp is None or timestamp > newest_verified_ts:
            continue  # newer/in-progress/ambiguous local data is preserved
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed.append(child.name)
    return removed


# --------------------------------------------------------------------------- #
# Cron observation (preserved from the frozen baseline)
# --------------------------------------------------------------------------- #
def observe_cron() -> None:
    cfg = json.loads(CRON_CONFIG.read_bytes())
    row = next(r for r in cfg if r.get("name") == "morning-brief")
    marker = row.get("entry_marker")
    if not isinstance(marker, str) or not 5 <= len(marker) <= 200 or "\n" in marker:
        raise Refusal("invalid cron marker")
    result = subprocess.run(["/usr/bin/crontab", "-u", "diab", "-l"],
                            capture_output=True, text=True, timeout=5)
    if result.returncode or len(result.stdout) > 65536:
        raise Refusal("cron observation refused")
    present = any(marker in line and not line.lstrip().startswith("#")
                  for line in result.stdout.splitlines())
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


# --------------------------------------------------------------------------- #
# Lock
# --------------------------------------------------------------------------- #
def acquire_lock() -> Path:
    LOCK.mkdir(mode=0o700)  # an existing or ambiguous lock always refuses
    owner = LOCK / "owner"
    fd = os.open(owner, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(OWNER + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return owner


def release_lock(owner: Path) -> None:
    st = owner.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or owner.read_text().strip() != OWNER
            or sorted(p.name for p in LOCK.iterdir()) != ["owner"]):
        raise Refusal("lock ownership changed; retained")
    owner.unlink()
    LOCK.rmdir()


# --------------------------------------------------------------------------- #
# Manifest publication
# --------------------------------------------------------------------------- #
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


def load_approved_deletes(path: Path) -> set[tuple[str, str]]:
    value = json.loads(path.read_bytes())
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
        status = BASE / "lean-retention-complete.json"
        temporary = BASE / (".lean-retention-" + uuid.uuid4().hex)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({"completed": time.time(), "policy": "seven-day-rolling",
                       "manifest_sha256": digest,
                       "latest_verified_points_preserved": True}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, status)
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
