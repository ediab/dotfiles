import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import MonitorError, atomic_json, deliver_transition, locked, read_private_json
from healthcheck_wrapper import component_timeout, ping, run_wrapped, validate_ping_url
from job_watchdog import inspect_scan_job, run_watchdog
from scanner import GIB, _check_guards, run_scan, validate_config


class CoreTests(unittest.TestCase):
    def test_notification_only_advances_after_confirmed_delivery_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "notification.json"
            with self.assertRaises(MonitorError):
                deliver_transition(state, "fingerprint-1", lambda _body: False,
                                   "summary", event="failure", now=10)
            self.assertFalse(state.exists())
            sent = []
            self.assertTrue(deliver_transition(state, "fingerprint-1", lambda body: sent.append(body) or True,
                                               "summary", event="failure", now=11))
            self.assertEqual(len(sent), 1)
            self.assertFalse(deliver_transition(state, "fingerprint-1", lambda _body: True,
                                                "summary", event="failure", now=12))
            self.assertEqual(json.loads(state.read_text())["sent_at"], 11)

    def test_quiet_recoveries_advance_and_deduplicate_without_email(self):
        for event in ("recovered", "findings_cleared"):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as tmp:
                state = Path(tmp) / "notification.json"
                atomic_json(state, {"delivered_fingerprint": "previous", "status": "error"})
                def no_mail(_body):
                    self.fail("quiet recovery attempted email")
                self.assertTrue(deliver_transition(state, event, no_mail, "summary", event=event,
                                                   now=20, extra={"status": "clean", "findings": []}))
                saved = read_private_json(state)
                self.assertEqual(saved["delivered_event"], event)
                self.assertEqual(saved["status"], "clean")
                self.assertEqual(saved["findings"], [])
                self.assertFalse(deliver_transition(state, event, no_mail, "summary", event=event, now=21))
                self.assertEqual(read_private_json(state)["sent_at"], 20)

    def test_unknown_event_is_not_silently_treated_as_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "notification.json"
            with self.assertRaisesRegex(MonitorError, "delivery failed"):
                deliver_transition(state, "new", lambda _body: False, "summary",
                                   event="new_problem_kind", now=10)
            self.assertFalse(state.exists())

    def test_private_config_requires_regular_same_user_private_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{}")
            path.chmod(0o644)
            with self.assertRaises(MonitorError):
                read_private_json(path)
            path.chmod(0o600)
            self.assertEqual(read_private_json(path), {})
            link = Path(tmp) / "config-link.json"
            link.symlink_to(path)
            with self.assertRaises(MonitorError):
                read_private_json(link)

    def test_shared_scan_lock_refuses_a_second_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "state/scan.lock"
            with locked(lock_path):
                with self.assertRaises(BlockingIOError):
                    with locked(lock_path):
                        self.fail("second scanner acquired the lock")


