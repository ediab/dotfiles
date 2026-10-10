#!/usr/bin/python3
"""Fixed-input note-sx updater. Keep this root-installed helper argument-free for callers."""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import PurePosixPath

ROOT_UID = 0
ROOT_GID = 0
DIAB_UID = 1000
DIAB_GID = 1000
DEPLOYER_UID = 1001
IMAGE = "ghcr.io/note-sx/server"
INITIAL_REPO_DIGEST = "sha256:e34075087bd06fb68255a056ef93d078b89e8ed355cc350a25c9500d026936f1"
ETC = "/etc/note-sx-deploy"
STATE_DIR = "/var/lib/note-sx-deploy"
BACKUP_DIR = "/var/backups/note-sx"
DOCKER_ROOT = "/var/lib/docker"
LOCK = f"{STATE_DIR}/deploy.lock"
STATE = f"{STATE_DIR}/state"
ENV_FILE = f"{ETC}/note-sx.env"
HOLD_FILE = f"{ETC}/first-update.hold"
DOCKER_CONFIG = f"{ETC}/docker"
APP_DIR = "/home/diab/apps/note-sx"
DB_DIR = f"{APP_DIR}/db"
UPLOAD_DIR = f"{APP_DIR}/userfiles"
ORIGINAL_ENV = f"{APP_DIR}/.env"
ORIGINAL_ENV_VPS = f"{APP_DIR}/.env.vps"
TAR = "/usr/bin/tar"
DOCKER = "/usr/bin/docker"
CURL = "/usr/bin/curl"
GETFACL = "/usr/bin/getfacl"
SETPRIV = "/usr/bin/setpriv"
PYTHON = "/usr/bin/python3"
SYSTEMD_INHIBIT = "/usr/bin/systemd-inhibit"
LOCK_TIMEOUT = 120
HEALTH_TIMEOUT = 150
HEALTH_INTERVAL = 5
MIN_FREE_BYTES = 2 * 1024**3
STATE_MAX_BYTES = 384
HOLD_MAX_BYTES = 512
MANIFEST_MAX_BYTES = 1024 * 1024
IMAGE_MANIFEST_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}

CLEAN_ENV = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/root",
    "DOCKER_CONFIG": DOCKER_CONFIG,
}
COMPOSE_TEMPLATE = """services:
  notesx-server:
    image: __IMAGE__
    container_name: notesx-server
    restart: always
    ports:
      - \"127.0.0.1:3010:3000\"
    env_file:
      - /etc/note-sx-deploy/note-sx.env
    volumes:
      - /home/diab/apps/note-sx/db:/notesx/db
      - /home/diab/apps/note-sx/userfiles:/notesx/userfiles
    healthcheck:
      test: [\"CMD\", \"wget\", \"-q\", \"-O\", \"/dev/null\", \"http://localhost:3000/v1/ping\"]
      interval: 30s
      timeout: 5s
      retries: 2
      start_period: 10s
"""

class Unsafe(RuntimeError):
    pass


def fail(message: str) -> None:
    raise Unsafe(message)


