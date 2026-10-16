"""Regression tests for the protected two-UID monitoring profile."""
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core
import job_watchdog
import monitor_status
import native_scanner
import scanner
import system_runtime


class RootConfigAndLockTests(unittest.TestCase):
    def test_root_config_allows_read_only_group_without_weakening_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{}')
            path.chmod(0o640)
            with self.assertRaises(core.MonitorError):
                core.read_private_json(path)
            info = SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_nlink=1, st_size=2)
            with patch.object(core, "SYSTEM_CONFIGS", {path}), patch.object(core, "root_ancestors") as ancestors:
                with patch("core.os.fstat", return_value=info):
                    self.assertEqual(core.read_monitor_config(path), {})
                ancestors.assert_called_once_with(path)
                for changes in ({"st_uid": 123}, {"st_nlink": 2}, {"st_mode": stat.S_IFREG | 0o660},
                                {"st_mode": stat.S_IFREG | 0o644}):
                    bad = SimpleNamespace(**{**vars(info), **changes})
                    with patch("core.os.fstat", return_value=bad), self.assertRaises(core.MonitorError):
                        core.read_monitor_config(path)

    def test_root_config_rejects_symlink_and_untrusted_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.symlink_to(Path(tmp) / "elsewhere")
            with patch.object(core, "SYSTEM_CONFIGS", {path}), patch.object(core, "root_ancestors"):
                with self.assertRaises(core.MonitorError):
                    core.read_monitor_config(path)
            with patch.object(core, "SYSTEM_CONFIGS", {path}), patch.object(
                    core, "root_ancestors", side_effect=core.MonitorError("untrusted ancestor")):
                with self.assertRaisesRegex(core.MonitorError, "ancestor"):
                    core.read_monitor_config(path)

    def test_shared_lock_never_chmods_or_creates_it_and_still_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.lock"
            path.touch(mode=0o660)
            info = SimpleNamespace(st_mode=stat.S_IFREG | 0o660, st_uid=0, st_nlink=1)
            with patch.object(core, "SHARED_LOCK", path), patch.object(core, "root_ancestors"), \
                 patch("core.os.fstat", return_value=info), patch("core.os.chmod") as chmod:
                with core.locked(path):
                    with self.assertRaises(BlockingIOError):
                        with core.locked(path):
                            self.fail("shared lock reacquired")
                chmod.assert_not_called()
            with patch.object(core, "SHARED_LOCK", path), patch.object(core, "root_ancestors"), \
                 patch("core.os.fstat", return_value=SimpleNamespace(**{**vars(info), "st_uid": 123})):
                with self.assertRaisesRegex(core.MonitorError, "untrusted shared"):
                    with core.locked(path):
                        self.fail("foreign-owned lock accepted")


class SystemProfileTests(unittest.TestCase):
    def test_system_native_pins_paths_lock_and_database_writer(self):
        raw = json.loads((ROOT / "examples/native-system.json").read_text())
        with patch("native_scanner.pwd.getpwnam", return_value=SimpleNamespace(pw_uid=1234)):
            value = native_scanner.validate_config(raw)
            self.assertEqual(value["trivy_db_owner"], 1234)
            self.assertEqual(value["state_dir"], core.NATIVE_STATE)
            self.assertEqual(value["lock_file"], core.SHARED_LOCK)
            self.assertEqual(value["unit_scope"], "system")
            raw["trivy_cache_dir"] = "/tmp/agent-cache"
            with self.assertRaisesRegex(core.MonitorError, "path-config-refused"):
                native_scanner.validate_config(raw)
        with patch("native_scanner.pwd.getpwnam", return_value=SimpleNamespace(pw_uid=0)):
            with self.assertRaisesRegex(core.MonitorError, "owner-refused"):
                native_scanner.validate_config(json.loads((ROOT / "examples/native-system.json").read_text()))
        with patch("native_scanner.pwd.getpwnam", side_effect=KeyError):
            with self.assertRaisesRegex(core.MonitorError, "owner-unavailable"):
                native_scanner.validate_config(json.loads((ROOT / "examples/native-system.json").read_text()))

    def test_system_image_pins_state_transport_and_five_gib_floor(self):
        raw = json.loads((ROOT / "examples/image-system.json").read_text())
        value = scanner.validate_config(raw)
        self.assertEqual(value["state_dir"], core.IMAGE_STATE)
        self.assertEqual(value["lock_file"], core.SHARED_LOCK)
        for change in ({"state_dir": "/tmp/state"}, {"email_transport_root": "/home/diab/Dev/xbot"},
                       {"min_free_bytes": 4*scanner.GIB}):
            with self.subTest(change=change), self.assertRaisesRegex(core.MonitorError, "refused"):
                scanner.validate_config({**raw, **change})

    def test_legacy_metadata_owner_is_explicit_and_target_scoped(self):
        owners = {"diab": 1000, "xbot-app": 990, "morning-brief-app": 988, "el-machine-app": 986}
        with patch("native_scanner.pwd.getpwnam", side_effect=lambda name: SimpleNamespace(pw_uid=owners[name])):
            targets = {t.application:t for t in native_scanner.default_targets()}
        self.assertEqual(targets["houses"].owner, 1000)
        self.assertEqual(targets["el-machine"].additional_metadata_owners, frozenset({1000}))
        for app in ("xbot", "morning-brief", "houses"):
            self.assertFalse(targets[app].additional_metadata_owners)

    def test_unknown_profile_refuses(self):
        for value in (True, "auto", [], {}):
            with self.subTest(value=value), self.assertRaises(core.MonitorError):
                system_runtime.system_profile({"profile":value})