class WrapperTests(unittest.TestCase):
    def config(self, root: Path, enabled=False):
        path = root / "config.json"
        healthchecks = {"enabled": enabled}
        if enabled:
            healthchecks["monitor_ping_urls"] = {
                "app": "https://hc-ping.com/REDACTED", "scan": "https://hc-ping.com/REDACTED-SCAN"
            }
        path.write_text(json.dumps({"healthchecks": healthchecks, "overall_timeout_seconds": 6600}))
        path.chmod(0o600)
        return path

    def test_preserves_original_exit_when_optional_ping_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp), enabled=True)
            called = []
            def runner(command, **kwargs):
                called.append((command, kwargs))
                return subprocess.CompletedProcess(command, 37)
            self.assertEqual(run_wrapped("app", ["/opt/python", "/home/user/vps-app-health.py", "--notify"],
                                         config_path=config, runner=runner,
                                         ping_fn=lambda *_a, **_k: False), 37)
            self.assertEqual(called[0][0], ["/opt/python", "/home/user/vps-app-health.py", "--notify"])

    def test_enabled_missing_ping_url_fails_explicitly_after_local_monitor(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp), enabled=True)
            called = []
            result = run_wrapped("disk", ["/opt/python", "/home/user/vps-disk-alert.py"],
                                 config_path=config,
                                 runner=lambda cmd, **_kw: called.append(cmd) or subprocess.CompletedProcess(cmd, 0))
            self.assertEqual(result, 2)
            self.assertEqual(len(called), 1)

    def test_ping_url_is_limited_to_https_healthchecks_host(self):
        self.assertEqual(validate_ping_url("https://hc-ping.com/REDACTED"), "https://hc-ping.com/REDACTED")
        with self.assertRaises(MonitorError):
            validate_ping_url("http://example.invalid/not-a-check")

    def test_ping_sends_empty_bounded_post_without_returning_response_body(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return None
            def read(self, count):
                self.count = count
                return b"private response"
        response = Response()
        calls = []
        def opener(request, timeout):
            calls.append((request, timeout))
            return response
        self.assertTrue(ping("https://hc-ping.com/REDACTED", "start", opener=opener))
        request, timeout = calls[0]
        self.assertEqual(request.data, b"")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "https://hc-ping.com/REDACTED/start")
        self.assertEqual(timeout, 5.0)
        self.assertEqual(response.count, 513)

    def test_component_timeouts_fit_service_budgets_and_scan_is_configured(self):
        self.assertEqual(component_timeout("app", {}), 90)
        self.assertEqual(component_timeout("disk", {}), 160)
        self.assertEqual(component_timeout("watchdog", {}), 20)
        self.assertEqual(component_timeout("scan", {"overall_timeout_seconds": 6600}), 6610)
        with self.assertRaises(MonitorError):
            component_timeout("scan", {"overall_timeout_seconds": 6901})
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp), enabled=True)
            seen = []
            run_wrapped("scan", ["/opt/python", "/ops/libexec/scanner.py"], config_path=config,
                        runner=lambda command, **kwargs: seen.append(kwargs) or subprocess.CompletedProcess(command, 0),
                        ping_fn=lambda *_args: True)
            self.assertEqual(seen[0]["timeout"], 6610)

    def test_negative_signal_status_uses_conventional_shell_code_and_ping_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp), enabled=True)
            signals = []
            result = run_wrapped("app", ["/opt/python", "/home/user/check.py"], config_path=config,
                                 runner=lambda command, **_kw: subprocess.CompletedProcess(command, -9),
                                 ping_fn=lambda _url, status: signals.append(status) or True)
            self.assertEqual(result, 137)
            self.assertEqual(signals, ["start", "1"])

    def test_component_timeout_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp), enabled=True)
            signals = []
            def timeout(_command, **kwargs):
                self.assertEqual(kwargs["timeout"], 90)
                raise subprocess.TimeoutExpired("check", 90)
            result = run_wrapped("app", ["/opt/python", "/home/user/check.py"], config_path=config,
                                 runner=timeout, ping_fn=lambda _url, status: signals.append(status) or True)
            self.assertEqual(result, 124)
            self.assertEqual(signals, ["start", "1"])


