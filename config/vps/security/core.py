"""Small, private-state primitives shared by staged VPS monitoring jobs."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable


class MonitorError(RuntimeError):
    pass


def read_private_json(path: Path, *, max_bytes: int = 65536) -> Any:
    """Read a same-user private regular config file without following symlinks."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as exc:
        raise MonitorError(f"required configuration missing: {path.name}") from exc
    except OSError as exc:
        raise MonitorError(f"cannot securely open private file: {path.name}") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > max_bytes):
            raise MonitorError(f"configuration must be a bounded private regular file: {path.name}")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            payload = stream.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise MonitorError(f"configuration exceeds size bound: {path.name}")
        return json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError(f"invalid configuration: {path.name}") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def atomic_json(path: Path, value: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        dirfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def locked(path: Path):
    """Return a context manager for the common interactive/scheduled scan lock."""
    class Lock:
        def __enter__(self):
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(path.parent, 0o700)
            self.stream = path.open("a", encoding="ascii")
            os.chmod(path, 0o600)
            try:
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                self.stream.close()
                raise
            return self

        def __exit__(self, *_exc):
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
    return Lock()


QUIET_EVENTS = frozenset({"recovered", "findings_cleared"})


def deliver_transition(
    state_path: Path,
    fingerprint: str,
    send: Callable[[str], bool],
    summary: str,
    *,
    event: str,
    now: int,
    extra: dict[str, Any] | None = None,
    state_max_bytes: int = 65536,
) -> bool:
    """Only commit notification state after the existing mail transport confirms."""
    old: dict[str, Any] = {}
    try:
        state_path.lstat()
    except FileNotFoundError:
        pass
    else:
        value = read_private_json(state_path, max_bytes=state_max_bytes)
        if not isinstance(value, dict):
            raise MonitorError("notification state has invalid shape")
        old = value
    if old.get("delivered_fingerprint") == fingerprint:
        return False
    # Email only about problems; recoveries just advance the state silently.
    if event not in QUIET_EVENTS and not send(summary):
        raise MonitorError("notification delivery failed; state not advanced")
    updated = dict(old)
    updated.update({
        "delivered_fingerprint": fingerprint,
        "delivered_event": event,
        "sent_at": now,
    })
    if extra:
        updated.update(extra)
    atomic_json(state_path, updated)
    return True
