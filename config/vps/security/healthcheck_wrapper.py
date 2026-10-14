#!/usr/bin/env python3
"""Add optional bounded Healthchecks pings around unchanged local monitors."""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from core import MonitorError, read_private_json


def validate_ping_url(value: object) -> str:
    if (not isinstance(value, str) or len(value) > 256 or "\n" in value or "@" in value):
        raise MonitorError("Healthchecks URL missing or invalid")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname not in {"hc-ping.com", "healthchecks.io"}
            or not parsed.path.strip("/") or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise MonitorError("Healthchecks URL must be a private HTTPS ping URL")
    return value.rstrip("/")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def ping(base_url: str, status: str, *, timeout: float = 5.0, opener=None) -> bool:
    if status not in {"start", "0", "1"}:
        raise ValueError("unsupported ping status")
    url = f"{base_url}/{status}"
    request = urllib.request.Request(url, data=b"", method="POST")
    try:
        if opener is None:
            opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler()).open
        with opener(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                return False
            response.read(513)  # Bound and discard response body; never relay it.
        return True
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def component_timeout(component: str, config: dict | None = None) -> int:
    fixed = {"app": 90, "disk": 160, "watchdog": 20}
    if component in fixed:
        return fixed[component]
    if component != "scan":
        raise MonitorError("unknown monitor component")
    value = config.get("overall_timeout_seconds", 6600) if isinstance(config, dict) else 6600
    if isinstance(value, bool) or not isinstance(value, int) or not 300 <= value <= 6900:
        raise MonitorError("scan timeout must be 300..6900 seconds")
    # Leave room for wrapper startup and both five-second Healthchecks requests
    # within the scanner service's 7200-second TimeoutStartSec.
    return value + 10


def _shell_exit_status(returncode: int) -> int:
    if returncode >= 0:
        return min(returncode, 255)
    number = -returncode
    try:
        name = signal.Signals(number).name
    except ValueError:
        name = f"signal-{number}"
    print(f"wrapped monitor terminated by {name}", file=sys.stderr)
    return min(128 + number, 255)


def run_wrapped(component: str, command: list[str], *, config_path: Path,
                 runner=subprocess.run, ping_fn=ping) -> int:
    """Run the original inspector unchanged, then report status without log bodies."""
    config_error = None
    base = None
    value = {}
    enabled = True
    try:
        value = read_private_json(config_path)
        if not isinstance(value, dict) or not isinstance(value.get("healthchecks"), dict):
            raise MonitorError("Healthchecks configuration shape is invalid")
        healthchecks = value["healthchecks"]
        enabled = healthchecks.get("enabled") is True
        if enabled:
            pings = healthchecks.get("monitor_ping_urls")
            if not isinstance(pings, dict):
                raise MonitorError("enabled Healthchecks URLs are missing")
            base = validate_ping_url(pings.get(component))
    except (MonitorError, OSError) as exc:
        config_error = exc
    try:
        run_timeout = component_timeout(component, value)
    except MonitorError as exc:
        config_error = config_error or exc
        run_timeout = 6910 if component == "scan" else 20
    start_ok = True
    if enabled and config_error is None and base:
        start_ok = ping_fn(base, "start")
    try:
        completed = runner(command, check=False, timeout=run_timeout)
        original_status = completed.returncode
    except subprocess.TimeoutExpired:
        original_status = 124
    except OSError:
        original_status = 127
    end_ok = True
    if enabled and config_error is None and base:
        end_ok = ping_fn(base, "0" if original_status == 0 else "1")
    if config_error is not None:
        print(f"Healthchecks configuration error: {type(config_error).__name__}", file=sys.stderr)
    elif enabled and (not start_ok or not end_ok):
        print("Healthchecks ping failed; local monitor result retained", file=sys.stderr)
    # The existing local monitor's result is authoritative for its checks. If it
    # passed, a required but unusable off-host configuration fails the wrapper.
    if original_status != 0:
        return _shell_exit_status(original_status)
    return 2 if config_error is not None or (enabled and (not start_ok or not end_ok)) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/vps-security-scan/config.json")
    parser.add_argument("--component", choices=("app", "disk", "scan", "watchdog"), required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not Path(command[0]).is_absolute():
        parser.error("provide an absolute original command after --")
    return run_wrapped(args.component, command, config_path=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
