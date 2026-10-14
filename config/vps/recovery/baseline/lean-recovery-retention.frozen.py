#!/usr/bin/env python3
"""Keep one receipt-proved recovery point; remove owner-approved obsolete copies."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import uuid

RCLONE = '/home/diab/.config/vps-backups/bin/rclone'
CONFIG = '/home/diab/.config/vps-backups/rclone.conf'
BASE = Path('/home/diab/ops/r2-recovery/receipts')
LOCK = Path('/home/diab/ops/r2-rollout-live.lock')
OWNER = 'lean-recovery-retention'
STAMP = re.compile(r'^20\d{6}T\d{6}(?:\d+)?Z[-.]')
START = time.monotonic()

def command(*args):
    remaining = 480 - (time.monotonic() - START)
    if remaining <= 0:
        raise RuntimeError('retention deadline')
    result = subprocess.run([RCLONE, *args, '--config', CONFIG, '--timeout', '20s',
                             '--retries', '1', '--low-level-retries', '1'],
                            capture_output=True, timeout=min(remaining, 180))
    if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
        raise RuntimeError('bounded rclone operation refused')
    return result.stdout

def document(path):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or st.st_size > 262144:
        raise RuntimeError('unsafe receipt')
    return json.loads(path.read_bytes())

def latest(root, pattern):
    paths = list(root.glob(pattern))
    if not paths or len(paths) > 10000:
        raise RuntimeError('receipt inventory')
    return document(max(paths, key=lambda p: p.stat().st_mtime_ns))

def protected_points():
    keep = {}
    specs = [('note-sx', 'note-sx-state-*.json'),
             ('cratch', 'cratch-neon-state-*-complete.json'),
             ('fousekis', 'fousekis-state-*.json'), ('redact', 'redact-state-*.json')]
    for app, pattern in specs:
        d = latest(BASE, pattern)
        if app == 'note-sx':
            if not (d.get('readback') == 'exact-set-and-sha256-pass'
                    and d.get('restore') == 'pass' and d.get('database_check') == 'pass'
                    and d.get('consumer', {}).get('recovered_html') == 'pass'):
                raise RuntimeError('note-sx proof missing')
            prefix, count = d['remote_prefix'], d['readback_file_count']
        else:
            proof = d.get('proof', {})
            if proof.get('fresh_exact_set_readback') is not True:
                raise RuntimeError('app readback proof missing')
            if app == 'cratch' and proof.get('schema_row_sequence_closure') is not True:
                raise RuntimeError('database replay proof missing')
            prefix = d['r2_prefix']
            count = d.get('object_count', 3)
        family = 'r2crypt:' + app + '/state'
        child = prefix.removeprefix(family + '/')
        if not prefix.startswith(family + '/') or '/' in child or not STAMP.match(child):
            raise RuntimeError('receipt namespace binding')
        rows = json.loads(command('lsjson', prefix, '--files-only'))
        if len(rows) != count or any(x.get('Size', -1) < 0 for x in rows):
            raise RuntimeError('protected remote set missing')
        keep[family] = (child, True)
    root = Path('/home/diab/apps/morning-brief/data/state-backup-receipts')
    complete = latest(root, '*-complete.json')
    if complete.get('verified') is not True:
        raise RuntimeError('morning complete proof missing')
    for key, family, remote_key, is_dir in [
        ('metadata_receipt', 'r2crypt:morning-brief/state', 'remote_prefix', True),
        ('config_receipt', 'r2crypt:morning-brief/config', 'remote_object', False)]:
        name = complete[key]
        if Path(name).name != name:
            raise RuntimeError('receipt link escape')
        d = document(root / name)
        remote = d[remote_key]
        child = remote.removeprefix(family + '/')
        if not remote.startswith(family + '/') or '/' in child or not STAMP.match(child):
            raise RuntimeError('morning namespace binding')
        result = json.loads(command('size', remote, '--json'))
        if result.get('count', 0) < 1 or result.get('bytes', 0) < 1:
            raise RuntimeError('protected morning point missing')
        keep[family] = (child, is_dir)
    return keep

def plan(keep, retire_legacy):
    deletes = []
    for family, (protected, is_dir) in keep.items():
        rows = json.loads(command('lsjson', family, '--dirs-only' if is_dir else '--files-only'))
        for row in rows:
            name = row['Path'].rstrip('/')
            # Ignore newer/in-progress writes. Never race a producer lacking this lock.
            if '/' not in name and STAMP.match(name) and name < protected:
                deletes.append((family + '/' + name, is_dir))
    # Explicit owner-approved retired backup families; unique archives are excluded.
    for prefix in (['r2crypt:tfl', 'r2crypt:el-machine/captures',
                   'r2crypt:cratch/rollback-images', 'r2crypt:houses/pilot',
                   'r2crypt:redact-pdf', 'r2crypt:verification', 'r2crypt:guard-probe']
                   if retire_legacy else []):
        measured = json.loads(command('size', prefix, '--json'))
        if measured.get('count', 0) > 0:
            deletes.append((prefix, True))
    return deletes

def local_duplicates():
    # Current app data is never under these recovery-only roots.
    note = latest(BASE, 'note-sx-state-*.json')
    houses = latest(BASE, 'houses-currentdb-*.json')
    roots = [(Path('/var/backups/note-sx/current-coolify-captures'), note['capture_id']),
             (Path('/home/diab/ops/r2-recovery/points/houses'), houses['point_id'])]
    import shutil
    for root, protected in roots:
        if not root.exists():
            root.mkdir(parents=True, mode=0o700)
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError('unsafe local recovery root')
        for child in root.iterdir():
            if child.is_symlink() or not STAMP.match(child.name) or child.name > protected:
                continue
            if child.is_dir():
                shutil.rmtree(child)

def observe_cron():
    cfg = json.loads(Path('/home/diab/.config/vps-backups/monitor-recovery.json').read_bytes())
    row = next(r for r in cfg if r.get('name') == 'morning-brief')
    marker = row.get('entry_marker')
    if not isinstance(marker, str) or not 5 <= len(marker) <= 200 or '\n' in marker:
        raise RuntimeError('invalid cron marker')
    result = subprocess.run(['/usr/bin/crontab', '-u', 'diab', '-l'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode or len(result.stdout) > 65536:
        raise RuntimeError('cron observation refused')
    present = any(marker in line and not line.lstrip().startswith('#')
                  for line in result.stdout.splitlines())
    parent = Path('/var/lib/vps-recovery')
    try:
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)  # Override the recovery service's private umask for metadata only.
    except FileExistsError:
        pass
    st = parent.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        raise RuntimeError('untrusted cron status root')
    temp = parent / ('.cron-observation-' + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    os.fchmod(fd, 0o644)  # Contains only a timestamp and a schedule-presence boolean.
    with os.fdopen(fd, 'w') as f:
        json.dump({'observed_at': time.time(), 'morning_backup_present': present}, f)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, parent / 'cron-observation.json')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--retire-legacy', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0 or any(k.startswith('RCLONE_') for k in os.environ):
        raise RuntimeError('trusted root invocation required')
    if command('version').splitlines()[0] != b'rclone v1.75.2':
        raise RuntimeError('client version mismatch')
    LOCK.mkdir(mode=0o700)  # Existing/ambiguous lock always refuses.
    owner = LOCK / 'owner'
    fd = os.open(owner, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(OWNER + '\n'); f.flush(); os.fsync(f.fileno())
    try:
        keep = protected_points()
        targets = plan(keep, args.retire_legacy)
        print(json.dumps({'protected_points': len(keep), 'obsolete_targets': len(targets), 'apply': args.apply}))
        if args.apply:
            for remote, is_dir in targets:
                command('purge' if is_dir else 'deletefile', remote)
            local_duplicates()
            # Re-check preserved remote points after cleanup, not merely command exit codes.
            protected_points()
            observe_cron()
            status = BASE / 'lean-retention-complete.json'
            temporary = BASE / ('.lean-retention-' + uuid.uuid4().hex)
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump({'completed': time.time(), 'protected_points': len(keep),
                           'latest_verified_points_preserved': True}, f)
                f.flush(); os.fsync(f.fileno())
            os.replace(temporary, status)
            print('retention=complete latest_verified_points_preserved')
    finally:
        st = owner.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or owner.read_text().strip() != OWNER
                or sorted(p.name for p in LOCK.iterdir()) != ['owner']):
            raise RuntimeError('lock ownership changed; retained')
        owner.unlink(); LOCK.rmdir()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('retention=refused class=' + type(e).__name__)
        raise SystemExit(1)