class ScannerTests(unittest.TestCase):
    IMAGE_ID = "sha256:" + "a" * 64
    CONTAINER_ID = "b" * 64

    def config(self, root: Path):
        raw = {
            "report_dir": str(root / "reports"),
            "state_dir": str(root / "state"),
            "email_transport_root": str(root / "xbot-missing"),
            "min_free_bytes": GIB,
            "scan_timeout_seconds": 60,
            "max_report_bytes": 2 * 1024 * 1024,
        }
        return validate_config(raw)

    def response(self, finding=None, *, trivy_status=0, leak="", trivy_override=None,
                 wrong_container_id=False, final_image_change=False):
        inspect_calls = 0
        def invoke(command, timeout):
            if command[1:4] == ["ps", "--no-trunc", "--quiet"]:
                return subprocess.CompletedProcess(command, 0, stdout=(self.CONTAINER_ID + "\n").encode(), stderr=b"")
            if command[1] == "inspect":
                nonlocal inspect_calls
                inspect_calls += 1
                image_id = "sha256:" + "d" * 64 if final_image_change and inspect_calls > 1 else self.IMAGE_ID
                row = {"Id": ("f" * 64 if wrong_container_id else self.CONTAINER_ID), "Image": image_id, "Name": "/sample-app",
                       "Config": {"Image": "registry.example/app:mutable-tag"}, "State": {"Running": True}}
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps([row]).encode(), stderr=b"")
            if command[1:3] == ["image", "inspect"]:
                rows = []
                for image_id in command[3:]:
                    rows.append({"Id": image_id, "RepoDigests": ["registry.example/app@sha256:" + "c" * 64]})
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps(rows).encode(), stderr=b"")
            if command[1] == "image":
                output = Path(command[command.index("--output") + 1])
                report = trivy_override if trivy_override is not None else {
                    "SchemaVersion": 2, "ArtifactName": self.IMAGE_ID, "ArtifactType": "container_image",
                    "Metadata": {"ImageID": self.IMAGE_ID}, "Results": []
                }
                if finding and trivy_override is None:
                    report["Results"] = [{"Target": "app/package-lock.json", "Class": "lang-pkgs", "Type": "npm",
                        "Vulnerabilities": [{
                        "VulnerabilityID": "CVE-2099-0001", "PkgName": "example-package",
                        "InstalledVersion": "1.0.0", "FixedVersion": "1.0.1", "Severity": "HIGH"}]}]
                output.write_text(json.dumps(report))
                return subprocess.CompletedProcess(command, trivy_status, stdout=b"", stderr=leak.encode())
            raise AssertionError("unexpected command")
        return invoke

    def test_scans_image_id_sequentially_and_marks_native_scope_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            emails = []
            report, status = run_scan(cfg, run=self.response(), send_email=lambda body: emails.append(body) or True, now=100)
            self.assertEqual(status, 0)
            self.assertEqual(report["status"], "clean")
            self.assertEqual(report["images"][0]["image_id"], self.IMAGE_ID)
            self.assertEqual(report["images"][0]["repo_digests"][0], "registry.example/app@sha256:" + "c" * 64)
            self.assertEqual(report["native_dependency_coverage"]["status"], "not_scanned")
            self.assertEqual(report["native_dependency_coverage"]["applications"], ["tfl", "xbot"])
            self.assertEqual(len(report["identity"]), 64)
            self.assertTrue((Path(tmp) / "state/scan.lock").exists())

    def test_malformed_or_wrong_image_trivy_json_fails_closed(self):
        cases = [
            {},
            {"SchemaVersion": 2, "ArtifactName": self.IMAGE_ID, "ArtifactType": "container_image",
             "Metadata": {"ImageID": "sha256:" + "d" * 64}, "Results": []},
        ]
        for override in cases:
            with self.subTest(override=override), tempfile.TemporaryDirectory() as tmp:
                report, status = run_scan(self.config(Path(tmp)),
                                          run=self.response(trivy_override=override),
                                          send_email=lambda _body: True, now=100)
                self.assertEqual((report["status"], status), ("error", 1))
                self.assertIn("invalid_trivy_report", {error["code"] for error in report["errors"]})

    def test_requested_container_id_is_cross_checked_and_final_inventory_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, status = run_scan(self.config(Path(tmp)), run=self.response(wrong_container_id=True),
                                      send_email=lambda _body: True, now=100)
            self.assertEqual((report["status"], status), ("error", 1))
        with tempfile.TemporaryDirectory() as tmp:
            report, status = run_scan(self.config(Path(tmp)), run=self.response(final_image_change=True),
                                      send_email=lambda _body: True, now=100)
            self.assertEqual((report["status"], status), ("error", 1))
            self.assertIn("runtime_inventory_changed", {error["code"] for error in report["errors"]})

    def test_completion_timestamp_uses_clock_at_end_of_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            report, _ = run_scan(cfg, run=self.response(), send_email=lambda _body: True,
                                 clock=iter([1700000000, 1700000123]).__next__)
            self.assertEqual(report["completed_at"], "2023-11-14T22:15:23+00:00")
            run_state = json.loads((Path(tmp) / "state/run.json").read_text())
            self.assertEqual(run_state["completed_at"], 1700000123)

    def test_corrupt_notification_state_fails_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            state_path = cfg["state_dir"] / "notifications.json"
            atomic_json(state_path, [])
            with self.assertRaisesRegex(MonitorError, "notification state has invalid shape"):
                run_scan(cfg, run=self.response(), send_email=lambda _body: True, now=100)

    def test_new_findings_errors_recovery_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            emails = []
            sender = lambda body: emails.append(body) or True
            found, code = run_scan(cfg, run=self.response(finding=True), send_email=sender, now=100)
            self.assertEqual((found["status"], code), ("findings", 0))
            self.assertIn("new_or_changed=1", emails[-1])
            self.assertNotIn("PRIVATE_OUTPUT_MARKER", emails[-1])
            before = len(emails)
            run_scan(cfg, run=self.response(finding=True), send_email=sender, now=200)
            self.assertEqual(len(emails), before)
            # A docker prerequisite failure is a scan error and never a clean report.
            failed = lambda command, _timeout: subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"PRIVATE_OUTPUT_MARKER")
            error, code = run_scan(cfg, run=failed, send_email=sender, now=300)
            self.assertEqual((error["status"], code), ("error", 1))
            self.assertNotIn("PRIVATE_OUTPUT_MARKER", json.dumps(error))
            self.assertNotIn("PRIVATE_OUTPUT_MARKER", emails[-1])
            before_recovery = len(emails)
            recovered, code = run_scan(cfg, run=self.response(), send_email=sender, now=400)
            self.assertEqual((recovered["status"], code), ("clean", 0))
            self.assertEqual(len(emails), before_recovery)
            state = read_private_json(cfg["state_dir"] / "notifications.json")
            self.assertEqual((state["status"], state["findings"]), ("clean", []))

    def test_error_followed_by_findings_is_not_a_quiet_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            emails = []
            sender = lambda body: emails.append(body) or True
            _, status = run_scan(cfg, run=self.response(trivy_status=1), send_email=sender, now=100)
            self.assertEqual(status, 1)
            self.assertEqual(len(emails), 1)
            with self.assertRaisesRegex(MonitorError, "delivery failed"):
                run_scan(cfg, run=self.response(finding=True), send_email=lambda _body: False, now=200)
            self.assertEqual(read_private_json(cfg["state_dir"] / "notifications.json")["status"], "error")
            report, status = run_scan(cfg, run=self.response(finding=True), send_email=sender, now=300)
            self.assertEqual((report["status"], status), ("findings", 0))
            self.assertEqual(len(emails), 2)
            self.assertIn("CVE-2099-0001", emails[-1])
            self.assertIn("new_or_changed=1", emails[-1])
            self.assertNotIn("recovered", emails[-1])
            self.assertEqual(read_private_json(cfg["state_dir"] / "notifications.json")["status"], "findings")

    def test_failed_delivery_does_not_acknowledge_finding_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            with self.assertRaises(MonitorError):
                run_scan(cfg, run=self.response(finding=True), send_email=lambda _body: False, now=100)
            state = Path(tmp) / "state/notifications.json"
            self.assertFalse(state.exists())
            self.assertFalse((Path(tmp) / "state/run.json").exists())

    def test_trivy_errors_fail_closed_and_raw_stderr_is_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            report, status = run_scan(cfg, run=self.response(trivy_status=1, leak="PRIVATE_OUTPUT_MARKER"),
                                      send_email=lambda _body: True, now=100)
            self.assertEqual((report["status"], status), ("error", 1))
            self.assertNotIn("PRIVATE_OUTPUT_MARKER", json.dumps(report))

    def test_retention_prunes_by_age_and_count_without_touching_fresh_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            old = reports / "scan-old.json"
            old.write_text("{}")
            os.utime(old, (1, 1))
            fresh = [reports / f"scan-{n}.json" for n in range(3)]
            now = time.time()
            for n, path in enumerate(fresh):
                path.write_text("{}")
                os.utime(path, (now + n, now + n))
            cfg = {"report_dir": reports, "min_free_bytes": GIB, "retention_days": 2,
                   "max_retained_reports": 2, "max_report_bytes": 1024,
                   "max_total_report_bytes": 4096}
            with patch("scanner.shutil.disk_usage", return_value=type("Usage", (), {"free": 2 * GIB})()):
                _check_guards(cfg)
            self.assertFalse(old.exists())
            self.assertEqual(len(list(reports.glob("scan-*.json"))), 1)
            self.assertTrue(fresh[-1].exists())

    def test_retention_preserves_last_valid_report_even_when_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
            valid = reports / "scan-valid.json"
            valid.write_text(json.dumps({"status": "clean"}))
            os.utime(valid, (1, 1))
            error = reports / "scan-error.json"
            error.write_text(json.dumps({"status": "error"}))
            cfg = {"report_dir": reports, "min_free_bytes": GIB, "retention_days": 2,
                   "max_retained_reports": 2, "max_report_bytes": 1024,
                   "max_total_report_bytes": 4096}
            with patch("scanner.shutil.disk_usage", return_value=type("Usage", (), {"free": 2 * GIB})()):
                _check_guards(cfg)
            self.assertTrue(valid.exists())
            self.assertFalse(error.exists())

    def test_missing_containers_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.config(Path(tmp))
            def no_containers(command, timeout):
                return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")
            report, status = run_scan(cfg, run=no_containers, send_email=lambda _body: True, now=100)
            self.assertEqual((report["status"], status), ("error", 1))


