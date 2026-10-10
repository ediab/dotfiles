#!/usr/bin/env python3
"""Isolated transaction tests; all paths and command binaries are fixture-local."""
import fcntl
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
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/vps/note-sx-deploy.py"
INDEX = "sha256:e34075087bd06fb68255a056ef93d078b89e8ed355cc350a25c9500d026936f1"
OLD = "sha256:cbe6ec9f4842bb9e053aabe3e44fd9485efc5da02740e99f32a7a013cf4ca2df"
NEW = "sha256:" + "5" * 64
PREVIOUS = "sha256:" + "1" * 64
IMAGE = "ghcr.io/note-sx/server"


class NoteSxDeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="note-sx-helper-test-")
        self.base = Path(self.temp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.state_json = self.base / "fake-docker.json"
        self.docker_log = self.base / "docker-calls.jsonl"
        self.inhibit_calls = self.base / "inhibit-calls.txt"
        self.acl_bad = self.base / "acl-bad-paths.json"
        self.write_docker_state()
        self.acl_bad.write_text("[]")

        self.home = self.base / "home"
        self.diab_home = self.home / "diab"
        self.apps = self.diab_home / "apps"
        self.app = self.apps / "note-sx"
        self.db = self.app / "db"
        self.uploads = self.app / "userfiles"
        self.deployer_home = self.home / "deployer"
        self.make_dir(self.home, 0o755)
        self.make_dir(self.diab_home, 0o751)
        self.make_dir(self.apps, 0o755)
        self.make_dir(self.app, 0o700)
        self.make_dir(self.db, 0o700)
        self.make_dir(self.uploads, 0o700)
        self.make_dir(self.deployer_home, 0o700)
        self.make_dir(self.diab_home / ".cache", 0o700)
        self.make_dir(self.deployer_home / ".cache", 0o700)
        self.make_file(self.app / ".env", b"TEST_SECRET=fixture-only\n", 0o600)
        self.make_file(self.app / ".env.vps", b"TEST_SECRET=fixture-only\n", 0o600)
        self.make_file(self.db / "state.sqlite", b"fixture database bytes\n", 0o600)
        self.make_file(self.uploads / "upload.bin", b"fixture upload bytes\n", 0o600)

        self.etc = self.base / "etc" / "note-sx-deploy"
        self.docker_config = self.etc / "docker"
        self.state_dir = self.base / "var" / "lib" / "note-sx-deploy"
        self.backups = self.base / "var" / "backups" / "note-sx"
        self.docker_root = self.base / "var" / "lib" / "docker"
        for path in (self.etc, self.docker_config, self.state_dir, self.backups, self.docker_root):
            self.make_dir(path, 0o700)
        self.make_file(self.state_dir / "deploy.lock", b"", 0o600)
        self.write_hold_file()

        self.install_fake_tools()
        self.tar = self.bin / "tar"
        self.script(self.tar, f'''#!{sys.executable}\nimport json,os,sys\nif json.load(open({str(self.state_json)!r}))["running"] != "stopped": sys.exit(72)\nos.environ["COPYFILE_DISABLE"]="1"\ntar={shutil.which("tar")!r}\nos.execv(tar, [tar, *sys.argv[1:]])\n''')
        self.helper = self.base / "note-sx-deploy.py"
        self.rewrite_helper(SOURCE.read_text())

    def tearDown(self):
        self.temp.cleanup()

    def make_dir(self, path, mode):
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, mode)

    def make_file(self, path, data, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        os.chmod(path, mode)

    def write_docker_state(self, **overrides):
        state = {
            "running": OLD,
            "repo_digest": INDEX,
            "index_to_platform": {INDEX: OLD},
            "current_manifest_mode": "normal",
            "latest_manifest_mode": "normal",
            "healthy": True,
            "registry": OLD,
            "images": [INDEX, OLD, NEW, PREVIOUS],
            "fail_pull": False,
            "fail_stop": False,
            "fail_up": 0,
            "fail_up_digests": [],
            "unhealthy_digests": [],
            "extra_writer": False,
            "stop_remains_running": False,
            "compose_refs": [],
            "calls": [],
        }
        if self.state_json.exists():
            state.update(json.loads(self.state_json.read_text()))
        state.update(overrides)
        self.state_json.write_text(json.dumps(state))

    def state(self):
        return json.loads(self.state_json.read_text())

    def write_hold_file(self, status="held", reviewed=OLD):
        content = f"status={status}\ncreated_utc=2026-10-10T12:00:00Z\nreason=review-upstream-latest-before-first-update\nbaseline={INDEX}\nreviewed_latest={reviewed}\n"
        if status == "released":
            content += "released_utc=2026-10-10T12:05:00Z\n"
        self.make_file(self.etc / "first-update.hold", content.encode(), 0o600)

    def release_hold_fixture(self):
        self.write_hold_file(status="released")
        self.write_docker_state(registry=NEW)

    def install_fake_tools(self):
        fake_getfacl = f"""#!{sys.executable}
import json,sys
bad=json.load(open({str(self.acl_bad)!r}))
if sys.argv[-1] in bad:
 print('user:deployer:rwx')
else:
 print('user::rwx\\ngroup::r-x\\nother::r-x')
"""
        self.script(self.bin / "getfacl", fake_getfacl)
        fake_docker = f"""#!{sys.executable}
import json,re,sys
state_path={str(self.state_json)!r}
calls_path={str(self.docker_log)!r}
IMAGE={IMAGE!r}
def load(): return json.load(open(state_path))
def save(s): json.dump(s,open(state_path,'w'))
s=load(); a=sys.argv[1:]; s['calls'].append(a); save(s)
if a[:3] == ['manifest','inspect','--verbose']:
 ref=a[3]
 if ref==IMAGE+':latest':
  d=s['registry']; prefix=IMAGE+':latest'
 elif ref.startswith(IMAGE+'@'):
  root=ref.split('@',1)[1]; d=s['index_to_platform'].get(root,root); prefix=IMAGE
 else: sys.exit(21)
 mode=s['latest_manifest_mode'] if ref==IMAGE+':latest' else s['current_manifest_mode']
 def descriptor(d,os_name,arch,media='application/vnd.oci.image.manifest.v1+json'):
  return {{'digest':d,'mediaType':media,'size':1234,'platform':{{'os':os_name,'architecture':arch}}}}
 rows=[
  {{'Ref':prefix+'@'+d,'Descriptor':descriptor(d,'linux','amd64')}},
  {{'Ref':prefix+'@sha256:'+('2'*64),'Descriptor':descriptor('sha256:'+('2'*64),'linux','arm64')}},
  {{'Ref':prefix+'@sha256:'+('3'*64),'Descriptor':descriptor('sha256:'+('3'*64),'unknown','unknown','application/vnd.in-toto+json')}},
 ]
 if mode=='single' and d not in s['index_to_platform']:
  print(json.dumps(rows[0])); sys.exit(0)
 if mode=='single-wrong-architecture':
  print(json.dumps({{'Ref':IMAGE+'@'+d,'Descriptor':descriptor(d,'linux','arm64')}})); sys.exit(0)
 if mode=='single-bad-media':
  print(json.dumps({{'Ref':IMAGE+'@'+d,'Descriptor':descriptor(d,'linux','amd64','application/vnd.oci.image.index.v1+json')}})); sys.exit(0)
 if mode=='single-bad-ref':
  print(json.dumps({{'Ref':IMAGE+':latest@'+d,'Descriptor':descriptor(d,'linux','amd64')}})); sys.exit(0)
 if mode=='single-arbitrary':
  print(json.dumps({{'Ref':IMAGE+'@'+d,'Descriptor':{{'digest':d,'platform':{{'os':'linux','architecture':'amd64'}}}}}})); sys.exit(0)
 if mode=='no-amd64': rows=rows[1:]
 if mode=='duplicate-amd64': rows.append({{'Ref':prefix+'@sha256:'+('6'*64),'Descriptor':descriptor('sha256:'+('6'*64),'linux','amd64')}})
 if mode=='wrong-architecture': rows[0]['Descriptor']['platform']={{'os':'linux','architecture':'arm64'}}
 if mode=='bad-ref': rows[0]['Ref']='unexpected'
 if mode=='bad-media': rows[0]['Descriptor']['mediaType']='application/vnd.oci.image.index.v1+json'
 print(json.dumps(rows)); sys.exit(0)
if a and a[0]=='ps':
 if s['extra_writer'] and any(x.startswith('volume=') for x in a): print('extra-writer')
 sys.exit(0)
if a and a[0]=='pull':
 if s['fail_pull']: sys.exit(1)
 digest=a[1].split('@',1)[1]
 if digest not in s['images']: s['images'].append(digest)
 save(s); sys.exit(0)
if a[:2]==['image','inspect']:
 ref=a[-1]
 if '@' in ref:
  digest=ref.split('@',1)[1]
  if digest not in s['images']: sys.exit(1)
 else:
  if ref!=s['running']: sys.exit(1)
  digest=s['repo_digest']
 print(json.dumps([IMAGE+'@'+digest])); sys.exit(0)
if a and a[0]=='inspect':
 fmt=a[2]; target=a[3]
 if target!='notesx-server': sys.exit(1)
 if fmt=='{{{{.Image}}}}': print(s['running']); sys.exit(0)
 if fmt.startswith('{{{{.State.Status}}}}'):
  status='running' if s['running']!='stopped' else 'exited'
  health='healthy' if s['healthy'] else 'unhealthy'
  print(status if fmt=='{{{{.State.Status}}}}' else status+'|'+health); sys.exit(0)
if a and a[0]=='compose':
 mf=a[a.index('-f')+1]
 text=open(mf).read()
 match=re.search(r'image:\\s*'+re.escape(IMAGE)+r'@(sha256:[0-9a-f]{{64}})',text)
 if not match: sys.exit(30)
 digest=match.group(1)
 if {str(self.etc / 'note-sx.env')!r} not in text or {str(self.db) + ':/notesx/db'!r} not in text or '127.0.0.1:3010:3000' not in text: sys.exit(31)
 action=a[-1]
 s.setdefault('compose_refs',[]).append(digest); save(s)
 if action=='stop':
  if s['fail_stop']:
   s['running']='stopped'; s['healthy']=False; save(s); sys.exit(1)
  if not s['stop_remains_running']:
   s['running']='stopped'; s['healthy']=False
  save(s); sys.exit(0)
 if action=='never': action=a[-4]
 if 'up' in a:
  if digest not in s['images'] or digest in s['fail_up_digests']: sys.exit(1)
  if s['fail_up']>0:
   s['fail_up']-=1; save(s); sys.exit(1)
  s['repo_digest']=digest
  s['running']=s['index_to_platform'].get(digest,digest)
  s['healthy']=s['running'] not in s['unhealthy_digests']
  save(s); sys.exit(0)

sys.exit(40)
"""
        self.script(self.bin / "docker", fake_docker)
        self.script(self.bin / "curl", f"""#!{sys.executable}
import json,sys
s=json.load(open({str(self.state_json)!r}))
sys.exit(0 if s['running']!='stopped' and s['healthy'] else 1)
""")
        self.script(self.bin / "setpriv", """#!/bin/sh
while [ "$#" -gt 0 ]; do
  case "$1" in --reuid=*|--regid=*|--init-groups) shift ;; --) shift; break ;; *) exit 90 ;; esac
done
exec "$@"
""")
        self.script(self.bin / "systemd-inhibit", f"""#!/bin/sh
if [ -e /proc/self/fd/9 ]; then exec 9>&-; fi
printf '%s\\n' "$*" >> {str(self.inhibit_calls)!r}
while [ "$#" -gt 0 ]; do
  case "$1" in --*) shift ;; *) break ;; esac
done
"$@" &
child=$!
wait "$child"
exit $?
""")

    def script(self, path, content):
        path.write_text(textwrap.dedent(content))
        path.chmod(0o755)

    def rewrite_helper(self, source):
        app = str(self.app)
        homes = {
            "/home/diab/apps/note-sx": "@APP@",
            "/home/diab/apps": "@APPS@",
            "/home/diab/.cache/vps-deploy.lock": "@DIABLOCK@",
            "/home/deployer/.cache/vps-deploy.lock": "@DEPLOYERLOCK@",
            "/home/diab": "@DIABHOME@",
            "/home/deployer": "@DEPLOYERHOME@",
            "/home": "@HOME@",
        }
        for old, placeholder in homes.items():
            source = source.replace(old, placeholder)
        source = source.replace("/etc/note-sx-deploy", "@ETC@")
        replacements = {
            'ROOT_UID = 0': f'ROOT_UID = {os.getuid()}',
            'ROOT_GID = 0': f'ROOT_GID = {os.getgid()}',
            'DIAB_UID = 1000': f'DIAB_UID = {os.getuid()}',
            'DIAB_GID = 1000': f'DIAB_GID = {os.getgid()}',
            'DEPLOYER_UID = 1001': f'DEPLOYER_UID = {os.getuid()}',
            'ETC = "@ETC@"': f'ETC = {str(self.etc)!r}',
            'STATE_DIR = "/var/lib/note-sx-deploy"': f'STATE_DIR = {str(self.state_dir)!r}',
            'BACKUP_DIR = "/var/backups/note-sx"': f'BACKUP_DIR = {str(self.backups)!r}',
            'DOCKER_ROOT = "/var/lib/docker"': f'DOCKER_ROOT = {str(self.docker_root)!r}',
            'TAR = "/usr/bin/tar"': f'TAR = {str(self.tar)!r}',
            'DOCKER = "/usr/bin/docker"': f'DOCKER = {str(self.bin / "docker")!r}',
            'CURL = "/usr/bin/curl"': f'CURL = {str(self.bin / "curl")!r}',
            'GETFACL = "/usr/bin/getfacl"': f'GETFACL = {str(self.bin / "getfacl")!r}',
            'SETPRIV = "/usr/bin/setpriv"': f'SETPRIV = {str(self.bin / "setpriv")!r}',
            'PYTHON = "/usr/bin/python3"': f'PYTHON = {sys.executable!r}',
            'SYSTEMD_INHIBIT = "/usr/bin/systemd-inhibit"': f'SYSTEMD_INHIBIT = {str(self.bin / "systemd-inhibit")!r}',
            'LOCK_TIMEOUT = 120': 'LOCK_TIMEOUT = 2.0',
            'HEALTH_TIMEOUT = 150': 'HEALTH_TIMEOUT = 1.2',
            'HEALTH_INTERVAL = 5': 'HEALTH_INTERVAL = 0.003',
            'MIN_FREE_BYTES = 2 * 1024**3': 'MIN_FREE_BYTES = 0',
        }
        for old, new in replacements.items():
            if old not in source:
                raise AssertionError(f"missing replacement token: {old}")
            source = source.replace(old, new, 1)
        pathmap = {
            "@ETC@": str(self.etc),
            "@APP@": app,
            "@APPS@": str(self.apps),
            "@DIABLOCK@": str(self.diab_home / ".cache/vps-deploy.lock"),
            "@DEPLOYERLOCK@": str(self.deployer_home / ".cache/vps-deploy.lock"),
            "@DIABHOME@": str(self.diab_home),
            "@DEPLOYERHOME@": str(self.deployer_home),
            "@HOME@": str(self.home),
        }
        for placeholder, value in pathmap.items():
            source = source.replace(placeholder, value)
        source = source.replace(f'("{self.home}", 0, 0, 0o755)', f'("{self.home}", {os.getuid()}, {os.getgid()}, 0o755)')
        self.helper.write_text(source)
        self.helper.chmod(0o700)
        compile(source, str(self.helper), "exec")

    def run_helper(self, *args, helper=None):
        script = helper or self.helper
        return subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True, timeout=8)

    def seed_state(self, current=OLD, previous=PREVIOUS):
        self.make_file(self.etc / "note-sx.env", b"TEST_SECRET=fixture-only\n", 0o600)
        current_ref = INDEX if current == OLD else current
        previous_ref = None if previous is None else (INDEX if previous == OLD else previous)
        data = f"current={current}\ncurrent_ref={current_ref}\nprevious={previous or 'none'}\nprevious_ref={previous_ref or 'none'}\n"
        self.make_file(self.state_dir / "state", data.encode(), 0o600)
        self.write_docker_state(running=current, repo_digest=current_ref)

    def calls(self):
        return self.state()["calls"]

    def test_cutover_uses_running_digest_and_copies_env_without_output(self):
        verify = self.run_helper("--verify-current")
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn(f"running_repo_digest={INDEX}", verify.stdout)
        self.assertIn(f"running_linux_amd64_digest={OLD}", verify.stdout)
        self.assertIn(f"upstream_linux_amd64_latest_digest={OLD}", verify.stdout)
        self.assertIn("latest_moved=no", verify.stdout)
        self.assertNotIn("fixture-only", verify.stdout + verify.stderr)
        self.assertFalse(any(call[:1] == ["pull"] for call in self.calls()))
        self.assertFalse(self.inhibit_calls.exists(), "read-only verification should not install a shutdown inhibitor")

        cutover = self.run_helper("--cutover-current")
        self.assertEqual(cutover.returncode, 0, cutover.stderr)
        self.assertIn("cutover_image_unchanged=yes", cutover.stdout)
        self.assertIn("latest_was_not_pulled=yes", cutover.stdout)
        self.assertNotIn("fixture-only", cutover.stdout + cutover.stderr)
        self.assertFalse(any(call[:1] == ["pull"] for call in self.calls()))
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual((self.etc / "note-sx.env").read_bytes(), (self.app / ".env").read_bytes())
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious=none\nprevious_ref=none\n")
        self.assertEqual(self.state()["compose_refs"], [INDEX, INDEX])
        self.assertEqual(len(list(self.backups.glob("state-*.tgz"))), 1)
        self.assertTrue(self.inhibit_calls.exists())

    def test_latest_update_pulls_immutable_digest_then_promotes_and_retains_three(self):
        self.seed_state()
        self.release_hold_fixture()
        for index in range(3):
            path = self.backups / f"state-2000010{index}T000000Z-old{index}.tgz"
            self.make_file(path, b"old archive fixture", 0o600)
        old_archive_dir = self.diab_home / "backups/note-sx"
        self.make_dir(old_archive_dir, 0o700)
        old_archive = old_archive_dir / "state-owner.tgz"
        self.make_file(old_archive, b"preserve", 0o600)

        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"latest_linux_amd64={NEW}", result.stdout)
        self.assertEqual(self.state()["running"], NEW)
        self.assertEqual((self.state_dir / "state").read_text(), f"current={NEW}\ncurrent_ref={NEW}\nprevious={OLD}\nprevious_ref={INDEX}\n")
        pull_calls = [call for call in self.calls() if call[:1] == ["pull"]]
        self.assertEqual(pull_calls, [["pull", IMAGE + "@" + NEW]])
        compose_files = [call for call in self.calls() if call[:1] == ["compose"]]
        self.assertTrue(compose_files)
        self.assertTrue(all(call[-1] in ("stop", "never") for call in compose_files))
        self.assertEqual(len(list(self.backups.glob("state-*.tgz"))), 3)
        self.assertEqual(old_archive.read_bytes(), b"preserve")
        self.assertTrue(self.inhibit_calls.exists())

    def test_single_manifest_child_supports_verify_noop_and_exact_reference_rollback(self):
        self.seed_state(previous=None)
        self.release_hold_fixture()
        self.write_docker_state(current_manifest_mode="single", latest_manifest_mode="single")

        updated = self.run_helper()
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(self.state()["running"], NEW)
        self.assertIn(f"healthy digest={NEW} image_ref={NEW}", updated.stdout)

        verified = self.run_helper("--verify-current")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn(f"running_repo_digest={NEW}", verified.stdout)
        self.assertIn(f"running_linux_amd64_digest={NEW}", verified.stdout)

        self.state_json.write_text(json.dumps({**self.state(), "calls": []}))
        noop = self.run_helper()
        self.assertEqual(noop.returncode, 0, noop.stderr)
        self.assertIn("already current", noop.stdout)
        self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))

        self.state_json.write_text(json.dumps({**self.state(), "calls": []}))
        rollback = self.run_helper("--rollback-previous")
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertIn(f"image_ref={INDEX}", rollback.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={NEW}\nprevious_ref={NEW}\n")
        self.assertFalse(any(call[0] == "pull" for call in self.calls()))

    def test_single_manifest_malformed_or_wrong_metadata_fails_closed(self):
        for mode in ("single-wrong-architecture", "single-bad-media", "single-bad-ref", "single-arbitrary"):
            with self.subTest(mode=mode):
                self.seed_state()
                self.release_hold_fixture()
                self.write_docker_state(current_manifest_mode=mode)
                result = self.run_helper()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))

    def test_same_payload_across_index_and_child_preserves_reference_and_previous(self):
        self.seed_state(current=OLD, previous=PREVIOUS)
        self.release_hold_fixture()
        self.write_docker_state(registry=OLD)
        before = (self.state_dir / "state").read_bytes()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.state_dir / "state").read_bytes(), before)
        self.assertEqual(self.state()["running"], OLD)
        self.assertIn("already current", result.stdout)
        self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))
        self.assertEqual(list(self.backups.glob("state-*.tgz")), [])

    def test_pull_failure_leaves_service_running_and_never_stops(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(fail_pull=True)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["running"], OLD)
        self.assertFalse(any(call[0] == "compose" for call in self.calls()))
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={PREVIOUS}\nprevious_ref={PREVIOUS}\n")

    def test_wrong_architecture_current_index_fails_closed(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(current_manifest_mode="wrong-architecture")
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("one linux/amd64 digest", result.stderr)
        self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))

    def test_malformed_latest_manifest_fails_before_pull(self):
        for mode in ("no-amd64", "duplicate-amd64", "bad-ref", "bad-media"):
            with self.subTest(mode=mode):
                self.seed_state()
                self.release_hold_fixture()
                self.write_docker_state(latest_manifest_mode=mode)
                result = self.run_helper()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))

    def test_snapshot_failure_recovers_old_digest_without_rotation(self):
        self.seed_state()
        self.release_hold_fixture()
        tar_fail = self.base / "tar-fail"
        self.script(tar_fail, "#!/bin/sh\nexit 1\n")
        self.rewrite_helper(SOURCE.read_text())
        source = self.helper.read_text().replace(f'TAR = {str(self.tar)!r}', f'TAR = {str(tar_fail)!r}', 1)
        self.helper.write_text(source)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual(list(self.backups.glob("state-*.tgz")), [])
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={PREVIOUS}\nprevious_ref={PREVIOUS}\n")

    def test_cancel_during_stopped_snapshot_recovers_old_image(self):
        self.seed_state()
        self.release_hold_fixture()
        cancel_tar = self.base / "cancel-tar.py"
        self.script(cancel_tar, f'''#!{sys.executable}\nimport os,signal,time\nos.kill(os.getppid(), signal.SIGTERM)\ntime.sleep(5)\n''')
        self.rewrite_helper(SOURCE.read_text())
        source = self.helper.read_text().replace(f'TAR = {str(self.tar)!r}', f'TAR = {str(cancel_tar)!r}', 1)
        self.helper.write_text(source)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interrupted by signal", result.stderr)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertFalse(list(self.backups.glob("state-*.tgz")))
        self.assertFalse(list(self.backups.glob(".note-sx-snapshot-*")))

    def test_outer_signals_keep_both_locks_until_inner_transaction_finishes(self):
        self.seed_state()
        self.release_hold_fixture()
        self.rewrite_helper(SOURCE.read_text())

        started = self.base / "tar-started"
        slow_tar = self.bin / "slow-tar.py"
        self.script(slow_tar, f'''#!{sys.executable}\nimport os,time\nfrom pathlib import Path\nPath({str(started)!r}).touch()\ntime.sleep(3)\nos.environ["COPYFILE_DISABLE"]="1"\ntar={shutil.which("tar")!r}\nos.execv(tar,[tar,*__import__("sys").argv[1:]])\n''')
        source = self.helper.read_text().replace(f'TAR = {str(self.tar)!r}', f'TAR = {str(slow_tar)!r}', 1)

        inhibitor = self.bin / "holding-systemd-inhibit"
        self.script(inhibitor, f'''#!/bin/sh\nwhile [ "$#" -gt 0 ]; do case "$1" in --*) shift ;; *) break ;; esac; done\n"$@" &\nchild=$!\nprintf '%s\\n' "$child" > {str(self.base / "inner.pid")!r}\nwait "$child"\nexit $?\n''')
        source = source.replace(f'SYSTEMD_INHIBIT = {str(self.bin / "systemd-inhibit")!r}', f'SYSTEMD_INHIBIT = {str(inhibitor)!r}', 1)
        self.helper.write_text(source)
        proc = subprocess.Popen([sys.executable, str(self.helper)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 8
        while not started.exists() and time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.02)
        self.assertTrue(started.exists(), "inner transaction did not reach stopped snapshot")

        for caught in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            proc.send_signal(caught)
        self.assertIsNone(proc.poll(), "inhibitor wrapper exited before its transaction child")
        for path in (self.state_dir / "deploy.lock", self.diab_home / ".cache/vps-deploy.lock"):
            fd = os.open(path, os.O_RDWR)
            try:
                with self.assertRaises(BlockingIOError, msg=f"lock released during active inner transaction: {path.name}"):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)

        stdout, stderr = proc.communicate(timeout=12)
        self.assertEqual(proc.returncode, 0, stderr)
        self.assertEqual(self.state()["running"], NEW)
        self.assertEqual(len(list(self.backups.glob("state-*.tgz"))), 1)
        self.assertIn("healthy digest=" + NEW, stdout)

    def test_group_term_keeps_inhibitor_and_both_locks_through_cleanup(self):
        ready = self.base / "locked-ready"
        cleaning = self.base / "cleanup-entered"
        release = self.base / "release-cleanup"
        self.rewrite_helper(SOURCE.read_text())
        source = self.helper.read_text().replace(
            '        wait_lock_holder(legacy)\n        if action == "update":',
            f'        wait_lock_holder(legacy)\n        open({str(ready)!r}, "w").close()\n'
            f'        while not os.path.exists({str(release)!r}): time.sleep(0.01)\n'
            '        if action == "update":',
            1,
        )
        source = source.replace(
            '        if legacy is not None:\n            try:\n                legacy.stdin.close()',
            f'        if legacy is not None:\n            open({str(cleaning)!r}, "w").close()\n'
            f'            while not os.path.exists({str(release)!r}): time.sleep(0.01)\n'
            '            try:\n                legacy.stdin.close()',
            1,
        )
        self.helper.write_text(source)
        proc = subprocess.Popen(
            [sys.executable, str(self.helper)], start_new_session=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 8
            while not ready.exists() and time.monotonic() < deadline and proc.poll() is None:
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "transaction did not acquire both fixture locks")
            os.killpg(proc.pid, signal.SIGTERM)
            deadline = time.monotonic() + 8
            while not cleaning.exists() and time.monotonic() < deadline and proc.poll() is None:
                time.sleep(0.01)
            self.assertTrue(cleaning.exists(), "signal did not reach the transaction child")
            self.assertIsNone(proc.poll(), "inhibitor wrapper exited before lock cleanup")
            for path in (self.state_dir / "deploy.lock", self.diab_home / ".cache/vps-deploy.lock"):
                fd = os.open(path, os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError, msg=f"lock released before cleanup: {path.name}"):
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(fd)
            release.touch()
            stdout, stderr = proc.communicate(timeout=8)
            self.assertEqual(proc.returncode, 1, stdout)
            self.assertIn("interrupted by signal", stderr)
            self.assertFalse(self.calls(), "held update must not reach Docker")
            for path in (self.state_dir / "deploy.lock", self.diab_home / ".cache/vps-deploy.lock"):
                fd = os.open(path, os.O_RDWR)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        finally:
            if proc.poll() is None:
                release.touch()
                try:
                    proc.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.communicate()

    def test_snapshot_preserves_symlink_without_following_target(self):
        self.seed_state()
        self.release_hold_fixture()
        outside = self.base / "private-fixture"
        outside.write_bytes(b"must not enter the snapshot")
        (self.uploads / "link").symlink_to(outside)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        archive_path = next(self.backups.glob("state-*.tgz"))
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember("userfiles/link")
            self.assertTrue(member.issym())
            self.assertIn("private-fixture", member.linkname)
            regular_contents = [archive.extractfile(item).read() for item in archive.getmembers() if item.isfile()]
            self.assertNotIn(outside.read_bytes(), regular_contents)

    def test_external_hardlink_aborts_snapshot_and_recovers(self):
        self.seed_state()
        self.release_hold_fixture()
        outside = self.base / "external-hardlink"
        outside.write_bytes(b"fixture")
        os.link(outside, self.db / "external-link")
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("external hardlink", result.stderr)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual(list(self.backups.glob("state-*.tgz")), [])

    def test_activation_failure_recovers_current_and_keeps_state(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(fail_up=1)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={PREVIOUS}\nprevious_ref={PREVIOUS}\n")

    def test_unhealthy_candidate_rolls_back_without_restoring_data(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(unhealthy_digests=[NEW])
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual((self.db / "state.sqlite").read_bytes(), b"fixture database bytes\n")

    def test_failed_rollback_reports_observed_digest(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(unhealthy_digests=[NEW], fail_up_digests=[INDEX])
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"recovery=failed expected={OLD} image_ref={INDEX} observed_ref={NEW}", result.stderr)
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={PREVIOUS}\nprevious_ref={PREVIOUS}\n")

    def test_state_promotion_failure_recovers_old_and_preserves_metadata(self):
        self.seed_state()
        self.release_hold_fixture()
        before = (self.state_dir / "state").read_bytes()
        source = SOURCE.read_text().replace("os.replace(path, STATE)", "raise OSError('injected promotion failure')", 1)
        patched = self.base / "promotion-fail.py"
        self.rewrite_helper(source)
        shutil.copy2(self.helper, patched)
        result = self.run_helper(helper=patched)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("state promotion failed", result.stderr)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual((self.state_dir / "state").read_bytes(), before)
        self.assertEqual(self.state()["running"], OLD)

    def test_acl_or_state_symlink_fails_before_pull(self):
        self.seed_state()
        self.release_hold_fixture()
        self.acl_bad.write_text(json.dumps([str(self.app)]))
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(call[0] == "pull" for call in self.calls()))
        self.acl_bad.write_text("[]")

        state_file = self.state_dir / "state"
        state_file.unlink()
        target = self.base / "state-target"
        target.write_text(f"current={OLD}\ncurrent_ref={INDEX}\nprevious={PREVIOUS}\nprevious_ref={PREVIOUS}\n")
        state_file.symlink_to(target)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(call[0] == "pull" for call in self.calls()))
        self.assertEqual(target.read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={PREVIOUS}\nprevious_ref={PREVIOUS}\n")

    def test_root_lock_timeout_and_invalid_arguments_do_no_docker_work(self):
        fd = os.open(self.state_dir / "deploy.lock", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = self.run_helper()
        finally:
            os.close(fd)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls())
        result = self.run_helper("--test-root", "/tmp")
        self.assertNotEqual(result.returncode, 0)
        result = self.run_helper("--_inhibited-update")
        self.assertNotEqual(result.returncode, 0)

    def test_legacy_cleanup_lock_timeout_prevents_docker_work(self):
        lock = self.diab_home / ".cache/vps-deploy.lock"
        fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = self.run_helper()
        finally:
            os.close(fd)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("legacy cleanup lock unavailable", result.stderr)
        self.assertFalse(self.calls())

    def test_legacy_lock_symlink_is_rejected_without_following(self):
        lock = self.diab_home / ".cache/vps-deploy.lock"
        target = self.base / "lock-target"
        target.write_bytes(b"unchanged")
        lock.symlink_to(target)
        result = self.run_helper("--hold-legacy-diab")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b"unchanged")

    def test_cutover_rejects_mismatched_existing_environment_copy(self):
        self.make_file(self.etc / "note-sx.env", b"different-fixture-value\n", 0o600)
        result = self.run_helper("--cutover-current")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs from the current app environment", result.stderr)
        self.assertNotIn("different-fixture-value", result.stdout + result.stderr)
        self.assertFalse(any(call[0] == "compose" or call[0] == "pull" for call in self.calls()))
        self.assertEqual(self.state()["running"], OLD)

    def test_pre_cutover_and_post_cutover_hold_are_explicit_and_inert(self):
        before = self.run_helper()
        self.assertEqual(before.returncode, 2, before.stderr)
        self.assertIn("update=held", before.stdout)
        self.assertNotIn("fixture-only", before.stdout + before.stderr)
        self.assertFalse(any(call[0] in ("pull", "compose", "ps") for call in self.calls()))
        self.assertEqual(self.state()["running"], OLD)

        self.seed_state(previous=None)
        self.state_json.write_text(json.dumps({**self.state(), "calls": []}))
        after = self.run_helper()
        self.assertEqual(after.returncode, 2, after.stderr)
        self.assertIn("no pull, stop, snapshot, or activation", after.stdout)
        self.assertFalse(any(call[0] in ("pull", "compose", "ps") for call in self.calls()))
        self.assertEqual(list(self.backups.glob("state-*.tgz")), [])
        self.assertEqual(self.state()["running"], OLD)

    def test_hold_tamper_modes_and_symlink_fail_closed(self):
        hold = self.etc / "first-update.hold"
        original = hold.read_bytes()
        hold.write_text("status=held\ncorrupt\n")
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls())
        hold.write_bytes(original)
        hold.chmod(0o644)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls())
        hold.chmod(0o600)
        hold.unlink()
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls())
        target = self.base / "hold-target"
        target.write_bytes(original)
        hold.symlink_to(target)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls())
        self.assertEqual(target.read_bytes(), original)

    def test_hold_wrong_owner_fails_closed_when_chown_is_available(self):
        self.seed_state()
        hold = self.etc / "first-update.hold"
        uid, gid = hold.stat().st_uid, hold.stat().st_gid
        try:
            os.chown(hold, uid + 1, -1)
        except PermissionError:
            self.skipTest("test process cannot change fixture ownership")
        try:
            result = self.run_helper()
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.calls())
        finally:
            os.chown(hold, uid, gid)

    def test_release_checks_reviewed_digest_then_restores_automatic_update(self):
        self.seed_state(previous=None)
        result = self.run_helper("--release-first-update-hold")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("automatic updates resume", result.stdout)
        self.assertIn("status=released", (self.etc / "first-update.hold").read_text())
        self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))

        self.write_docker_state(registry=NEW, calls=[])
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call for call in self.calls() if call[0] == "pull"], [["pull", IMAGE + "@" + NEW]])
        self.assertEqual(self.state()["running"], NEW)
        self.assertEqual((self.state_dir / "state").read_text(), f"current={NEW}\ncurrent_ref={NEW}\nprevious={OLD}\nprevious_ref={INDEX}\n")

    def test_release_refuses_upstream_digest_changed_since_review(self):
        self.seed_state(previous=None)
        moved = "sha256:" + "4" * 64
        self.write_docker_state(registry=moved)
        result = self.run_helper("--release-first-update-hold")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("keep hold active", result.stderr)
        self.assertIn("status=held", (self.etc / "first-update.hold").read_text())
        self.assertFalse(any(call[0] in ("pull", "compose") for call in self.calls()))

    def test_root_console_rollback_previous_never_restores_data(self):
        self.seed_state(current=NEW, previous=OLD)
        self.release_hold_fixture()
        self.write_docker_state(running=NEW, repo_digest=NEW, registry=NEW, images=[INDEX, OLD, NEW, PREVIOUS])
        before = (self.db / "state.sqlite").read_bytes()
        result = self.run_helper("--rollback-previous")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("data_restore=not_performed", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertEqual((self.state_dir / "state").read_text(), f"current={OLD}\ncurrent_ref={INDEX}\nprevious={NEW}\nprevious_ref={NEW}\n")
        self.assertEqual((self.db / "state.sqlite").read_bytes(), before)
        self.assertFalse(any(call[0] == "pull" for call in self.calls()))

    def test_stop_must_be_confirmed_before_snapshot(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(stop_remains_running=True)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remained active", result.stderr)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertFalse(list(self.backups.glob("state-*.tgz")))

    def test_other_running_container_blocks_snapshot(self):
        self.seed_state()
        self.release_hold_fixture()
        self.write_docker_state(extra_writer=True)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still mounts note-sx state", result.stderr)
        self.assertIn("recovery=healthy", result.stdout)
        self.assertEqual(self.state()["running"], OLD)
        self.assertFalse(list(self.backups.glob("state-*.tgz")))

    def test_cutover_refuses_changed_running_digest(self):
        self.write_docker_state(running=NEW, repo_digest=NEW, images=[INDEX, OLD, NEW, PREVIOUS])
        result = self.run_helper("--cutover-current")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline changed", result.stderr)
        self.assertFalse(any(call[0] == "pull" for call in self.calls()))
        self.assertFalse(any(call[0] == "compose" for call in self.calls()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