def digest_ok(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def run(argv: list[str], *, capture: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            argv,
            env=CLEAN_ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unsafe("fixed command failed") from exc


def lstat(path: str) -> os.stat_result:
    try:
        return os.lstat(path)
    except OSError as exc:
        raise Unsafe("required path is unavailable") from exc


def check_dir(path: str, uid: int, gid: int, mode: int) -> None:
    st = lstat(path)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_gid != gid:
        fail("unsafe directory owner or type")
    if stat.S_IMODE(st.st_mode) != mode or st.st_nlink < 2:
        fail("unsafe directory permissions")


def check_file(path: str, uid: int, gid: int, mode: int, max_bytes: int) -> os.stat_result:
    st = lstat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_gid != gid:
        fail("unsafe file owner or type")
    if stat.S_IMODE(st.st_mode) != mode or st.st_nlink != 1 or st.st_size > max_bytes:
        fail("unsafe file permissions or size")
    return st


def read_hold() -> dict[str, str]:
    st = check_file(HOLD_FILE, ROOT_UID, ROOT_GID, 0o600, HOLD_MAX_BYTES)
    try:
        fd = os.open(HOLD_FILE, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise Unsafe("first-update hold state is unavailable") from exc
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (st.st_dev, st.st_ino):
            fail("first-update hold state changed during open")
        data = os.read(fd, HOLD_MAX_BYTES + 1)
    finally:
        os.close(fd)
    timestamp = rb"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
    pattern = rb"status=(held|released)\ncreated_utc=(" + timestamp + rb")\nreason=([a-z0-9-]{1,80})\nbaseline=(sha256:[0-9a-f]{64})\nreviewed_latest=(sha256:[0-9a-f]{64})\n(?:released_utc=(" + timestamp + rb")\n)?"
    match = re.fullmatch(pattern, data)
    if not match or (match.group(1) == b"held" and match.group(6) is not None) or (match.group(1) == b"released" and match.group(6) is None):
        fail("invalid first-update hold state")
    return {key: value.decode("ascii") for key, value in zip(
        ("status", "created_utc", "reason", "baseline", "reviewed_latest", "released_utc"),
        match.groups(), strict=False
    ) if value is not None}


def write_hold_released(hold: dict[str, str]) -> None:
    data = (
        "status=released\n"
        f"created_utc={hold['created_utc']}\n"
        f"reason={hold['reason']}\n"
        f"baseline={hold['baseline']}\n"
        f"reviewed_latest={hold['reviewed_latest']}\n"
        f"released_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
    ).encode("ascii")
    fd, path = tempfile.mkstemp(prefix=".first-update-hold-", dir=ETC)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, HOLD_FILE)
        dirfd = os.open(ETC, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def no_extended_acl(path: str, *, no_defaults: bool = False) -> None:
    result = run([GETFACL, "-cp", path], capture=True, timeout=10)
    if result.returncode != 0:
        fail("could not verify path ACL")
    try:
        lines = result.stdout.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise Unsafe("could not verify path ACL") from exc
    for line in lines:
        if line.startswith("default:"):
            if no_defaults or line not in ("default:user::rwx", "default:group::r-x", "default:other::r-x"):
                fail("unexpected default ACL on fixed path")
        if re.match(r"^(user|group):[^:]+:", line):
            fail("unexpected named ACL on fixed path")


def check_data_paths() -> None:
    # Admin-owned ancestors are accepted; no unprivileged group/other writer may replace a bind path.
    expected = (
        ("/", 0, 0, 0o755),
        ("/home", 0, 0, 0o755),
        ("/home/diab", DIAB_UID, DIAB_GID, 0o751),
        ("/home/diab/apps", DIAB_UID, DIAB_GID, 0o755),
        (APP_DIR, DIAB_UID, DIAB_GID, 0o700),
        (DB_DIR, DIAB_UID, DIAB_GID, 0o700),
        (UPLOAD_DIR, DIAB_UID, DIAB_GID, 0o700),
    )
    for path, uid, gid, mode in expected:
        check_dir(path, uid, gid, mode)
        no_extended_acl(path, no_defaults=path in (APP_DIR, DB_DIR, UPLOAD_DIR))
    for path in (ORIGINAL_ENV, ORIGINAL_ENV_VPS):
        check_file(path, DIAB_UID, DIAB_GID, 0o600, 1024 * 1024)
        no_extended_acl(path, no_defaults=True)


def check_control_installation(*, require_env: bool = True) -> None:
    check_dir(ETC, ROOT_UID, ROOT_GID, 0o700)
    check_dir(DOCKER_CONFIG, ROOT_UID, ROOT_GID, 0o700)
    check_dir(STATE_DIR, ROOT_UID, ROOT_GID, 0o700)
    check_dir(BACKUP_DIR, ROOT_UID, ROOT_GID, 0o700)
    docker_root = lstat(DOCKER_ROOT)
    if (not stat.S_ISDIR(docker_root.st_mode) or docker_root.st_uid != ROOT_UID or
            docker_root.st_gid != ROOT_GID or stat.S_IMODE(docker_root.st_mode) & 0o022):
        fail("unsafe Docker storage directory")
    if docker_root.st_dev != os.stat(BACKUP_DIR, follow_symlinks=False).st_dev:
        fail("Docker and snapshot storage must share the checked filesystem")
    check_file(LOCK, ROOT_UID, ROOT_GID, 0o600, 0)
    check_file(HOLD_FILE, ROOT_UID, ROOT_GID, 0o600, HOLD_MAX_BYTES)
    try:
        if require_env or os.path.lexists(ENV_FILE):
            check_file(ENV_FILE, ROOT_UID, ROOT_GID, 0o600, 64 * 1024)
    except OSError as exc:
        raise Unsafe("protected environment file unavailable") from exc
    no_extended_acl(ETC, no_defaults=True)
    no_extended_acl(DOCKER_CONFIG, no_defaults=True)
    no_extended_acl(STATE_DIR, no_defaults=True)
    no_extended_acl(BACKUP_DIR, no_defaults=True)
    no_extended_acl(HOLD_FILE, no_defaults=True)
    if require_env or os.path.lexists(ENV_FILE):
        no_extended_acl(ENV_FILE, no_defaults=True)
    try:
        if next(os.scandir(DOCKER_CONFIG), None) is not None:
            fail("Docker config directory must remain empty")
    except OSError as exc:
        raise Unsafe("could not verify Docker config directory") from exc


def check_installation() -> None:
    check_control_installation()
    check_data_paths()


def private_digest(path: str, uid: int, gid: int, mode: int, max_bytes: int) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise Unsafe("could not safely verify protected environment file") from exc
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid or before.st_gid != gid or
                stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1 or before.st_size > max_bytes):
            fail("protected environment file metadata changed")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, 8192)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                fail("protected environment file is too large")
            digest.update(chunk)
        after = os.fstat(fd)
        if total != before.st_size or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            fail("protected environment file changed while reading")
        return digest.digest()
    finally:
        os.close(fd)


def copy_env_file() -> None:
    if os.path.lexists(ENV_FILE):
        check_file(ENV_FILE, ROOT_UID, ROOT_GID, 0o600, 64 * 1024)
        source_hash = private_digest(ORIGINAL_ENV, DIAB_UID, DIAB_GID, 0o600, 64 * 1024)
        target_hash = private_digest(ENV_FILE, ROOT_UID, ROOT_GID, 0o600, 64 * 1024)
        if not hmac.compare_digest(source_hash, target_hash):
            fail("existing root environment copy differs from the current app environment")
        return
    try:
        src = os.open(ORIGINAL_ENV, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise Unsafe("could not safely open the original environment file") from exc
    fd = -1
    tmp = None
    try:
        st = os.fstat(src)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != DIAB_UID or st.st_gid != DIAB_GID or
                stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1 or st.st_size > 64 * 1024):
            fail("original environment file is not protected")
        source_hash = hashlib.sha256()
        fd, tmp = tempfile.mkstemp(prefix=".note-sx-env-", dir=ETC)
        os.fchmod(fd, 0o600)
        total = 0
        with os.fdopen(fd, "wb", closefd=True) as out:
            fd = -1
            while True:
                chunk = os.read(src, 8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > 64 * 1024:
                    fail("original environment file is too large")
                source_hash.update(chunk)
                out.write(chunk)
            after = os.fstat(src)
            if (st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                fail("original environment file changed during transfer")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, ENV_FILE)
        dfd = os.open(ETC, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        target_hash = private_digest(ENV_FILE, ROOT_UID, ROOT_GID, 0o600, 64 * 1024)
        if not hmac.compare_digest(source_hash.digest(), target_hash):
            fail("protected environment transfer verification failed")
    except Exception:
        if fd >= 0:
            os.close(fd)
        if tmp:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        raise
    finally:
        os.close(src)


def legacy_lock_path(which: str) -> tuple[str, int, int, str]:
    if which == "diab":
        return "/home/diab/.cache/vps-deploy.lock", DIAB_UID, DIAB_GID, "/home/diab"
    if which == "deployer":
        return "/home/deployer/.cache/vps-deploy.lock", DEPLOYER_UID, DEPLOYER_UID, "/home/deployer"
    fail("unknown legacy lock")


def open_nofollow_lock(path: str, uid: int, gid: int, home: str) -> int:
    # This code runs as the lock owner, never as root. O_NOFOLLOW prevents a legacy symlink lock.
    try:
        home_st = os.lstat(home)
        cache_st = os.lstat(os.path.dirname(path))
        if (not stat.S_ISDIR(home_st.st_mode) or home_st.st_uid != uid or stat.S_IMODE(home_st.st_mode) & 0o022 or
                stat.S_ISLNK(cache_st.st_mode) or not stat.S_ISDIR(cache_st.st_mode) or
                cache_st.st_uid != uid or (stat.S_IMODE(cache_st.st_mode) & 0o022)):
            fail("unsafe legacy lock parent")
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        st = os.fstat(fd)
    except OSError as exc:
        raise Unsafe("unsafe legacy lock file") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_gid != gid or st.st_nlink != 1:
        os.close(fd)
        fail("unsafe legacy lock file")
    return fd


def hold_legacy_lock(which: str) -> int:
    path, uid, gid, home = legacy_lock_path(which)
    if os.geteuid() != uid:
        fail("legacy lock must run as its owning user")
    fd = open_nofollow_lock(path, uid, gid, home)
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                fail("legacy lock timeout")
            time.sleep(0.1)


def acquire_root_lock() -> int:
    st = check_file(LOCK, ROOT_UID, ROOT_GID, 0o600, 0)
    try:
        fd = os.open(LOCK, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise Unsafe("unsafe root lock") from exc
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != (st.st_dev, st.st_ino):
        os.close(fd)
        fail("root lock changed during open")
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                fail("root transaction lock timeout")
            time.sleep(0.1)


def read_state() -> tuple[str, str, str | None, str | None] | None:
    try:
        fd = os.open(STATE, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Unsafe("unsafe transaction state") from exc
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != ROOT_UID or st.st_gid != ROOT_GID or
                stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1 or st.st_size > STATE_MAX_BYTES):
            fail("unsafe transaction state")
        data = os.read(fd, STATE_MAX_BYTES + 1)
    finally:
        os.close(fd)
    match = re.fullmatch(
        rb"current=(sha256:[0-9a-f]{64})\ncurrent_ref=(sha256:[0-9a-f]{64})\n"
        rb"previous=(none|sha256:[0-9a-f]{64})\nprevious_ref=(none|sha256:[0-9a-f]{64})\n",
        data,
    )
    if not match:
        fail("invalid transaction state")
    current, current_ref = match.group(1).decode("ascii"), match.group(2).decode("ascii")
    previous_raw, previous_ref_raw = match.group(3).decode("ascii"), match.group(4).decode("ascii")
    if (previous_raw == "none") != (previous_ref_raw == "none"):
        fail("incomplete previous image state")
    return current, current_ref, None if previous_raw == "none" else previous_raw, None if previous_ref_raw == "none" else previous_ref_raw


def write_state(current: str, current_ref: str, previous: str | None, previous_ref: str | None) -> None:
    if (not digest_ok(current) or not digest_ok(current_ref) or
            (previous is not None and not digest_ok(previous)) or
            (previous_ref is not None and not digest_ok(previous_ref)) or
            ((previous is None) != (previous_ref is None))):
        fail("invalid transaction digest")
    data = f"current={current}\ncurrent_ref={current_ref}\nprevious={previous or 'none'}\nprevious_ref={previous_ref or 'none'}\n".encode("ascii")
    fd, path = tempfile.mkstemp(prefix=".state-", dir=STATE_DIR)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, STATE)
        dirfd = os.open(STATE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def restore_state(state_before: tuple[str, str, str | None, str | None] | None, attempted: tuple[str, str]) -> None:
    if state_before is not None:
        write_state(*state_before)
        return
    current = read_state()
    if current is None:
        return
    if current != (*attempted, None, None):
        fail("state changed during failed first promotion")
    check_file(STATE, ROOT_UID, ROOT_GID, 0o600, STATE_MAX_BYTES)
    os.unlink(STATE)
    dirfd = os.open(STATE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)


def docker(argv: list[str], *, capture: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    return run([DOCKER, *argv], capture=capture, timeout=timeout)


def manifest_amd64_digest(reference: str) -> str:
    is_latest = reference == f"{IMAGE}:latest"
    if not is_latest and not re.fullmatch(re.escape(IMAGE) + r"@sha256:[0-9a-f]{64}", reference):
        fail("invalid image manifest reference")
    result = docker(["manifest", "inspect", "--verbose", reference], capture=True, timeout=60)
    if result.returncode != 0 or len(result.stdout) > MANIFEST_MAX_BYTES:
        fail("could not resolve immutable image manifest")
    try:
        metadata = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Unsafe("invalid image manifest metadata") from exc
    single_manifest = isinstance(metadata, dict)
    if single_manifest:
        entries = [metadata]
    elif isinstance(metadata, list) and metadata:
        entries = metadata
    else:
        fail("unexpected image manifest metadata")

    found = []
    for entry in entries:
        if not isinstance(entry, dict):
            fail("unexpected image manifest metadata")
        desc = entry.get("Descriptor")
        if not isinstance(desc, dict) or not digest_ok(desc.get("digest")) or not isinstance(desc.get("mediaType"), str):
            fail("malformed image manifest descriptor")
        platform = desc.get("platform")
        if (not isinstance(platform, dict) or not isinstance(platform.get("os"), str) or
                not isinstance(platform.get("architecture"), str)):
            fail("malformed image platform metadata")
        if platform["os"] != "linux" or platform["architecture"] != "amd64":
            if single_manifest:
                fail("single image manifest is not linux/amd64")
            continue
        digest = desc["digest"]
        media_type = desc["mediaType"]
        expected_ref = f"{IMAGE}:latest@{digest}" if is_latest else f"{IMAGE}@{digest}"
        if media_type not in IMAGE_MANIFEST_TYPES or entry.get("Ref") != expected_ref:
            fail("upstream linux/amd64 immutable reference or media type was malformed")
        found.append(digest)
    if len(found) != 1:
        fail("image manifest did not identify one linux/amd64 digest")
    return found[0]


def latest_digest() -> str:
    return manifest_amd64_digest(f"{IMAGE}:latest")


def image_repo_digests(image_ref: str) -> list[str]:
    result = docker(["image", "inspect", "--format", "{{json .RepoDigests}}", image_ref], capture=True, timeout=30)
    if result.returncode != 0:
        fail("image digest metadata unavailable")
    try:
        refs = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Unsafe("invalid image digest metadata") from exc
    if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
        fail("invalid image digest metadata")
    matches = [x for x in refs if x.startswith(f"{IMAGE}@")]
    if len(matches) != 1 or not re.fullmatch(re.escape(IMAGE) + r"@sha256:[0-9a-f]{64}", matches[0]):
        fail("expected exactly one note-sx immutable image digest")
    return matches


def current_repo_digest() -> str:
    result = docker(["inspect", "--format", "{{.Image}}", "notesx-server"], capture=True, timeout=30)
    if result.returncode != 0:
        fail("running note-sx container unavailable")
    image_id = result.stdout.decode("ascii", "strict").strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        fail("running image id was malformed")
    return image_repo_digests(image_id)[0].split("@", 1)[1]


def current_digest() -> str:
    return manifest_amd64_digest(f"{IMAGE}@{current_repo_digest()}")


def print_current_report(actual: str, actual_ref: str, latest: str) -> None:
    print(f"running_repo_digest={actual_ref}")
    print(f"running_linux_amd64_digest={actual}")
    print(f"upstream_linux_amd64_latest_digest={latest}")
    print(f"latest_moved={'no' if actual == latest else 'yes'}")
    print("semantic_version=not_available_from_current_image_metadata")
    print("data_migration_compatibility=not_assessed; image rollback does not restore SQLite/uploads")


def compose_manifest(digest: str) -> str:
    if not digest_ok(digest):
        fail("invalid compose digest")
    fd, path = tempfile.mkstemp(prefix=".compose-", dir=STATE_DIR)
    try:
        os.fchmod(fd, 0o600)
        payload = COMPOSE_TEMPLATE.replace("__IMAGE__", f"{IMAGE}@{digest}").encode("ascii")
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return path
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def compose_args(manifest: str) -> list[str]:
    return [
        "compose", "--project-directory", ETC, "--env-file", "/dev/null",
        "--project-name", "note-sx", "-f", manifest,
    ]


def compose_stop(digest: str) -> None:
    manifest = compose_manifest(digest)
    try:
        result = docker([*compose_args(manifest), "stop"], timeout=90)
        if result.returncode != 0:
            fail("could not stop note-sx cleanly")
    finally:
        os.unlink(manifest)


def compose_up(digest: str) -> bool:
    manifest = compose_manifest(digest)
    try:
        result = docker([*compose_args(manifest), "up", "-d", "--no-build", "--pull", "never"], timeout=120)
        return result.returncode == 0
    finally:
        os.unlink(manifest)


def container_stopped() -> bool:
    result = docker(["inspect", "--format", "{{.State.Status}}", "notesx-server"], capture=True, timeout=20)
    return result.returncode == 0 and result.stdout.decode("ascii", "ignore").strip() == "exited"


def no_running_data_writers() -> None:
    for path in (DB_DIR, UPLOAD_DIR):
        result = docker(["ps", "--quiet", "--filter", f"volume={path}"], capture=True, timeout=20)
        if result.returncode != 0 or result.stdout.strip():
            fail("a running container still mounts note-sx state")


def container_healthy() -> bool:
    result = docker(
        ["inspect", "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", "notesx-server"],
        capture=True,
        timeout=20,
    )
    if result.returncode != 0 or result.stdout.decode("ascii", "ignore").strip() != "running|healthy":
        return False
    ping = run([CURL, "--fail", "--silent", "--show-error", "--max-time", "5", "--output", "/dev/null", "http://127.0.0.1:3010/v1/ping"], timeout=10)
    return ping.returncode == 0


def wait_healthy(expected_ref: str) -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT
    while True:
        try:
            if current_repo_digest() == expected_ref and container_healthy():
                return True
        except Unsafe:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(HEALTH_INTERVAL)


def data_summary() -> int:
    total = 0
    deadline = time.monotonic() + 120
    app_device = os.stat(APP_DIR, follow_symlinks=False).st_dev
    inodes: dict[tuple[int, int], list[int]] = {}
    roots = (DB_DIR, UPLOAD_DIR)
    for root in roots:
        stack = [root]
        if os.stat(root, follow_symlinks=False).st_dev != app_device:
            fail("mount point inside note-sx state tree")
        while stack:
            if time.monotonic() >= deadline:
                fail("note-sx state metadata scan timed out")
            directory = stack.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            st = entry.stat(follow_symlinks=False)
                        except OSError as exc:
                            raise Unsafe("state tree changed during metadata scan") from exc
                        if st.st_dev != app_device:
                            fail("mount point inside note-sx state tree")
                        if stat.S_ISDIR(st.st_mode):
                            stack.append(entry.path)
                        elif stat.S_ISREG(st.st_mode):
                            key = (st.st_dev, st.st_ino)
                            row = inodes.setdefault(key, [0, st.st_nlink])
                            row[0] += 1
                            total += st.st_size
                        elif stat.S_ISLNK(st.st_mode):
                            # Keep app-created symlinks as links; the tar command never dereferences them.
                            continue
                        else:
                            fail("unsupported special file in note-sx state")
            except OSError as exc:
                raise Unsafe("could not inspect note-sx state tree") from exc
    if any(names != nlink for names, nlink in inodes.values()):
        fail("external hardlink in note-sx state tree")
    return total


def free_space(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError as exc:
        raise Unsafe("could not determine free space") from exc


def validate_archive(path: str) -> None:
    found: set[str] = set()
    deadline = time.monotonic() + 120
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive:
                if time.monotonic() >= deadline:
                    fail("snapshot archive validation timed out")
                name = PurePosixPath(member.name)
                parts = name.parts
                if name.is_absolute() or not parts or any(part in ("", ".", "..") for part in parts):
                    fail("unsafe snapshot member path")
                if parts[0] not in ("db", "userfiles"):
                    fail("unexpected snapshot root")
                found.add(parts[0])
                if member.isdev() or member.isfifo():
                    fail("unsupported special file in snapshot")
                if member.islnk():
                    link = PurePosixPath(member.linkname)
                    if link.is_absolute() or any(part == ".." for part in link.parts) or not link.parts or link.parts[0] not in ("db", "userfiles"):
                        fail("unsafe hardlink in snapshot")
    except (OSError, tarfile.TarError, EOFError) as exc:
        raise Unsafe("snapshot archive validation failed") from exc
    if found != {"db", "userfiles"}:
        fail("snapshot archive incomplete")


def create_snapshot(logical_bytes: int) -> str:
    required = logical_bytes + MIN_FREE_BYTES
    if free_space(BACKUP_DIR) < required:
        fail("insufficient space for verified note-sx snapshot")
    fd, tmp = tempfile.mkstemp(prefix=".note-sx-snapshot-", dir=BACKUP_DIR)
    try:
        os.fchmod(fd, 0o600)
        os.close(fd)
        result = run([TAR, "--one-file-system", "-czf", tmp, "-C", APP_DIR, "db", "userfiles"], timeout=300)
        if result.returncode != 0:
            fail("note-sx snapshot command failed")
        validate_archive(tmp)
        archive_fd = os.open(tmp, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            os.fsync(archive_fd)
        finally:
            os.close(archive_fd)
        suffix = uuid.uuid4().hex
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        final = os.path.join(BACKUP_DIR, f"state-{stamp}-{suffix}.tgz")
        os.rename(tmp, final)
        dirfd = os.open(BACKUP_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        return final
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def rotate_new_backups() -> None:
    entries = []
    try:
        with os.scandir(BACKUP_DIR) as scan:
            for entry in scan:
                if not (entry.name.startswith("state-") and entry.name.endswith(".tgz")):
                    continue
                st = entry.stat(follow_symlinks=False)
                if (not stat.S_ISREG(st.st_mode) or st.st_uid != ROOT_UID or st.st_gid != ROOT_GID or
                        stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1):
                    fail("unsafe file in note-sx snapshot rotation set")
                entries.append((st.st_mtime_ns, entry.name, entry.path))
    except OSError as exc:
        raise Unsafe("could not inspect snapshot retention set") from exc
    entries.sort(reverse=True)
    for _, _, path in entries[3:]:
        os.unlink(path)
    if len(entries) > 3:
        dirfd = os.open(BACKUP_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)


def recover(digest: str, image_ref: str) -> bool:
    if not compose_up(image_ref):
        return False
    return wait_healthy(image_ref)


def recover_and_report(digest: str, image_ref: str) -> bool:
    if recover(digest, image_ref):
        print(f"recovery=healthy digest={digest} image_ref={image_ref}")
        return True
    try:
        observed = current_repo_digest()
    except Unsafe:
        observed = "unknown"
    print(f"recovery=failed expected={digest} image_ref={image_ref} observed_ref={observed}; manual service/data review required", file=sys.stderr)
    return False


def transaction(target: str, target_ref: str, old: str, old_ref: str, state_before: tuple[str, str, str | None, str | None] | None) -> int:
    snapshot = None
    try:
        if current_digest() != old or current_repo_digest() != old_ref or not container_healthy():
            fail("running app changed or was unhealthy before stop")
        check_data_paths()
        compose_stop(old_ref)
        if not container_stopped():
            fail("note-sx container remained active after stop")
        no_running_data_writers()
        logical_bytes = data_summary()
        snapshot = create_snapshot(logical_bytes)
        if min(free_space(DOCKER_ROOT), free_space(BACKUP_DIR)) < MIN_FREE_BYTES:
            fail("free-space reserve was breached by snapshot creation")
        rotate_new_backups()
        print(f"snapshot=verified bytes={os.path.getsize(snapshot)}")
    except Exception as exc:
        print(f"note-sx-deploy: snapshot/stop failed: {exc}", file=sys.stderr)
        recover_and_report(old, old_ref)
        return 1

    try:
        activated = compose_up(target_ref) and wait_healthy(target_ref)
    except Exception as exc:
        print(f"note-sx-deploy: activation interrupted ({exc}); recovering digest={old}", file=sys.stderr)
        activated = False
    if not activated:
        print(f"note-sx-deploy: activation failed; recovering digest={old}", file=sys.stderr)
        recover_and_report(old, old_ref)
        return 1

    if target != old or state_before is None:
        previous = old if state_before is not None else None
        previous_ref = old_ref if state_before is not None else None
        try:
            write_state(target, target_ref, previous, previous_ref)
        except Exception:
            # A failed promotion must not leave the new image running with stale state.
            try:
                restore_state(state_before, (target, target_ref))
            except Exception:
                print("note-sx-deploy: transaction state could not be restored", file=sys.stderr)
            print(f"note-sx-deploy: state promotion failed; recovering digest={old}", file=sys.stderr)
            recover_and_report(old, old_ref)
            return 1

    print(f"note-sx-deploy: healthy digest={target} image_ref={target_ref} previous={state_before[0] if state_before else 'none'}")
    return 0


def do_update() -> int:
    check_control_installation(require_env=False)
    hold = read_hold()
    if hold["status"] == "held":
        actual_ref = current_repo_digest()
        actual = current_digest()
        state = read_state()
        if (actual_ref != hold["baseline"] or
                (state is not None and (state[0] != actual or state[1] != actual_ref))):
            fail("held baseline/state no longer matches the running image")
        if not container_healthy():
            fail("first-update hold is active but the current service is unhealthy")
        print(f"note-sx-deploy: update=held reason={hold['reason']} current_ref={actual_ref} current_linux_amd64={actual} reviewed_latest={hold['reviewed_latest']}; no pull, stop, snapshot, or activation; exit=2")
        return 2
    check_installation()
    state = read_state()
    if state is None:
        fail("current digest is not initialized; use root-console --verify-current then --cutover-current")
    current, current_ref, _, _ = state
    actual_ref = current_repo_digest()
    actual = current_digest()
    if actual != current or actual_ref != current_ref:
        fail(f"runtime/state mismatch: running={actual} ref={actual_ref} recorded={current} ref={current_ref}")
    if not container_healthy():
        fail("current service is unhealthy; refusing automatic update")
    selected = latest_digest()
    if selected == current:
        print(f"note-sx-deploy: already current linux/amd64 digest={current} image_ref={current_ref}; no pull or restart")
        return 0
    if min(free_space(DOCKER_ROOT), free_space(BACKUP_DIR)) < MIN_FREE_BYTES:
        fail("insufficient free space before immutable pull")
    pulled = docker(["pull", f"{IMAGE}@{selected}"], timeout=300)
    if pulled.returncode != 0:
        fail("immutable upstream pull failed; running app left untouched")
    if image_repo_digests(f"{IMAGE}@{selected}")[0].split("@", 1)[1] != selected:
        fail("pulled image digest does not match selected linux/amd64 digest")
    if min(free_space(DOCKER_ROOT), free_space(BACKUP_DIR)) < MIN_FREE_BYTES:
        fail("insufficient free space after immutable pull")
    print(f"update_selection current_linux_amd64={current} latest_linux_amd64={selected}")
    return transaction(selected, selected, current, current_ref, state)


def do_verify_current() -> int:
    check_control_installation(require_env=False)
    hold = read_hold()
    state = read_state()
    actual_ref = current_repo_digest()
    actual = current_digest()
    latest = latest_digest()
    print_current_report(actual, actual_ref, latest)
    if state is None:
        print("transaction_state=not_initialized")
    else:
        print(f"transaction_state_current_linux_amd64={state[0]}")
        print(f"transaction_state_current_ref={state[1]}")
        print(f"transaction_state_previous_linux_amd64={state[2] or 'none'}")
        print(f"transaction_state_previous_ref={state[3] or 'none'}")
        print(f"transaction_state_matches_runtime={'yes' if state[0] == actual and state[1] == actual_ref else 'no'}")
    print(f"first_update_hold={hold['status']} reason={hold['reason']} baseline={hold['baseline']} reviewed_latest={hold['reviewed_latest']}")
    if hold.get("released_utc"):
        print(f"first_update_hold_released_utc={hold['released_utc']}")
    healthy = container_healthy()
    print(f"service_healthy={'yes' if healthy else 'no'}")
    return 0 if healthy else 1


def do_cutover_current() -> int:
    check_control_installation(require_env=False)
    hold = read_hold()
    if hold["status"] != "held" or hold["baseline"] != INITIAL_REPO_DIGEST:
        fail("current-image cutover requires the root-controlled e340 first-update hold")
    check_data_paths()
    if read_state() is not None:
        fail("transaction state already exists; current cutover is one-time only")
    actual_ref = current_repo_digest()
    actual = current_digest()
    latest = latest_digest()
    print_current_report(actual, actual_ref, latest)
    if actual_ref != INITIAL_REPO_DIGEST:
        fail(f"baseline changed: expected_repo_digest={INITIAL_REPO_DIGEST} running_repo_digest={actual_ref}; no image update performed")
    if not container_healthy():
        fail("current service is unhealthy; refusing current-image cutover")
    copy_env_file()
    check_control_installation()
    print(f"cutover_image_unchanged=yes image_ref={actual_ref} linux_amd64_payload={actual}; latest_was_not_pulled=yes; first_newer_image_update=held")
    return transaction(actual, actual_ref, actual, actual_ref, None)


def do_release_first_update_hold() -> int:
    check_control_installation()
    hold = read_hold()
    if hold["status"] != "held":
        fail("first newer-image update hold is not active")
    state = read_state()
    actual_ref = current_repo_digest()
    actual = current_digest()
    if (actual_ref != hold["baseline"] or state is None or
            state[0] != actual or state[1] != actual_ref):
        fail("hold release requires the cutover baseline and transaction state to match runtime")
    if not container_healthy():
        fail("hold release requires the current service to be healthy")
    selected = latest_digest()
    if selected != hold["reviewed_latest"] or selected != actual:
        fail(f"upstream linux/amd64 payload differs from the held/reviewed current image: current={actual} reviewed={hold['reviewed_latest']} latest={selected}; keep hold active")
    write_hold_released(hold)
    print(f"first_update_hold=released baseline_ref={actual_ref} current_linux_amd64={actual} reviewed_latest={selected}; automatic updates resume on the next ordinary invocation")
    return 0


def do_rollback_previous() -> int:
    check_installation()
    state = read_state()
    if state is None or state[2] is None or state[3] is None:
        fail("no previous image digest is recorded")
    current_ref = current_repo_digest()
    current = current_digest()
    if state[0] != current or state[1] != current_ref or not container_healthy():
        fail("rollback requires the recorded current image to be running and healthy")
    target, target_ref = state[2], state[3]
    if target == current or image_repo_digests(f"{IMAGE}@{target_ref}")[0].split("@", 1)[1] != target_ref:
        fail("previous immutable image is unavailable or invalid; no pull performed")
    print(f"rollback=starting current={current} previous={target} image_ref={target_ref} data_restore=not_performed")
    return transaction(target, target_ref, current, current_ref, state)


def run_as_legacy_owner(which: str) -> subprocess.Popen:
    _, uid, gid, home = legacy_lock_path(which)
    # setpriv execs the lock holder; runuser supervises it and can kill it after TERM.
    return subprocess.Popen(
        [SETPRIV, f"--reuid={uid}", f"--regid={gid}", "--init-groups", "--",
         PYTHON, __file__, f"--hold-legacy-{which}"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "HOME": home},
        text=True,
        bufsize=1,
        close_fds=True,
    )


def wait_lock_holder(process: subprocess.Popen, seconds: int = LOCK_TIMEOUT) -> None:
    import selectors
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    events = selector.select(seconds)
    selector.close()
    if not events or process.stdout.readline().strip() != "LOCKED":
        process.kill()
        process.wait()
        fail("legacy cleanup lock unavailable")


def run_locked_action(action: str) -> int:
    lock_fd = acquire_root_lock()
    legacy = None
    try:
        # The cleanup job still uses this diab-owned lock. Acquire it through its owner,
        # with O_NOFOLLOW, rather than root-opening a path under /home.
        legacy = run_as_legacy_owner("diab")
        wait_lock_holder(legacy)
        if action == "update":
            return do_update()
        if action == "cutover":
            return do_cutover_current()
        if action == "rollback":
            return do_rollback_previous()
        fail("invalid internal mode")
    finally:
        if legacy is not None:
            try:
                legacy.stdin.close()
            except (OSError, AttributeError):
                pass
            try:
                legacy.wait(timeout=5)
            except subprocess.TimeoutExpired:
                legacy.kill()
                legacy.wait()
        os.close(lock_fd)


def run_inhibited_action(action: str) -> int:
    # Keep systemd-inhibit alive through unit TERM; the command child installs recovery handlers.
    for caught_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(caught_signal, signal.SIG_IGN)
    cmd = [SYSTEMD_INHIBIT, "--what=shutdown", "--who=note-sx-deploy", "--why=note-sx transaction",
           PYTHON, __file__, f"--_inhibited-{action}"]
    try:
        os.execve(SYSTEMD_INHIBIT, cmd, CLEAN_ENV)
    except OSError as exc:
        raise Unsafe("shutdown inhibitor could not be started") from exc
    fail("shutdown inhibitor returned unexpectedly")


def main() -> int:
    if os.geteuid() not in (ROOT_UID, DIAB_UID, DEPLOYER_UID):
        fail("unsupported identity")
    args = sys.argv[1:]
    if args in (["--hold-legacy-diab"], ["--hold-legacy-deployer"]):
        which = "diab" if args[0].endswith("diab") else "deployer"
        fd = hold_legacy_lock(which)
        try:
            for caught_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                signal.signal(caught_signal, signal.SIG_IGN)
            print("LOCKED", flush=True)
            sys.stdin.buffer.read(1)
        finally:
            os.close(fd)
        return 0
    if os.geteuid() != ROOT_UID:
        fail("root privileges required")
    if args == []:
        return run_inhibited_action("update")
    if args == ["--verify-current"]:
        lock_fd = acquire_root_lock()
        try:
            return do_verify_current()
        finally:
            os.close(lock_fd)
    if args == ["--cutover-current"]:
        return run_inhibited_action("cutover")
    if args == ["--release-first-update-hold"]:
        lock_fd = acquire_root_lock()
        try:
            return do_release_first_update_hold()
        finally:
            os.close(lock_fd)
    if args == ["--rollback-previous"]:
        return run_inhibited_action("rollback")
    if args in (["--_inhibited-update"], ["--_inhibited-cutover"], ["--_inhibited-rollback"]):
        action = args[0].removeprefix("--_inhibited-")
        return run_locked_action(action)
    fail("usage: note-sx-deploy [--verify-current|--cutover-current|--release-first-update-hold|--rollback-previous]")


def interrupted(signum: int, _frame: object) -> None:
    raise Unsafe(f"deployment interrupted by signal {signum}")


for caught_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(caught_signal, interrupted)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Unsafe as exc:
        print(f"note-sx-deploy: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("note-sx-deploy: interrupted", file=sys.stderr)
        raise SystemExit(130)