class WatchdogTests(unittest.TestCase):
    def test_missing_prerequisite_and_inactive_timer_are_explicit_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            def inactive(*_args, **_kwargs):
                return subprocess.CompletedProcess([], 3, stdout=b"", stderr=b"")
            self.assertEqual(inspect_scan_job(Path(tmp), now=100, run=inactive),
                             ["scanner:missing-heartbeat", "scanner:timer-inactive"])

    def test_stale_heartbeat_and_failed_delivery_transitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_json(root / "run.json", {"completed_at": 1, "status": "error", "scan_id": "safe"})
            def active(*_args, **_kwargs):
                return subprocess.CompletedProcess([], 0, stdout=b"active", stderr=b"")
            issues = inspect_scan_job(root, now=32 * 3600 + 2, run=active)
            self.assertEqual(sorted(issues), ["scanner:failed-run", "scanner:stale-heartbeat"])
            config = {"state_dir": root, "max_heartbeat_age_seconds": 32 * 3600,
                      "email_transport_root": "/unused"}
            with self.assertRaises(MonitorError):
                run_watchdog(config, now=32 * 3600 + 2, inspect=lambda *_a, **_k: issues, send=lambda _body: False)
            self.assertFalse((root / "watchdog-notifications.json").exists())
            messages = []
            run_watchdog(config, now=32 * 3600 + 2, inspect=lambda *_a, **_k: issues,
                         send=lambda body: messages.append(body) or True)
            self.assertIn("failed", messages[-1])
            self.assertEqual(run_watchdog(config, now=32 * 3600 + 3, inspect=lambda *_a, **_k: [],
                                          send=lambda _body: self.fail("recovery attempted email")), 0)
            self.assertEqual(len(messages), 1)
            self.assertEqual(read_private_json(root / "watchdog-notifications.json")["issues"], [])
            self.assertEqual(run_watchdog(config, now=32 * 3600 + 4, inspect=lambda *_a, **_k: issues,
                                          send=lambda body: messages.append(body) or True), 1)
            self.assertEqual(len(messages), 2)

    def test_fresh_failed_heartbeat_is_unhealthy_even_when_notification_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_json(root / "run.json", {"completed_at": 2000, "status": "error", "scan_id": "safe"})
            active = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout=b"active", stderr=b"")
            config = {"state_dir": root, "max_heartbeat_age_seconds": 32 * 3600,
                      "email_transport_root": "/unused"}
            sent = []
            first = run_watchdog(config, now=2001, inspect=lambda p, **kw: inspect_scan_job(p, now=kw["now"], run=active),
                                 send=lambda body: sent.append(body) or True)
            second = run_watchdog(config, now=2002, inspect=lambda p, **kw: inspect_scan_job(p, now=kw["now"], run=active),
                                  send=lambda body: sent.append(body) or True)
            self.assertEqual((first, second), (1, 1))
            self.assertEqual(len(sent), 1)
            self.assertIn("failed-run", sent[0])

    def test_heartbeat_symlink_and_corrupt_notification_state_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real-run.json"
            atomic_json(target, {"completed_at": 100, "status": "clean", "scan_id": "safe"})
            (root / "run.json").symlink_to(target)
            active = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout=b"active", stderr=b"")
            self.assertEqual(inspect_scan_job(root, now=101, run=active), ["scanner:untrusted-heartbeat"])
            atomic_json(root / "watchdog-notifications.json", [])
            config = {"state_dir": root, "max_heartbeat_age_seconds": 32 * 3600,
                      "email_transport_root": "/unused"}
            with self.assertRaises(MonitorError):
                run_watchdog(config, now=101, inspect=lambda *_args, **_kwargs: [], send=lambda _body: True)


if __name__ == "__main__":
    unittest.main()