class BrokerClientTests(unittest.TestCase):
    def test_only_fixed_houses_user_query_uses_broker(self):
        run = Mock(return_value="normal system result")
        query = Mock(return_value={"checked_at":time.time(), "verified":True,
                                   "working_directory":system_runtime.HOUSES_DIRECTORY})
        invoke = system_runtime.system_unit_runner(run, query)
        self.assertEqual(invoke(system_runtime.HOUSES_QUERY).stdout, system_runtime.HOUSES_DIRECTORY)
        query.assert_called_once_with("houses-binding")
        self.assertEqual(invoke(["/usr/bin/systemctl", "show", "tfl.service"]), "normal system result")
        with self.assertRaisesRegex(core.MonitorError, "query-refused"):
            invoke(["/usr/bin/systemctl", "--user", "start", "anything.service"])

    def test_stale_false_or_wrong_houses_response_refuses(self):
        good = {"checked_at":time.time(), "verified":True, "working_directory":system_runtime.HOUSES_DIRECTORY}
        for change in ({"checked_at":time.time()-60}, {"verified":False}, {"working_directory":"/tmp/other"}):
            invoke = system_runtime.system_unit_runner(Mock(), Mock(return_value={**good, **change}))
            with self.subTest(change=change), self.assertRaises(core.MonitorError):
                invoke(system_runtime.HOUSES_QUERY)

    def test_status_client_checks_root_peer_and_schema(self):
        def client(uid, payload):
            connection = Mock()
            connection.__enter__ = Mock(return_value=connection)
            connection.__exit__ = Mock(return_value=False)
            connection.getsockopt.return_value = struct.pack("3i", 1, uid, 0)
            connection.recv.return_value = payload
            return connection
        info = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=0)
        for uid, body, error in ((0,b'{"schema_version":1,"operation":"status"}\n',False),
                                 (1000,b'{}\n',True),(0,b'{"schema_version":1,"operation":"read-config"}\n',True)):
            with patch("system_runtime.root_ancestors"), patch.object(Path,"lstat",return_value=info), \
                 patch("system_runtime.socket.SO_PEERCRED", 17, create=True), \
                 patch("system_runtime.socket.socket",return_value=client(uid, body)):
                if error:
                    with self.assertRaises(core.MonitorError):system_runtime.query_status("status")
                else:
                    self.assertEqual(system_runtime.query_status("status")["schema_version"],1)
        with self.assertRaisesRegex(core.MonitorError,"operation-refused"):
            system_runtime.query_status("read-config")

    def test_image_watchdog_fails_closed_but_tolerates_second_rollover(self):
        good={"checked_at":101,"image":{"completed_at":99,"status":"findings"},
              "units":{"vps-image-scan.timer":{"ActiveState":"active"},
                       "vps-image-scan.service":{"Result":"success","ExecMainStatus":"0"}}}
        with patch("job_watchdog.query_status",return_value=good):
            self.assertEqual(job_watchdog.inspect_system_image_job(Path('/unused'),now=100),[])
        with patch("job_watchdog.query_status",return_value={**good,"image":{"unavailable":True}}):
            self.assertIn("scanner:untrusted-heartbeat",job_watchdog.inspect_system_image_job(Path('/unused'),now=100))
        with patch("job_watchdog.query_status",return_value={**good,"units":{}}):
            self.assertIn("scanner:failed-service",job_watchdog.inspect_system_image_job(Path('/unused'),now=100))


