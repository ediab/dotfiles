"""Fixed system-profile boundaries; no arbitrary privileged operation or path."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import time

from core import MonitorError, root_ancestors

STATUS_SOCKET = Path("/run/vps-security-scan/status.sock")
HOUSES_DIRECTORY = "/home/diab/apps/houses/pipeline"
HOUSES_QUERY = ["/usr/bin/systemctl", "--user", "show", "--property=WorkingDirectory",
                "--value", "houses-health.service"]


def system_profile(config: dict) -> bool:
    profile = config.get("profile", "user")
    if profile not in ("user", "system"):
        raise MonitorError("monitor-profile-invalid")
    return profile == "system"


def query_status(operation: str) -> dict:
    if operation not in ("houses-binding", "status"):
        raise MonitorError("monitor-status-operation-refused")
    try:
        root_ancestors(STATUS_SOCKET)
        info = STATUS_SOCKET.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o007:
            raise MonitorError("monitor-status-socket-untrusted")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            connection.connect(str(STATUS_SOCKET))
            _pid, uid, _gid = struct.unpack("3i", connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            if uid != 0:
                raise MonitorError("monitor-status-peer-untrusted")
            connection.sendall(operation.encode("ascii") + b"\n")
            data = bytearray()
            while b"\n" not in data:
                chunk = connection.recv(min(4096, 65537 - len(data)))
                if not chunk or len(data) + len(chunk) > 65536:
                    raise MonitorError("monitor-status-response-invalid")
                data.extend(chunk)
            value = json.loads(data)
        if (not isinstance(value, dict) or value.get("schema_version") != 1
                or value.get("operation") != operation):
            raise MonitorError("monitor-status-schema-invalid")
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        raise MonitorError("monitor-status-unavailable") from exc


def system_unit_runner(run, query=query_status):
    """Read system units normally; never grant native access to diab's user bus."""
    def invoke(command, **kwargs):
        if "--user" not in command:
            return run(command, **kwargs)
        if command != HOUSES_QUERY:
            raise MonitorError("user-unit-query-refused")
        value = query("houses-binding")
        checked = value.get("checked_at")
        if (type(checked) not in (int, float) or not 0 <= time.time() - checked <= 30
                or value.get("verified") is not True
                or value.get("working_directory") != HOUSES_DIRECTORY):
            raise MonitorError("service-binding-mismatch")
        return subprocess.CompletedProcess(command, 0, stdout=HOUSES_DIRECTORY, stderr="")
    return invoke
