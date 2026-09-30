#!/usr/bin/env bash
# Apply explicitly selected configuration only. Preview by default; never manage software.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import uuid

root = Path(sys.argv[1])
home = Path.home()
source_root = root / 'home'
live_root = home / '.pi/agent'
configs = ('settings.json', 'web-search.json', 'subagents.json', 'open-tui.json', 'pi-btw.json')
groups = ('agent-content', 'configs', 'agents', 'extensions', 'themes')
parser = argparse.ArgumentParser(description='Preview/apply selected repo configuration; no installs, Git, or remote operations.', allow_abbrev=False)
parser.add_argument('--file', action='append', default=[], help='Config basename, or agents/, extensions/, themes/ relative file')
parser.add_argument('--group', action='append', choices=groups, default=[])
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--yes', action='store_true', help='Apply the reviewed scope (default is preview)')
mode.add_argument('--dry-run', action='store_true', help='Explicit preview')
parser.add_argument('--include-packages', action='store_true', help='Explicitly authorize changing settings package declarations; Pi may install them later')
args = parser.parse_args(sys.argv[2:])
if not args.file and not args.group:
    parser.error('Select at least one --file or --group; there is no implicit all-files apply')


def safe_destination(path):
    current = path
    while current != home:
        if current.is_symlink():
            raise ValueError(f'Refusing symlink destination/parent: {current}')
        if current == path:
            if current.exists() and not current.is_file():
                raise ValueError(f'Destination is not a regular file: {current}')
        elif current.exists() and not current.is_dir():
            raise ValueError(f'Destination parent is not a directory: {current}')
        if current.parent == current:
            raise ValueError(f'Destination escapes HOME: {path}')
        current = current.parent


def reject_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')


def read_object(path):
    value = json.loads(path.read_text(), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return value


try:
    selected = set(args.file)
    for group in args.group:
        if group == 'configs':
            selected.update(configs)
        elif group != 'agent-content':
            folder = source_root / group
            if folder.is_symlink():
                raise ValueError(f'Refusing symlink source group: {folder}')
            if folder.exists():
                selected.update(p.relative_to(source_root).as_posix() for p in folder.rglob('*') if p.is_file())
    if args.include_packages and 'settings.json' not in selected:
        parser.error('--include-packages requires selecting settings.json')

    plans = []
    for relative in sorted(selected):
        rel = PurePosixPath(relative)
        if rel.is_absolute() or '..' in rel.parts or relative != rel.as_posix():
            raise ValueError(f'Invalid source path: {relative}')
        if relative not in configs and not (len(rel.parts) >= 2 and rel.parts[0] in ('agents', 'extensions', 'themes')):
            raise ValueError(f'Not a configuration target: {relative}')
        if rel.parts[0] == 'agents' and (len(rel.parts) != 2 or rel.suffix != '.md'):
            raise ValueError(f'Not an agent profile: {relative}')
        source = source_root / relative
        current = source
        while current != source_root:
            if current.is_symlink():
                raise ValueError(f'Refusing symlink source: {current}')
            current = current.parent
        if not source.is_file():
            raise ValueError(f'Missing source: {source}')
        target = live_root / relative
        safe_destination(target)
        old = target.read_bytes() if target.exists() else None
        content = source.read_bytes()
        if source.suffix == '.json':
            wanted = read_object(source)
            previous = read_object(target) if old is not None else {}
            if relative == 'settings.json':
                # Runtime IDs, host-specific paths/proxy, and package declarations
                # are not portable preference changes. Never copy another host's IDs.
                for key in ('deviceId', 'lastChangelogVersion', 'sessionDir', 'httpProxy'):
                    wanted.pop(key, None)
                    if key in previous:
                        wanted[key] = previous[key]
                if wanted.get('packages') != previous.get('packages'):
                    print('settings.json: package declarations differ; ' +
                          ('explicitly included (Pi may install them at startup)' if args.include_packages else 'preserving live declarations; use --include-packages only after approval'))
                if not args.include_packages:
                    wanted.pop('packages', None)
                    if 'packages' in previous:
                        wanted['packages'] = previous['packages']
                elif 'packages' in wanted and not isinstance(wanted['packages'], list):
                    raise ValueError('settings.json packages must be an array')
                content = (json.dumps(wanted, indent=2) + '\n').encode()
            changes = sorted(k for k in set(wanted) | set(previous)
                             if k not in wanted or k not in previous or
                             json.dumps(wanted[k], sort_keys=True) != json.dumps(previous[k], sort_keys=True))
            print(f'{relative}: changed keys: {", ".join(changes) or "none (formatting only)"}')
        print(f'{"KEEP" if content == old else "COPY"} {relative} -> {target}')
        plans.append((target, content, old))

    agent_content = 'agent-content' in args.group
    if agent_content:
        print('Agent-content scope: ALL managed skills and installed-client instructions; see the full helper plan below.', flush=True)
        subprocess.run(['bash', str(root / 'lint-agent-content.sh')], check=True)
        subprocess.run(['bash', str(root / 'sync-agent-content.sh'), '--dry-run'], check=True)
    if not args.yes:
        print('Preview only. Repeat the same scope with --yes to apply.')
        sys.exit(0)

    # Recheck all destinations before writes; an app may have changed settings
    # while the helper was preflighting. Do not overwrite newly observed edits.
    for target, content, old in plans:
        safe_destination(target)
        if (target.read_bytes() if target.exists() else None) != old:
            raise ValueError(f'Live file changed during preview: {target}; compare again')
    if agent_content:
        subprocess.run(['bash', str(root / 'sync-agent-content.sh'), '--yes'], check=True)

    backup_root = home / '.local/state/pi-dotfiles/backups/apply' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    os.umask(0o077)
    for target, content, old in plans:
        if content == old:
            continue
        safe_destination(target)
        if (target.read_bytes() if target.exists() else None) != old:
            raise ValueError(f'Live file changed before apply: {target}; compare again')
        permissions = stat.S_IMODE(target.stat().st_mode) if old is not None else 0o600
        if old is not None:
            backup = backup_root / target.relative_to(live_root)
            safe_destination(backup)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(old)
            print(f'BACKUP {target} -> {backup}')
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.dotfiles-', delete=False) as stream:
                tmp = Path(stream.name)
                os.fchmod(stream.fileno(), permissions)
                stream.write(content)
            os.replace(tmp, target)
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()
        print(f'APPLIED {target}')
except (OSError, ValueError, subprocess.CalledProcessError) as error:
    print(f'ERROR: {error}', file=sys.stderr)
    sys.exit(1)
PY