class BrokerServerTests(unittest.TestCase):
    def setUp(self):
        # Scratch state is same-user owned; only its root-parent namespace is mocked.
        check = patch('monitor_status.root_ancestors')
        check.start()
        self.addCleanup(check.stop)

    def report(self, root):
        scan_id='20261018T130001Z-1234abcd'
        completed=1792328402
        report={"scan_id":scan_id,"completed_at":"2026-10-18T13:00:02+00:00","status":"clean",
                "findings":[],"errors":[],"coverage_status":"complete",
                "trivy_database_updated_at":"2026-10-18T01:00:00+00:00",
                "targets":[{"application":app,"coverage_complete":True} for app in sorted(monitor_status.APPLICATIONS)],
                "private_contents":"PRIVATE_APP_CONTENT"}
        name='native-scan-'+scan_id+'.json'
        core.atomic_json(root/'native-run.json',{"scan_id":scan_id,"completed_at":completed,"status":"clean","report":name})
        core.atomic_json(root/'reports'/name,report)
        return report, name

    def test_sanitized_report_contains_only_acceptance_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.report(root)
            with patch('monitor_status.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid())):
                value=monitor_status.scan_metadata(root,'test',True)
            self.assertEqual(len(value['targets']),5)
            self.assertEqual(value['coverage_status'],'complete')
            self.assertNotIn('PRIVATE_APP_CONTENT',json.dumps(value))

    def test_reports_directory_symlink_refuses_and_partial_targets_are_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,name=self.report(root)
            with patch('monitor_status.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid())):
                core.atomic_json(root/'reports'/name,{**report,'targets':report['targets'][:2]})
                self.assertEqual(monitor_status.scan_metadata(root,'test',True)['coverage_status'],'incomplete')
                (root/'reports').rename(root/'saved')
                (root/'reports').symlink_to(root/'saved',target_is_directory=True)
                with self.assertRaisesRegex(core.MonitorError,'directory-untrusted'):
                    monitor_status.scan_metadata(root,'test',True)

    def test_report_path_traversal_and_heartbeat_mismatch_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,name=self.report(root)
            with patch('monitor_status.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid())):
                heartbeat=json.loads((root/'native-run.json').read_text())
                core.atomic_json(root/'native-run.json',{**heartbeat,'report':'../private.json'})
                with self.assertRaisesRegex(core.MonitorError,'path-refused'):
                    monitor_status.scan_metadata(root,'test',True)
                core.atomic_json(root/'native-run.json',heartbeat)
                core.atomic_json(root/'reports'/name,{**report,'scan_id':'different'})
                with self.assertRaisesRegex(core.MonitorError,'mismatch'):
                    monitor_status.scan_metadata(root,'test',True)

    def test_record_symlink_and_foreign_owner_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'data.json';core.atomic_json(path,{})
            with self.assertRaisesRegex(core.MonitorError,'untrusted'):
                monitor_status._record(path,os.getuid()+1)
            link=root/'link.json';link.symlink_to(path)
            with self.assertRaises(OSError):monitor_status._record(link,os.getuid())

    def test_fixed_houses_query_drops_credentials_and_never_echoes_unexpected_output(self):
        with patch('monitor_status.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=1000)), \
             patch('monitor_status.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='PRIVATE_APP_CONTENT',stderr='')) as run:
            value=monitor_status.houses_binding()
            self.assertFalse(value['verified'])
            self.assertNotIn('PRIVATE_APP_CONTENT',json.dumps(value))
            self.assertEqual(run.call_args.kwargs['user'],'diab')
            self.assertEqual(run.call_args.kwargs['extra_groups'],[])
            self.assertEqual(run.call_args.args[0][-1],'houses-health.service')

    def test_unknown_root_operation_never_runs_a_command(self):
        with patch('monitor_status.subprocess.run') as run, self.assertRaises(core.MonitorError):
            monitor_status.reply('read-config')
        run.assert_not_called()


class TransportBoundaryTests(unittest.TestCase):
    def test_both_senders_refuse_writable_ancestors_before_import(self):
        before=list(sys.path)
        for sender in (scanner._email_sender,native_scanner._email_sender):
            with patch('core.root_ancestors',side_effect=core.MonitorError('untrusted ancestor')):
                with self.assertRaisesRegex(core.MonitorError,'ancestor'):
                    sender({'email_transport_root':'/home/diab/mutable'})
        self.assertEqual(sys.path,before)

    def test_transitive_modules_and_bytecode_cannot_be_user_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('summary_config.py','scrape_timeline.py','fastmail_jmap.py','util.py','.env.local'):
                (root/name).write_text('')
                (root/name).chmod(0o640)
            original=Path.lstat
            def as_root(path,*args,**kwargs):
                value=original(path,*args,**kwargs)
                return SimpleNamespace(st_uid=0,st_mode=value.st_mode,st_nlink=value.st_nlink,st_size=value.st_size)
            with patch('core.root_ancestors'), patch.object(Path,'lstat',as_root):
                core.trusted_mail_transport(root)
                (root/'util.py').chmod(0o660)
                with self.assertRaisesRegex(core.MonitorError,'tree-untrusted'):
                    core.trusted_mail_transport(root)
                (root/'util.py').chmod(0o640)
                cache=root/'__pycache__';cache.mkdir(mode=0o750)
                (cache/'util.cpython-312.pyc').write_bytes(b'not executable')
                (cache/'util.cpython-312.pyc').chmod(0o666)
                with self.assertRaisesRegex(core.MonitorError,'tree-untrusted'):
                    core.trusted_mail_transport(root)

    def test_broker_outage_is_an_alertable_deduplicated_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            config={'state_dir':Path(tmp),'profile':'system','max_heartbeat_age_seconds':32*3600}
            send=Mock(return_value=True)
            with patch('job_watchdog.query_status',side_effect=core.MonitorError('offline')):
                self.assertEqual(job_watchdog.run_watchdog(config,now=100,send=send),1)
                self.assertEqual(job_watchdog.run_watchdog(config,now=101,send=send),1)
            send.assert_called_once()
            self.assertIn('status-broker-unavailable',send.call_args.args[0])


class DatabaseAndUnitTests(unittest.TestCase):
    def test_database_acl_is_read_only_and_unprivileged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'db').mkdir(mode=0o700);(root/'db/metadata.json').write_text('{}');(root/'db/trivy.db').touch()
            (root/'db/metadata.json').chmod(0o600);(root/'db/trivy.db').chmod(0o600)
            run=Mock(return_value=subprocess.CompletedProcess([],0))
            with patch('scanner.SHARED_TRIVY_CACHE',root), patch('scanner.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=1234)):
                scanner._share_database(run)
            self.assertEqual(run.call_count,4)
            for call in run.call_args_list:
                command=call.args[0]
                self.assertEqual(command[:2],['/usr/bin/setfacl','-m'])
                self.assertNotIn('w',command[2])
                self.assertNotIn('sudo',command)

    def test_database_owner_or_link_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'db').mkdir(mode=0o700);(root/'db/metadata.json').symlink_to(root/'private')
            run=Mock(return_value=subprocess.CompletedProcess([],0))
            with patch('scanner.SHARED_TRIVY_CACHE',root), patch('scanner.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=1234)):
                with self.assertRaises(core.MonitorError):scanner._share_database(run)
            run.assert_not_called()

    def test_only_image_scan_gets_docker_and_no_unit_uses_home_code(self):
        directory=ROOT/'systemd-system'
        for path in directory.glob('*.service'):
            text=path.read_text()
            self.assertNotIn('/home/diab/ops/',text)
            self.assertNotIn('/home/diab/Dev/',text)
            self.assertIn('NoNewPrivileges=yes',text)
            self.assertIn('/usr/bin/python3 -E -s -B',text)
            if path.name=='vps-image-scan.service':
                self.assertIn('SupplementaryGroups=docker ',text)
            else:
                self.assertNotIn('SupplementaryGroups=docker',text)
                if 'watchdog' in path.name:self.assertIn('User=vps-native-scan',text)


if __name__=='__main__':unittest.main()
