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


SYSTEM_CONFIGS = frozenset({Path("/etc/vps-security-scan/config.json"),
                            Path("/etc/vps-security-scan/native.json"),
                            Path("/etc/vps-security-scan/image-watchdog.json")})
SHARED_LOCK = Path("/run/vps-security-scan/scan.lock")
IMAGE_STATE = Path("/var/lib/vps-security-scan/image")
NATIVE_STATE = Path("/var/lib/vps-security-scan/native")
SHARED_TRIVY_CACHE = Path("/var/cache/vps-security-scan/trivy")


def root_ancestors(path: Path) -> None:
    for parent in path.parents:
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022):
            raise MonitorError("untrusted root-owned path ancestor")


def trusted_mail_transport(root: Path) -> None:
    """Validate the whole immutable snapshot, including transitive imports/pyc.

    Permission checks are safe from a same-UID rename after ancestor validation:
    neither monitor identity can modify any directory in this root-owned tree.
    """
    if not root.is_absolute():
        raise MonitorError("email-transport-path-untrusted")
    root_ancestors(root / "summary_config.py")
    required = {"summary_config.py", "scrape_timeline.py", "fastmail_jmap.py", "util.py", ".env.local"}
    seen = set()
    count = total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        if len(Path(directory).relative_to(root).parts) > 2:
            raise MonitorError("email-transport-tree-untrusted")
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            count += 1
            if (count > 64 or info.st_uid != 0 or info.st_mode & 0o022
                    or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
                    or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
                raise MonitorError("email-transport-tree-untrusted")
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
                if total > 2 * 1024 * 1024:
                    raise MonitorError("email-transport-tree-untrusted")
                if Path(directory) == root:
                    seen.add(name)
    if not required <= seen:
        raise MonitorError("email-transport-incomplete")


def read_monitor_config(path: Path, *, max_bytes: int = 65536) -> Any:
    if path in SYSTEM_CONFIGS:
        root_ancestors(path)
        return read_private_json(path, max_bytes=max_bytes, _root_owned=True)
    return read_private_json(path, max_bytes=max_bytes)


def read_private_json(path: Path, *, max_bytes: int = 65536, _root_owned: bool = False) -> Any:
    """Read a same-user private regular config file without following symlinks."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as exc:
        raise MonitorError(f"required configuration missing: {path.name}") from exc
    except OSError as exc:
        raise MonitorError(f"cannot securely open private file: {path.name}") from exc
    try:
        info = os.fstat(fd)
        owner = 0 if _root_owned else os.getuid()
        unsafe_mode = (stat.S_IMODE(info.st_mode) not in (0o600, 0o640)
                       if _root_owned else bool(info.st_mode & 0o077))
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner or unsafe_mode
                or (_root_owned and info.st_nlink != 1) or info.st_size > max_bytes):
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
            if path == SHARED_LOCK:
                root_ancestors(path)
                fd = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                        or stat.S_IMODE(info.st_mode) != 0o660):
                    os.close(fd)
                    raise MonitorError("untrusted shared scan lock")
                self.stream = os.fdopen(fd, "r+", encoding="ascii")
            else:
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
    """Acknowledge quiet recoveries locally; other events require confirmed mail."""
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
