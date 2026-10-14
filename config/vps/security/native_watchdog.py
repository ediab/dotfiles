#!/usr/bin/env python3
"""Hourly email watchdog for native scanner freshness, status and timer state."""
from __future__ import annotations

import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Callable

from core import MonitorError, atomic_json, deliver_transition, read_private_json
from native_scanner import _email_sender, validate_config


MAX_HEARTBEAT_AGE = 8 * 24 * 3600


def inspect_native_job(state_dir: Path, *, now: int, max_age: int = MAX_HEARTBEAT_AGE,
                       run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> list[str]:
    issues: list[str] = []
    path = state_dir / "native-run.json"
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 4096):
            return ["native:untrusted-heartbeat"]
        value = read_private_json(path, max_bytes=4096)
        if not isinstance(value, dict):
            return ["native:invalid-heartbeat"]
        completed = value.get("completed_at")
        if (isinstance(completed, bool) or not isinstance(completed, (int, float))
                or not math.isfinite(completed)):
            return ["native:invalid-heartbeat"]
        if now - completed > max_age or completed > now + 300:
            issues.append("native:stale-heartbeat")
        if value.get("status") not in {"clean", "findings", "error"}:
            issues.append("native:invalid-status")
        elif value["status"] == "error":
            issues.append("native:failed-run")
    except FileNotFoundError:
        issues.append("native:missing-heartbeat")
    except (OSError, MonitorError):
        issues.append("native:invalid-heartbeat")
    timer = run(["/usr/bin/systemctl", "--user", "is-active", "vps-native-scan.timer"],
                capture_output=True, timeout=5, check=False)
    if timer.returncode != 0:
        issues.append("native:timer-inactive")
    return issues


def _state(path: Path) -> dict:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"issues": [], "sent_at": 0}
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 4096):
        raise MonitorError("native-watchdog-state-untrusted")
    value = read_private_json(path, max_bytes=4096)
    if not isinstance(value, dict):
        raise MonitorError("native-watchdog-state-invalid")
    issues, sent_at = value.get("issues", []), value.get("sent_at", 0)
    if (not isinstance(issues, list) or any(not isinstance(item, str) for item in issues)
            or isinstance(sent_at, bool) or not isinstance(sent_at, (int, float))
            or not math.isfinite(sent_at)):
        raise MonitorError("native-watchdog-state-invalid")
    return value


def run_watchdog(config: dict, *, now: int | None = None,
                 inspect: Callable[..., list[str]] = inspect_native_job,
                 send: Callable[[str], bool] | None = None,
                 run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> int:
    now = int(time.time()) if now is None else now
    issues = sorted(inspect(config["state_dir"], now=now,
                            max_age=config.get("max_heartbeat_age_seconds", MAX_HEARTBEAT_AGE), run=run))
    state_path = config["state_dir"] / "native-watchdog-notifications.json"
    state = _state(state_path)
    previous = sorted(state.get("issues", []))
    last_sent = state.get("sent_at", 0)
    event = None
    body = None
    if issues and (issues != previous or now - last_sent >= 24 * 3600):
        event = "failed:" + ",".join(issues)
        body = "VPS native dependency scan monitoring failed.\n" + ", ".join(issues)
    elif not issues and previous:
        event = "recovered"
        body = "VPS native dependency scan monitoring recovered.\nThe heartbeat and timer are healthy."
    if event is not None and body is not None:
        fingerprint = hashlib.sha256(event.encode("utf-8")).hexdigest()
        sender = send or _email_sender(config)
        deliver_transition(state_path, fingerprint, sender, body, event=event, now=now,
                           extra={"issues": issues}, state_max_bytes=4096)
    elif not issues and not previous:
        atomic_json(state_path, {"issues": [], "sent_at": 0})
    return 1 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path.home() / ".config/vps-security-scan/native.json")
    args = parser.parse_args()
    try:
        raw = read_private_json(args.config, max_bytes=32 * 1024)
        config = validate_config(raw)
        age = raw.get("max_heartbeat_age_seconds", MAX_HEARTBEAT_AGE)
        if type(age) is not int or not 7 * 24 * 3600 <= age <= MAX_HEARTBEAT_AGE:
            raise MonitorError("native-watchdog-age-invalid")
        return run_watchdog({"state_dir": config["state_dir"],
                             "email_transport_root": str(config["email_transport_root"]),
                             "max_heartbeat_age_seconds": age}, now=int(time.time()))
    except (MonitorError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"native watchdog could not complete: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
