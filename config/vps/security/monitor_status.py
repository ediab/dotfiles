#!/usr/bin/env python3
"""Socket-activated, fixed read-only status broker. Never executes app code."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys
import time

from core import IMAGE_STATE, NATIVE_STATE, MonitorError, root_ancestors
from system_runtime import HOUSES_DIRECTORY

APPLICATIONS = frozenset({"tfl", "xbot", "morning-brief", "el-machine", "houses"})
FIELDS = ("ActiveState", "SubState", "Result", "ExecMainStatus", "ExecMainStartTimestamp",
          "ExecMainExitTimestamp", "LastTriggerUSec", "NextElapseUSecRealtime", "User", "Group")


def _run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
    if result.returncode or len(result.stdout) > 8192:
        raise MonitorError("status-query-unavailable")
    return result.stdout.strip()


def houses_binding():
    uid = pwd.getpwnam("diab").pw_uid
    if uid == 0:
        raise MonitorError("status-user-identity-refused")
    result = subprocess.run(["/usr/bin/systemctl", "--user", "show", "--property=WorkingDirectory",
                             "--value", "houses-health.service"],
                            user="diab", group="diab", extra_groups=[], cwd="/", capture_output=True,
                            text=True, timeout=5, check=False,
                            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                                 "XDG_RUNTIME_DIR": f"/run/user/{uid}",
                                 "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus"})
    valid = result.returncode == 0 and result.stdout.strip() == HOUSES_DIRECTORY
    return {"verified": valid, "working_directory": HOUSES_DIRECTORY if valid else None}


def _record(path: Path, owner: int, maximum=8*1024*1024, private=True):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_nlink != 1
                or info.st_mode & (0o077 if private else 0o022) or info.st_size > maximum):
            raise MonitorError("status-record-untrusted")
        data = stream.read(maximum+1)
        if len(data) > maximum:
            raise MonitorError("status-record-too-large")
        value = json.loads(data)
    if not isinstance(value, dict):
        raise MonitorError("status-record-invalid")
    return value


def _iso(value):
    if not isinstance(value, str) or len(value) > 64:
        raise MonitorError("status-timestamp-invalid")
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise MonitorError("status-timestamp-invalid")
    return timestamp.astimezone(timezone.utc).isoformat()


def scan_metadata(state: Path, account: str, native: bool):
    owner = pwd.getpwnam(account).pw_uid
    if owner == 0:
        raise MonitorError("status-record-owner-refused")
    root_ancestors(state)
    for directory in (state, state / "reports"):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_mode & 0o077:
            raise MonitorError("status-record-directory-untrusted")
    heartbeat = _record(state / ("native-run.json" if native else "run.json"), owner, 4096)
    scan_id = heartbeat.get("scan_id")
    completed = heartbeat.get("completed_at")
    if (not isinstance(scan_id, str) or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", scan_id)
            or type(completed) not in (int, float) or not math.isfinite(completed)
            or heartbeat.get("status") not in ("clean", "findings", "error")):
        raise MonitorError("status-heartbeat-invalid")
    report_name = ("native-scan-" if native else "scan-") + scan_id + ".json"
    reported = heartbeat.get("report")
    if reported not in (report_name, str(state / "reports" / report_name)):
        raise MonitorError("status-report-path-refused")
    report = _record(state / "reports" / report_name, owner, 32*1024*1024)
    completed_iso = _iso(report.get("completed_at"))
    if (report.get("scan_id") != scan_id or report.get("status") != heartbeat["status"]
            or abs(datetime.fromisoformat(completed_iso).timestamp()-completed) > 5):
        raise MonitorError("status-report-heartbeat-mismatch")
    findings, errors = report.get("findings"), report.get("errors")
    if not isinstance(findings, list) or not isinstance(errors, list):
        raise MonitorError("status-report-shape-invalid")
    result = {"scan_id": scan_id, "completed_at": completed, "completed_at_utc": completed_iso,
              "report": report_name, "status": heartbeat["status"],
              "findings_count": len(findings), "errors_count": len(errors)}
    if native:
        targets = report.get("targets")
        if not isinstance(targets, list) or len(targets) > 5:
            raise MonitorError("status-native-targets-invalid")
        rows = []
        for target in targets:
            if not isinstance(target, dict) or target.get("application") not in APPLICATIONS:
                raise MonitorError("status-native-targets-invalid")
            rows.append({"application": target["application"],
                         "coverage_complete": target.get("coverage_complete") is True})
        if len({r["application"] for r in rows}) != len(rows):
            raise MonitorError("status-native-targets-invalid")
        complete = (report.get("coverage_status") == "complete"
                    and {row["application"] for row in rows} == APPLICATIONS
                    and all(row["coverage_complete"] for row in rows))
        result.update(targets=rows, coverage_status=("complete" if complete else "incomplete"),
                      trivy_database_updated_at=_iso(report.get("trivy_database_updated_at")))
    return result


def unit_metadata(unit):
    text = _run(["/usr/bin/systemctl", "show", unit, *["--property="+key for key in FIELDS]])
    value = {}
    for line in text.splitlines():
        key, sep, data = line.partition("=")
        if not sep or key not in FIELDS or len(data) > 160:
            raise MonitorError("status-unit-shape-invalid")
        value[key] = data
    return value


def status():
    value = {"units": {unit: unit_metadata(unit) for unit in (
        "vps-image-scan.service", "vps-image-scan.timer", "vps-image-scan-watchdog.service",
        "vps-image-scan-watchdog.timer", "vps-native-scan.service", "vps-native-scan.timer",
        "vps-native-scan-watchdog.service", "vps-native-scan-watchdog.timer")}}
    for lane, state, account, native in (("image", IMAGE_STATE, "vps-image-scan", False),
                                         ("native", NATIVE_STATE, "vps-native-scan", True)):
        try:
            value[lane] = scan_metadata(state, account, native)
        except (OSError, ValueError, KeyError, MonitorError):
            value[lane] = {"unavailable": True}
    return value


def reply(operation):
    if operation not in ("houses-binding", "status"):
        raise MonitorError("status-operation-refused")
    payload = houses_binding() if operation == "houses-binding" else status()
    return {"schema_version": 1, "operation": operation, "checked_at": int(time.time()), **payload}


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        return 2
    with socket.socket(fileno=0) as connection:
        connection.settimeout(5)
        request = bytearray()
        while b"\n" not in request:
            data = connection.recv(33-len(request))
            if not data or len(request)+len(data) > 32:
                raise MonitorError("status-operation-refused")
            request.extend(data)
        if not request.endswith(b"\n") or request.count(b"\n") != 1:
            raise MonitorError("status-operation-refused")
        output = reply(request[:-1].decode("ascii"))
        encoded = json.dumps(output, separators=(",", ":")).encode()+b"\n"
        if len(encoded) > 65536:
            raise MonitorError("status-response-too-large")
        connection.sendall(encoded)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, MonitorError, subprocess.TimeoutExpired):
        # Never echo requests, private source records or command output.
        raise SystemExit(2)
