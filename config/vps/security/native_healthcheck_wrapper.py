#!/usr/bin/env python3
"""Run the staged native scan/watchdog with optional bounded Healthchecks pings."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from core import MonitorError, read_private_json
from native_scanner import MAX_CONFIG_BYTES, ping, validate_config


COMPONENT_TIMEOUTS = {"native": 1510, "native-watchdog": 35}


def _exit_status(returncode: int) -> int:
    if returncode >= 0:
        return min(returncode, 255)
    number = -returncode
    try:
        signal_name = signal.Signals(number).name
    except ValueError:
        signal_name = f"signal-{number}"
    print(f"native monitor terminated by {signal_name}", file=sys.stderr)
    return min(128 + number, 255)


def run_wrapped(component: str, command: list[str], *, config_path: Path,
                runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                ping_fn: Callable[..., bool] = ping) -> int:
    timeout = COMPONENT_TIMEOUTS.get(component)
    if timeout is None:
        raise MonitorError("native-wrapper-component-invalid")
    value = validate_config(read_private_json(config_path, max_bytes=MAX_CONFIG_BYTES))
    hc = value["healthchecks"]
    base = hc.get("native_ping_url" if component == "native" else "watchdog_ping_url") if hc.get("enabled") else None
    start_ok = ping_fn(base, "start") if base else True
    try:
        result = runner(command, check=False, timeout=timeout)
        status = _exit_status(result.returncode)
    except subprocess.TimeoutExpired:
        status = 124
    except OSError:
        status = 127
    finish_ok = ping_fn(base, "0" if status == 0 else "1") if base else True
    if base and not (start_ok and finish_ok):
        print("native Healthchecks ping failed; local monitor status retained", file=sys.stderr)
        if status == 0:
            return 2
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=tuple(COMPONENT_TIMEOUTS), required=True)
    parser.add_argument("--config", type=Path,
                        default=Path.home() / ".config/vps-security-scan/native.json")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not Path(command[0]).is_absolute():
        parser.error("provide an absolute original command after --")
    try:
        return run_wrapped(args.component, command, config_path=args.config)
    except (MonitorError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"native Healthchecks wrapper could not complete: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
