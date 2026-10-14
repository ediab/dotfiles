#!/usr/bin/env python3
"""Hourly email watchdog for the daily scanner's stale or failed heartbeat."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Callable

from core import MonitorError, atomic_json, read_private_json
from scanner import _email_sender


def inspect_scan_job(state_dir: Path, *, now: int, max_age: int = 32 * 3600,
                     run=subprocess.run) -> list[str]:
    issues = []
    path = state_dir / "run.json"
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 2048):
            return ["scanner:untrusted-heartbeat"]
        data = read_private_json(path, max_bytes=2048)
        if not isinstance(data, dict):
            return ["scanner:invalid-heartbeat"]
        completed = data.get("completed_at")
        if (isinstance(completed, bool) or not isinstance(completed, (int, float))
                or not math.isfinite(completed)):
            return ["scanner:invalid-heartbeat"]
        if now - completed > max_age or completed > now + 300:
            issues.append("scanner:stale-heartbeat")
        status = data.get("status")
        if not isinstance(status, str) or status not in {"clean", "findings", "error"}:
            issues.append("scanner:invalid-status")
        elif status == "error":
            issues.append("scanner:failed-run")
    except FileNotFoundError:
        issues.append("scanner:missing-heartbeat")
    except (MonitorError, OSError):
        issues.append("scanner:invalid-heartbeat")
    timer = run(["/usr/bin/systemctl", "--user", "is-active", "vps-image-scan.timer"],
                capture_output=True, timeout=5, check=False)
    if timer.returncode != 0:
        issues.append("scanner:timer-inactive")
    return issues


def summarize(state: dict, issues: list[str], now: int) -> tuple[str | None, str | None]:
    if not isinstance(state, dict):
        raise MonitorError("watchdog notification state has invalid shape")
    current = sorted(issues)
    previous = state.get("issues", [])
    last_sent = state.get("sent_at", 0)
    if (not isinstance(previous, list) or any(not isinstance(item, str) for item in previous)
            or isinstance(last_sent, bool) or not isinstance(last_sent, (int, float))
            or not math.isfinite(last_sent)):
        raise MonitorError("watchdog notification state has invalid shape")
    if current == previous and not (current and now - last_sent >= 86400):
        return None, None
    if current:
        label = "failed"
        body = "VPS daily image scan monitoring: " + label + ".\n" + ", ".join(current)
        event = "failed:" + ",".join(current)
    elif previous:
        event = "recovered"
        body = "VPS daily image scan monitoring recovered.\nThe scanner heartbeat and timer are healthy."
    else:
        return None, None
    return event, body


def run_watchdog(config: dict, *, now: int | None = None,
                 inspect: Callable[..., list[str]] = inspect_scan_job,
                 send: Callable[[str], bool] | None = None) -> int:
    now = int(time.time()) if now is None else now
    issues = inspect(config["state_dir"], now=now, max_age=config["max_heartbeat_age_seconds"])
    state_path = config["state_dir"] / "watchdog-notifications.json"
    try:
        state_path.lstat()
    except FileNotFoundError:
        state = {}
    else:
        state = read_private_json(state_path, max_bytes=4096)
    if not isinstance(state, dict):
        raise MonitorError("watchdog notification state has invalid shape")
    event, body = summarize(state, issues, now)
    if event is None:
        return 1 if issues else 0
    if send is None:
        send = _email_sender(config)
    if not send(body):
        raise MonitorError("watchdog email failed; notification state not advanced")
    atomic_json(state_path, {"issues": sorted(issues), "sent_at": now, "event": event})
    return 1 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/vps-security-scan/config.json")
    args = parser.parse_args()
    try:
        config = read_private_json(args.config)
        if not isinstance(config, dict) or not isinstance(config.get("state_dir"), str):
            raise MonitorError("watchdog configuration is invalid")
        age = config.get("max_heartbeat_age_seconds", 32 * 3600)
        if isinstance(age, bool) or not isinstance(age, int) or not 26 * 3600 <= age <= 48 * 3600:
            raise MonitorError("heartbeat age bound is invalid")
        scanner_config = {"state_dir": Path(config["state_dir"]),
                          "email_transport_root": config.get("email_transport_root", str(Path.home() / "Dev/xbot"))}
        scanner_config["max_heartbeat_age_seconds"] = age
        return run_watchdog(scanner_config, now=int(time.time()))
    except (MonitorError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"watchdog could not complete: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
