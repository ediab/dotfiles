#!/usr/bin/env python3
"""Apply global Pi settings and reconcile only previously configured packages.

prepare SETTINGS records pending cleanup before replacing live settings; reconcile
finishes it. Both phases run locally or from the VPS's agent-content staging dir.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def read_settings(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("packages", []), list):
        raise ValueError(f"Invalid settings: {path}")
    return data


def write_json(path, data):
    # Atomic replacement keeps capture/startup readers away from partial JSON.
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def package(source, agent_dir):
    """Return (identity, managed install path, npm version selector).

    Relative local sources resolve from global settings, not the caller's cwd.
    Pi itself performs installation/removal and version-range resolution.
    """
    if source.startswith("npm:"):
        spec = source[4:]
        name, separator, version = spec.rpartition("@")
        if not separator or not name:
            name, version = spec, ""
        if (not re.fullmatch(r"(?:@[\w.-]+/)?[\w.-]+", name)
                or name.split("/")[-1] in (".", "..")):
            raise ValueError(f"Invalid npm source: {source}")
        return "npm:" + name, agent_dir / "npm/node_modules" / name, version

    if source.startswith(("git:", "https://", "http://", "ssh://")):
        value = source[4:] if source.startswith("git:") else source
        if "://" in value:
            url = urlsplit(value)
            host, repo = url.hostname, url.path.lstrip("/")
        elif value.startswith("git@"):
            host, repo = value[4:].split(":", 1)
        else:
            host, repo = value.split("/", 1)
        repo = repo.split("@", 1)[0].rstrip("/").removesuffix(".git")
        if (not host or not re.fullmatch(r"[\w.-]+", host) or host in (".", "..")
                or len(repo.split("/")) < 2
                or any(part in ("", ".", "..") for part in unquote(repo).split("/"))
                or "\\" in unquote(repo) or "\x00" in unquote(repo)):
            raise ValueError(f"Invalid git source: {source}")
        identity = host + "/" + repo
        return "git:" + identity, agent_dir / "git" / identity, ""

    local = Path(source).expanduser()
    if not local.is_absolute():
        local = agent_dir / local
    local = local.resolve()
    return "local:" + str(local), local, ""


def sources(settings, agent_dir):
    result = {}
    for entry in settings.get("packages", []):
        source = entry if isinstance(entry, str) else entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Every package must be a source string or an object with a source")
        source = source.strip()
        identity, _, _ = package(source, agent_dir)
        if identity in result:
            raise ValueError(f"Duplicate package identity: {identity}")
        result[identity] = source
    return result


def prepare(desired_path, agent_dir):
    live = agent_dir / "settings.json"
    pending = agent_dir / "settings.json.pre-reconcile"
    desired = read_settings(desired_path)
    sources(desired, agent_dir)  # Validate before writing any state.
    previous = sources(read_settings(pending), agent_dir) if pending.exists() else {}
    if live.exists():
        for identity, source in sources(read_settings(live), agent_dir).items():
            # Pending entries describe the last reconciled source. Live settings
            # may already name an uninstalled ref from the failed attempt.
            previous.setdefault(identity, source)
    # Keep cleanup from an earlier failure even if another settings change arrives.
    write_json(pending, {"packages": list(previous.values())})
    write_json(live, desired)


def needs_install(source, previous, agent_dir):
    identity, installed, version = package(source, agent_dir)
    if identity.startswith("npm:"):
        manifest = installed / "package.json"
        if not manifest.is_file():
            return True
        installed_version = json.loads(manifest.read_text()).get("version")
        if not installed_version:
            return True
        if version:
            # Exact pins need no network when satisfied. Delegate ranges/tags to Pi.
            return not EXACT_VERSION.fullmatch(version) or installed_version != version
        return previous.get(identity, source) != source
    if identity.startswith("git:"):
        return not (installed / ".git").exists() or previous.get(identity) != source
    if not installed.exists():
        raise ValueError(f"Local package does not exist: {installed}")
    return False


def reconcile(agent_dir):
    live = agent_dir / "settings.json"
    pending = agent_dir / "settings.json.pre-reconcile"
    if not pending.is_file():
        raise ValueError("No prepared package state; run prepare first")
    desired = read_settings(live)
    wanted = sources(desired, agent_dir)
    previous = sources(read_settings(pending), agent_dir)
    try:
        # Remove first, and compare identities: a version/ref change is an install,
        # never a removal of the newly installed version of the same package.
        for identity, source in list(previous.items()):
            if identity not in wanted:
                print(f"  - {source}", flush=True)
                subprocess.run(["pi", "remove", source, "--no-approve"], cwd=agent_dir, check=True)
                del previous[identity]
                write_json(pending, {"packages": list(previous.values())})
        for identity, source in wanted.items():
            if needs_install(source, previous, agent_dir):
                print(f"  + {source}", flush=True)
                subprocess.run(["pi", "install", source, "--no-approve"], cwd=agent_dir, check=True)
            previous[identity] = source
            write_json(pending, {"packages": list(previous.values())})
    finally:
        # CLI writes must not flatten object filters or alter canonical defaults.
        # Keep the pending ledger until both reconciliation and restoration succeed.
        write_json(live, desired)
    pending.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "reconcile"))
    parser.add_argument("settings", nargs="?", type=Path)
    args = parser.parse_args()
    agent_dir = Path.home() / ".pi/agent"
    if args.operation == "prepare":
        if args.settings is None:
            parser.error("prepare requires a settings file")
        prepare(args.settings, agent_dir)
    else:
        if args.settings is not None:
            parser.error("reconcile takes no settings file")
        reconcile(agent_dir)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Package reconciliation failed: {error}", file=sys.stderr)
        sys.exit(1)
