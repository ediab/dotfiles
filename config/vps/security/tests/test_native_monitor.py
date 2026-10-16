from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import MonitorError, atomic_json, locked, read_private_json
from native_healthcheck_wrapper import run_wrapped
from native_scanner import (
    Inventory,
    HOME,
    MIN_FREE_BYTES,
    Target,
    _db_updated_at,
    _disk_guard,
    _npm_manifest,
    _ancestors_manageable,
    _metadata_package,
    _installed_npm_packages,
    _prune_reports,
    _summary,
    _unit_binding,
    _validate_trivy,
    _writable_bits_ok,
    collect_inventory,
    default_targets,
    run_scan,
    validate_config,
)
from native_watchdog import MAX_HEARTBEAT_AGE, inspect_native_job, run_watchdog


class NativeInventoryTests(unittest.TestCase):
    def python_target(self, root: Path, *, lock: str = "demo==1.2.3\n",
                      lock_kind: str = "requirements", exact: bool = True) -> Target:
        if lock == "demo==1.2.3\n":
            lock = "demo==1.2.3 \\\n    --hash=sha256:" + "a" * 64 + "\n"
        root.mkdir(parents=True)
        (root / "requirements.lock").write_text(lock, encoding="utf-8")
        site = root / ".venv/lib/python3.12/site-packages"
        metadata = site / "demo-1.2.3.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: demo\nVersion: 1.2.3\n\n", encoding="utf-8")
        return Target("demo-app", "python", root, root.parent, "requirements.lock", ".venv",
                      lock_kind, "installed-python-environment", exact)

    def test_active_python_inventory_reads_only_installed_name_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self.python_target(Path(tmp) / "app")
            metadata_dir = target.root / ".venv/lib/python3.12/site-packages/demo-1.2.3.dist-info"
            (metadata_dir / "direct_url.json").write_text(
                '{"url":"https://packages.example.invalid/private.whl"}', encoding="utf-8")
            inventory = collect_inventory(target)
            self.assertIn(b"demo==1.2.3\n", inventory.input_bytes)
            self.assertNotIn(b"https://", inventory.input_bytes)
            self.assertEqual(inventory.binding["lock_binding"], "matched")
            self.assertNotIn("direct_url", json.dumps(inventory.binding))

    def test_escaping_environment_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = self.python_target(base / "app")
            outside = base / "outside"
            outside.mkdir()
            (target.root / ".venv").rename(target.root / ".venv-original")
            (target.root / ".venv").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(MonitorError, "environment-binding"):
                collect_inventory(target)

    def test_hash_lock_continuation_with_multiple_hashes_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = ("demo==1.2.3 \\\n"
                    "    --hash=sha256:" + "a" * 64 + " \\\n"
                    "    --hash=sha256:" + "b" * 64 + "\n")
            target = self.python_target(Path(tmp) / "app", lock=lock)
            self.assertTrue(collect_inventory(target).binding["coverage_complete"])

    def test_missing_python_metadata_and_unmatched_lock_are_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self.python_target(Path(tmp) / "app", lock="different==9.9\n")
            inventory = collect_inventory(target)
            self.assertFalse(inventory.binding["coverage_complete"])
            self.assertEqual(inventory.binding["lock_binding"], "mismatch-or-unpinned")
            (target.root / ".venv/lib/python3.12/site-packages/demo-1.2.3.dist-info/METADATA").unlink()
            with self.assertRaises(MonitorError):
                collect_inventory(target)

    def test_npm_lock_is_sanitized_before_filesystem_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tfl"
            root.mkdir()
            target = Target("tfl", "npm", root, root.parent, "package-lock.json", None,
                            "npm", "declared-lock-only")
            payload = json.dumps({
                "name": "tfl", "lockfileVersion": 3,
                "packages": {
                    "": {"name": "tfl", "scripts": {"postinstall": "steal-secrets"}},
                    "node_modules/pkg": {"version": "4.5.6", "resolved": "https://registry.example.invalid/pkg.tgz",
                                         "integrity": "sha512-AAAAAAAAAAAAAAAA", "dev": True},
                },
            }).encode()
            manifest, count, complete = _npm_manifest(payload, target)
            self.assertEqual(count, 1)
            self.assertTrue(complete)
            self.assertNotIn(b"registry", manifest)
            self.assertNotIn(b"scripts", manifest)
            self.assertIn(b'"version":"4.5.6"', manifest)

    def test_user_scope_unit_binding_checks_working_directory_only(self):
        target = Target("houses", "python", Path("/home/diab/apps/houses/pipeline"),
                        Path("/home/diab/apps/houses"), "uv.lock", ".venv", "uv",
                        "installed-python-environment", False, "houses-health.service",
                        "/home/diab/apps/houses/pipeline", None, (), "user")
        seen = []

        def unit_runner(command, **_kwargs):
            seen.append(command)
            return subprocess.CompletedProcess(command, 0,
                                              stdout="/home/diab/apps/houses/pipeline", stderr="")

        self.assertEqual(_unit_binding(target, unit_runner), "systemd-unit-verified")
        self.assertIn("--user", seen[0])
        self.assertIn("WorkingDirectory", seen[0][3])

        def wrong(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="/home/diab/apps/houses", stderr="")

        with self.assertRaisesRegex(MonitorError, "service-binding-mismatch"):
            _unit_binding(target, wrong)

    def test_default_scope_uses_verified_active_roots(self):
        targets = {target.application: target for target in default_targets()}
        self.assertEqual(str(targets["tfl"].root), "/var/lib/tfl/current")
        self.assertEqual(str(targets["tfl"].allowed_base), "/var/lib/tfl/releases")
        self.assertEqual(str(targets["xbot"].root), "/home/diab/Dev/xbot")
        self.assertEqual(str(targets["morning-brief"].root), "/home/diab/apps/morning-brief")
        self.assertEqual(str(targets["el-machine"].root), "/home/diab/apps/el-machine")
        self.assertEqual(str(targets["houses"].root), "/home/diab/apps/houses/pipeline")
        self.assertEqual(str(targets["houses"].allowed_base), "/home/diab/apps/houses")
        self.assertEqual(targets["houses"].lock_kind, "uv")
        self.assertEqual(targets["houses"].unit, "houses-health.service")
        self.assertEqual(targets["houses"].unit_scope, "user")
        self.assertEqual(len(targets), 5)
        self.assertEqual(targets["tfl"].scope, "active-release-runtime")
        self.assertEqual(targets["tfl"].unit, "tfl.service")
        self.assertEqual(targets["tfl"].unit_working_directory, "/var/lib/tfl/current")
        self.assertEqual(targets["tfl"].unit_user, "tfl")

    def test_dedicated_runtime_owners_and_unit_bindings_are_explicit(self):
        owners = {"xbot-app": 2101, "morning-brief-app": 2102, "el-machine-app": 2103}
        with mock.patch("native_scanner.pwd.getpwnam",
                        side_effect=lambda name: SimpleNamespace(pw_uid=owners[name])):
            targets = {target.application: target for target in default_targets()}
        for app, account in (("xbot", "xbot-app"), ("morning-brief", "morning-brief-app"),
                             ("el-machine", "el-machine-app")):
            self.assertEqual(targets[app].owner, owners[account])
        self.assertEqual(targets["xbot"].unit, "xbot-timeline.service")
        self.assertEqual(targets["xbot"].unit_user, "xbot-app")
        self.assertEqual(targets["el-machine"].unit, "el-machine-web.service")
        self.assertEqual(targets["el-machine"].unit_user, "el-machine-app")
        with mock.patch("native_scanner.pwd.getpwnam", side_effect=KeyError):
            missing = {target.application: target for target in default_targets()}
        self.assertTrue(all(missing[app].owner is None for app in ("xbot", "morning-brief", "el-machine")))
        self.assertEqual(missing["xbot"].unit_user, "xbot-app")

    def test_native_and_npm_unit_bindings_require_exact_executable_and_argv(self):
        targets = {target.application: target for target in default_targets()}
        for app in ("xbot", "el-machine", "tfl"):
            target = targets[app]
            values = {"WorkingDirectory": target.unit_working_directory, "User": target.unit_user,
                      "ExecStart": "{ path=" + target.unit_exec_argv[0] + " ; argv[]="
                                   + " ".join(target.unit_exec_argv) + " ; }"}
            def runner(command, **_kwargs):
                return subprocess.CompletedProcess(command, 0,
                    stdout=values[command[2].split("=", 1)[1]], stderr="")
            with self.subTest(app=app):
                self.assertEqual(_unit_binding(target, runner), "systemd-unit-verified")
                valid = values["ExecStart"]
                values["ExecStart"] = valid.replace("path=" + target.unit_exec_argv[0], "path=/wrong/executable")
                with self.assertRaisesRegex(MonitorError, "service-binding-mismatch"):
                    _unit_binding(target, runner)
                values["ExecStart"] = valid.replace(" ; }", " --unexpected ; }")
                with self.assertRaisesRegex(MonitorError, "service-binding-mismatch"):
                    _unit_binding(target, runner)

    def test_el_machine_metadata_hardlinks_are_read_bounded_and_contained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = root / "site-packages"
            meta = site / "library-1.2.3.dist-info"
            meta.mkdir(parents=True)
            payload = meta / "METADATA"
            payload.write_text("Metadata-Version: 2.1\nName: library\nVersion: 1.2.3\n\n",
                               encoding="utf-8")
            for index in range(5):
                os.link(payload, root / f"cached-metadata-{index}")
            self.assertEqual(payload.stat().st_nlink, 6)
            self.assertEqual(_metadata_package(site.resolve(), meta.name, frozenset({os.getuid()}))[:2],
                             ("library", "1.2.3"))
            payload.unlink()
            payload.symlink_to(root / "cached-metadata-0")
            with self.assertRaisesRegex(MonitorError, "package-metadata-unavailable"):
                _metadata_package(site.resolve(), meta.name, frozenset({os.getuid()}))

    def test_tfl_active_release_inventory_checks_service_and_sanitizes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            releases = base / "releases"
            release = releases / "release-abc"
            modules = release / "node_modules"
            package = modules / "pkg"
            package.mkdir(parents=True)
            (release / "package-lock.json").write_text(json.dumps({
                "name": "tfl", "lockfileVersion": 3,
                "packages": {"": {"name": "tfl"}, "node_modules/pkg": {"version": "4.5.6"}},
            }), encoding="utf-8")
            (package / "package.json").write_text(json.dumps({
                "name": "pkg", "version": "4.5.6", "scripts": {"postinstall": "must-not-run"},
            }), encoding="utf-8")
            current = base / "current"
            current.symlink_to(release, target_is_directory=True)
            target = Target("tfl", "npm", current, releases, "package-lock.json", "node_modules",
                            "npm", "active-release-runtime", False, "tfl.service", str(current), "tfl",
                            ("/usr/bin/npm", "start", "--", "-H", "127.0.0.1", "-p", "8084"))

            def unit_runner(command, **_kwargs):
                prop = command[2].split("=", 1)[1]
                values = {"WorkingDirectory": str(current), "User": "tfl",
                          "ExecStart": "{ path=/usr/bin/npm ; argv[]=/usr/bin/npm start -- -H 127.0.0.1 -p 8084 ; }"}
                return subprocess.CompletedProcess(command, 0, stdout=values[prop], stderr="")

            inventory = collect_inventory(target, unit_runner=unit_runner)
            self.assertTrue(inventory.binding["coverage_complete"])
            self.assertEqual(inventory.binding["release_binding"], "release-symlink")
            self.assertEqual(inventory.binding["unit_binding"], "systemd-unit-verified")
            self.assertIn(("pkg", "4.5.6"), inventory.expected_packages)
            self.assertNotIn(b"must-not-run", inventory.input_bytes)

            lock = json.loads((release / "package-lock.json").read_text())
            for suffix, version in (("pkg/node_modules/pkg", "4.5.6"),
                                    ("pkg/node_modules/pkg/node_modules/pkg", "7.8.9")):
                nested = modules / suffix
                nested.mkdir(parents=True)
                (nested / "package.json").write_text(json.dumps({"name": "pkg", "version": version}))
                lock["packages"]["node_modules/" + suffix] = {"version": version}
            (release / "package-lock.json").write_text(json.dumps(lock))
            inventory = collect_inventory(target, unit_runner=unit_runner)
            self.assertTrue(inventory.binding["coverage_complete"])
            self.assertEqual(inventory.package_count, 3)
            self.assertEqual(inventory.expected_packages, (("pkg", "4.5.6"), ("pkg", "7.8.9")))

    def test_tfl_wrong_systemd_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            release = base / "releases/r1"
            (release / "node_modules/pkg").mkdir(parents=True)
            (release / "package-lock.json").write_text(json.dumps({
                "name": "tfl", "lockfileVersion": 3,
                "packages": {"node_modules/pkg": {"version": "1.0.0"}},
            }), encoding="utf-8")
            (release / "node_modules/pkg/package.json").write_text(
                '{"name":"pkg","version":"1.0.0"}', encoding="utf-8")
            current = base / "current"
            current.symlink_to(release, target_is_directory=True)
            target = Target("tfl", "npm", current, base / "releases", "package-lock.json",
                            "node_modules", "npm", "active-release-runtime", False, "tfl.service",
                            str(current), "tfl", ("/usr/bin/npm", "start"))
            wrong_user = lambda command, **_kwargs: subprocess.CompletedProcess(command, 0,
                stdout="other-user" if "User" in command[2] else str(current), stderr="")
            with self.assertRaisesRegex(MonitorError, "service-binding-mismatch"):
                collect_inventory(target, unit_runner=wrong_user)

            def wrong_exec(command, **_kwargs):
                prop = command[2].split("=", 1)[1]
                values = {"WorkingDirectory": str(current), "User": "tfl",
                          "ExecStart": "{ path=/usr/bin/npm ; argv[]=/usr/bin/npm start -- -H 127.0.0.1 -p 9999 ; }"}
                return subprocess.CompletedProcess(command, 0, stdout=values[prop], stderr="")

            with self.assertRaisesRegex(MonitorError, "service-binding-mismatch"):
                collect_inventory(target, unit_runner=wrong_exec)


class OwnershipPolicyTests(unittest.TestCase):
    def metadata(self, root: Path):
        site = root / "site-packages"
        meta = site / "library-1.2.3.dist-info"
        meta.mkdir(parents=True)
        (meta / "METADATA").write_text("Name: library\nVersion: 1.2.3\n", encoding="utf-8")
        return site, meta

    def scanner_name(self) -> str:
        return pwd.getpwuid(os.getuid()).pw_name

    def test_private_group_modes_from_the_live_preflight_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, meta = self.metadata(Path(tmp))
            os.chmod(meta, 0o775)
            os.chmod(meta / "METADATA", 0o664)
            with mock.patch("native_scanner._group_members",
                            return_value=frozenset({self.scanner_name()})):
                self.assertEqual(
                    _metadata_package(site.resolve(), meta.name, frozenset({os.getuid()}))[:2],
                    ("library", "1.2.3"))

    def test_world_writable_metadata_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, meta = self.metadata(Path(tmp))
            os.chmod(meta, 0o777)
            with self.assertRaisesRegex(MonitorError, "package-metadata-directory-refused"):
                _metadata_package(site.resolve(), meta.name, frozenset({os.getuid()}))
            os.chmod(meta, 0o755)
            os.chmod(meta / "METADATA", 0o666)
            with self.assertRaisesRegex(MonitorError, "package-metadata-type-or-size-refused"):
                _metadata_package(site.resolve(), meta.name, frozenset({os.getuid()}))

    def test_shared_group_write_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, meta = self.metadata(Path(tmp))
            os.chmod(meta, 0o775)
            with mock.patch("native_scanner._group_members", return_value=frozenset({"otheruser"})):
                with self.assertRaisesRegex(MonitorError, "package-metadata-directory-refused"):
                    _metadata_package(site.resolve(), meta.name, frozenset({os.getuid()}))

    def test_foreign_owner_is_reported_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, meta = self.metadata(Path(tmp))
            with self.assertRaisesRegex(MonitorError, "package-metadata-owner-unsupported"):
                _metadata_package(site.resolve(), meta.name, frozenset({os.getuid() + 424242}))

    def test_writable_bits_policy_world_group_owner(self):
        from types import SimpleNamespace
        base = {"st_uid": os.getuid(), "st_gid": os.getgid()}
        self.assertTrue(_writable_bits_ok(SimpleNamespace(st_mode=0o100755, **base)))
        self.assertFalse(_writable_bits_ok(SimpleNamespace(st_mode=0o100777, **base)))
        self.assertFalse(_writable_bits_ok(SimpleNamespace(st_mode=0o100757, **base)))
        with mock.patch("native_scanner._group_members", return_value=frozenset({self.scanner_name()})):
            self.assertTrue(_writable_bits_ok(SimpleNamespace(st_mode=0o100775, **base)))
        with mock.patch("native_scanner._group_members", return_value=frozenset({"otheruser"})):
            self.assertFalse(_writable_bits_ok(SimpleNamespace(st_mode=0o100775, **base)))

    def test_ancestor_policy_is_bounded_to_the_app_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            middle = root / "a" / "b"
            middle.mkdir(parents=True)
            deep = middle / "node_modules"
            deep.mkdir()
            _ancestors_manageable(deep, root)
            os.chmod(middle, 0o777)
            with self.assertRaisesRegex(MonitorError, "ancestor-writable-refused"):
                _ancestors_manageable(deep, root)
            os.chmod(middle, 0o755)
            with self.assertRaisesRegex(MonitorError, "ancestor-stop-invalid"):
                _ancestors_manageable(deep, root / "unrelated")

    def test_npm_generated_lock_is_skipped_and_unknown_hidden_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()  # collect_inventory passes an already-resolved app root
            modules = root / "node_modules"
            package = modules / "pkg"
            package.mkdir(parents=True)
            (package / "package.json").write_text('{"name":"pkg","version":"1.0.0"}',
                                                   encoding="utf-8")
            (modules / ".package-lock.json").write_text("{}", encoding="utf-8")
            os.chmod(modules / ".package-lock.json", 0o644)
            (modules / ".bin").mkdir()
            self.assertEqual(_installed_npm_packages(root, "node_modules"),
                             {"node_modules/pkg": ("pkg", "1.0.0")})
            (modules / ".package-lock.json").unlink()
            (modules / ".package-lock.json").symlink_to(root / "missing")
            with self.assertRaisesRegex(MonitorError, "npm-generated-metadata-refused"):
                _installed_npm_packages(root, "node_modules")
            (modules / ".package-lock.json").unlink()
            (modules / ".evil").symlink_to(root / "missing")
            with self.assertRaisesRegex(MonitorError, "npm-package-link-or-type-refused"):
                _installed_npm_packages(root, "node_modules")


class TrivyFilesystemTests(unittest.TestCase):
    def inventory(self):
        target = Target("demo-app", "python", Path("/src/app"), Path("/src"), "requirements.lock",
                        ".venv", "requirements", "installed-python-environment")
        return Inventory(target, "requirements.txt", b"demo==1.2.3\n", "a" * 64, 1,
                         {"application": "demo-app", "coverage_complete": True},
                         (("demo", "1.2.3"),), "lang-pkgs", "pip")

    def test_filesystem_report_accepts_valid_zero_findings_and_maps_findings(self):
        empty = {"SchemaVersion": 2, "ArtifactName": "/private/stage", "ArtifactType": "filesystem",
                 "Metadata": {"ImageConfig": {}}, "Results": [{"Target": "requirements.txt",
                 "Class": "lang-pkgs", "Type": "pip", "Packages": [{"Name": "demo", "Version": "1.2.3"}],
                 "Vulnerabilities": []}]}
        self.assertEqual(_validate_trivy(empty, self.inventory(), expected_artifact="/private/stage"), [])
        report = {**empty, "Results": [{"Target": "requirements.txt", "Class": "lang-pkgs", "Type": "pip",
                   "Vulnerabilities": [{"VulnerabilityID": "CVE-2026-0001", "PkgName": "demo",
                                         "InstalledVersion": "1.2.3", "FixedVersion": "1.2.4",
                                         "Severity": "HIGH"}],
                   "Packages": [{"Name": "demo", "Version": "1.2.3"}]}]}
        finding = _validate_trivy(report, self.inventory(), expected_artifact="/private/stage")[0]
        self.assertEqual(finding["application"], "demo-app")
        self.assertEqual(finding["package"], "demo")
        self.assertNotIn("/private", json.dumps(finding))

    def test_trivy_report_requires_exact_artifact_ecosystem_and_package_inventory(self):
        valid = {"SchemaVersion": 2, "ArtifactName": "/private/stage", "ArtifactType": "filesystem",
                 "Metadata": {}, "Results": [{"Target": "requirements.txt", "Class": "lang-pkgs",
                 "Type": "pip", "Packages": [{"Name": "demo", "Version": "1.2.3"}],
                 "Vulnerabilities": []}]}
        wrong = (
            {**valid, "ArtifactName": "/other/manifest"},
            {**valid, "Results": [{**valid["Results"][0], "Target": "other.lock"}]},
            {**valid, "Results": [{**valid["Results"][0], "Class": "os-pkgs"}]},
            {**valid, "Results": [{**valid["Results"][0], "Type": "npm"}]},
            {**valid, "Results": [{**valid["Results"][0], "Packages": []}]},
            {**valid, "Results": [{**valid["Results"][0], "Packages": [{"Name": "foreign", "Version": "9.9"}]}]},
        )
        for report in wrong:
            with self.subTest(report=report), self.assertRaises(MonitorError):
                _validate_trivy(report, self.inventory(), expected_artifact="/private/stage")

    def test_wrong_artifact_type_and_malformed_trivy_fail_closed(self):
        base = {"SchemaVersion": 2, "ArtifactName": "scan", "ArtifactType": "container_image",
                "Metadata": {"ImageID": "sha256:deadbeef"}, "Results": []}
        with self.assertRaisesRegex(MonitorError, "trivy-filesystem-report-invalid"):
            _validate_trivy(base, self.inventory(), expected_artifact="scan")
        for malformed in ({}, {**base, "ArtifactType": "filesystem", "Results": None},
                          {**base, "ArtifactType": "filesystem", "Results": []},
                          {**base, "ArtifactType": "filesystem", "Results": [{"Target": "x"}]}):
            with self.subTest(malformed=malformed), self.assertRaises(MonitorError):
                _validate_trivy(malformed, self.inventory(), expected_artifact="scan")

    def test_package_only_trivy_metadata_may_be_omitted_but_not_malformed(self):
        report = {"SchemaVersion": 2, "ArtifactName": "/private/stage",
                  "ArtifactType": "filesystem", "Results": [{
                      "Target": "requirements.txt", "Class": "lang-pkgs", "Type": "pip",
                      "Packages": [{"Name": "demo", "Version": "1.2.3"}]}]}
        self.assertEqual(_validate_trivy(report, self.inventory(),
                                        expected_artifact="/private/stage"), [])
        for metadata in (None, [], "invalid"):
            with self.subTest(metadata=metadata), self.assertRaises(MonitorError):
                _validate_trivy({**report, "Metadata": metadata}, self.inventory(),
                                expected_artifact="/private/stage")

    def test_db_freshness_and_five_gib_hard_floor(self):
        now = 1_800_000_000
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.json"
            updated = "2027-01-15T08:00:00+00:00"
            path.write_text(json.dumps({"UpdatedAt": updated}), encoding="utf-8")
            path.chmod(0o600)
            from datetime import datetime
            timestamp = int(datetime.fromisoformat(updated).timestamp())
            self.assertEqual(_db_updated_at(path, now=timestamp + 10, owner=os.getuid()), timestamp)
            self.assertGreaterEqual(MIN_FREE_BYTES, 5 * 1024**3)
            with self.assertRaisesRegex(MonitorError, "free-space-hard-floor"):
                _disk_guard(Path(tmp), min_free_bytes=MIN_FREE_BYTES,
                            disk_usage=lambda _path: SimpleNamespace(free=MIN_FREE_BYTES - 1))


class NativeScanTests(unittest.TestCase):
    def target(self, root: Path) -> Target:
        root.mkdir(parents=True)
        (root / "requirements.lock").write_text(
            "demo==1.2.3 \\\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
        meta = root / ".venv/lib/python3.12/site-packages/demo-1.2.3.dist-info"
        meta.mkdir(parents=True)
        (meta / "METADATA").write_text("Name: demo\nVersion: 1.2.3\n", encoding="utf-8")
        return Target("demo-app", "python", root, root.parent, "requirements.lock", ".venv",
                      "requirements", "installed-python-environment", True)

    def config(self, root: Path):
        state = root / "state"
        reports = state / "reports"
        cache = root / "cache"
        metadata = cache / "db/metadata.json"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        import datetime
        updated_at = datetime.datetime.fromtimestamp(1_800_000_000, datetime.timezone.utc)
        metadata.write_text(json.dumps({"UpdatedAt": updated_at.isoformat()}),
                            encoding="utf-8")
        metadata.chmod(0o600)
        return {"state_dir": state, "report_dir": reports, "email_transport_root": root / "xbot",
                "trivy_cache_dir": cache, "trivy_path": Path("/usr/bin/trivy"),
                "min_free_bytes": MIN_FREE_BYTES, "overall_timeout_seconds": 1200,
                "per_target_timeout_seconds": 300, "max_report_bytes": 8 * 1024**2,
                "max_trivy_report_bytes": 16 * 1024**2, "max_retained_reports": 24,
                "max_total_report_bytes": 256 * 1024**2, "retention_seconds": 45 * 86400}

    def runner(self, artifact_type="filesystem", *, mutate=None, finding=None):
        def fake(command, **kwargs):
            if "--list-all-pkgs" not in command:
                raise AssertionError("native scans must request complete Trivy package inventory")
            if mutate:
                mutate()
            output = Path(command[command.index("--output") + 1])
            package = {"Name": "demo", "Version": "1.2.3"}
            payload = {"SchemaVersion": 2, "ArtifactName": command[-1],
                       "ArtifactType": artifact_type, "Metadata": {"ImageConfig": {}},
                       "Results": [{"Target": "requirements.txt", "Class": "lang-pkgs",
                           "Type": "pip", "Packages": [package],
                           "Vulnerabilities": [] if finding is None else [finding]}]}
            output.write_text(json.dumps(payload), encoding="utf-8")
            output.chmod(0o600)
            return subprocess.CompletedProcess(command, 0)
        return fake

    def run_with(self, root, target, runner=None, **kwargs):
        return run_scan(self.config(root), targets=(target,), runner=runner or self.runner(),
                        send_email=kwargs.get("send_email", lambda _body: True), now=1_800_000_000,
                        clock=lambda: 1_800_000_010,
                        disk_usage=lambda _path: SimpleNamespace(free=20 * 1024**3))

    def test_success_is_distinct_filesystem_artifact_and_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            report, status = self.run_with(root, target)
            self.assertEqual(status, 0)
            self.assertEqual(report["artifact_type"], "filesystem")
            self.assertEqual(report["status"], "clean")
            self.assertEqual(report["completed_at"], "2027-01-15T08:00:10+00:00")
            saved = (root / "state/reports" / f"native-scan-{report['scan_id']}.json").read_text()
            self.assertNotIn(str(root), saved)
            self.assertTrue((root / "state/native-run.json").exists())
            self.assertEqual(list((root / "state").glob("native-scan-*")), [])

    def test_wrong_trivy_type_or_failed_process_is_error_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            report, status = self.run_with(root, target, self.runner("container_image"))
            self.assertEqual(status, 1)
            self.assertEqual(report["status"], "error")
            self.assertEqual(report["findings"], [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            def failed(command, **kwargs):
                return subprocess.CompletedProcess(command, 1)
            report, status = self.run_with(root, target, failed)
            self.assertEqual(status, 1)
            self.assertIn("trivy-failed", {item["code"] for item in report["errors"]})

    def test_incomplete_lock_binding_is_error_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            (target.root / "requirements.lock").write_text("other==9.9\n", encoding="utf-8")
            report, status = self.run_with(root, target)
            self.assertEqual(status, 1)
            self.assertEqual(report["coverage_status"], "incomplete")
            self.assertIn("coverage-incomplete", {item["code"] for item in report["errors"]})

    def test_inventory_change_during_scan_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            changed = False
            def mutate():
                nonlocal changed
                if not changed:
                    changed = True
                    (target.root / "requirements.lock").write_text("demo==1.2.4\n", encoding="utf-8")
            report, status = self.run_with(root, target, self.runner(mutate=mutate))
            self.assertEqual(status, 1)
            self.assertIn("inventory-changed-during-scan", {item["code"] for item in report["errors"]})

    def test_failed_email_does_not_advance_notification_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            with self.assertRaisesRegex(MonitorError, "delivery failed"):
                self.run_with(root, target, self.runner("container_image"), send_email=lambda _body: False)
            self.assertFalse((root / "state/native-notifications.json").exists())

    def test_changed_findings_deduplicate_then_clear_on_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            sent = []
            finding = {"VulnerabilityID": "CVE-2026-1234", "PkgName": "demo",
                       "InstalledVersion": "1.2.3", "FixedVersion": "1.2.4", "Severity": "HIGH"}
            first, _ = self.run_with(root, target, self.runner(finding=finding),
                                     send_email=lambda body: sent.append(body) or True)
            second, _ = self.run_with(root, target, self.runner(finding=finding),
                                      send_email=lambda body: sent.append(body) or True)
            self.assertEqual(first["status"], "findings")
            self.assertEqual(second["status"], "findings")
            self.assertEqual(len(sent), 1)
            self.assertIn("CVE-2026-1234", sent[0])
            self.assertNotIn(str(root), sent[0])
            self.run_with(root, target, self.runner(),
                          send_email=lambda body: sent.append(body) or True)
            self.assertEqual(len(sent), 1)
            state = read_private_json(root / "state/native-notifications.json")
            self.assertEqual((state["status"], state["findings"]), ("clean", []))
            self.assertEqual(state["delivered_event"], "findings_cleared")
            self.run_with(root, target, self.runner(finding=finding),
                          send_email=lambda body: sent.append(body) or True)
            self.assertEqual(len(sent), 2)
            self.assertIn("CVE-2026-1234", sent[1])

    def test_error_followed_by_findings_is_delivered_not_silenced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            sent = []
            sender = lambda body: sent.append(body) or True
            report, status = self.run_with(root, target, self.runner("container_image"), send_email=sender)
            self.assertEqual((report["status"], status), ("error", 1))
            finding = {"VulnerabilityID": "CVE-2026-1234", "PkgName": "demo",
                       "InstalledVersion": "1.2.3", "FixedVersion": "1.2.4", "Severity": "HIGH"}
            with self.assertRaisesRegex(MonitorError, "delivery failed"):
                self.run_with(root, target, self.runner(finding=finding), send_email=lambda _body: False)
            self.assertEqual(read_private_json(root / "state/native-notifications.json")["status"], "error")
            report, status = self.run_with(root, target, self.runner(finding=finding), send_email=sender)
            self.assertEqual((report["status"], status), ("findings", 0))
            self.assertEqual(len(sent), 2)
            self.assertIn("CVE-2026-1234", sent[-1])
            self.assertIn("findings changed", sent[-1])
            self.assertNotIn("recovered", sent[-1])

    def test_error_summary_still_reports_new_findings_without_paths(self):
        report = {"status": "error", "errors": [{"code": "coverage-incomplete"}],
                  "findings": [{"application": "xbot", "vulnerability_id": "CVE-2026-2345",
                                "package": "demo", "installed_version": "1.2.3",
                                "fixed_version": "1.2.4", "severity": "HIGH"}]}
        event, body = _summary(report, {}, "scan-id")
        self.assertEqual(event, "scan_error")
        self.assertIn("CVE-2026-2345", body)
        self.assertNotIn("/home/diab", body)

    def test_incomplete_scan_never_claims_resolved_and_retains_finding_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            finding = {"VulnerabilityID": "CVE-2026-1234", "PkgName": "demo",
                       "InstalledVersion": "1.2.3", "FixedVersion": "1.2.4", "Severity": "HIGH"}
            complete, _ = self.run_with(root, target, self.runner(finding=finding))
            state_path = root / "state/native-notifications.json"
            before = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(len(before["findings"]), 1)
            (target.root / "requirements.lock").write_text("other==9.9\n", encoding="utf-8")
            partial, _ = self.run_with(root, target, self.runner())
            after = json.loads(state_path.read_text(encoding="utf-8"))
            summary = _summary(partial, before, "partial-test")[1]
            self.assertEqual(partial["status"], "error")
            self.assertNotIn("RESOLVED", summary)
            self.assertEqual(after["findings"], before["findings"])
            self.assertEqual(complete["findings"], before["findings"])

    def test_inventory_failure_reports_safe_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.target(root / "app")
            meta = target.root / ".venv/lib/python3.12/site-packages/demo-1.2.3.dist-info"
            os.chmod(meta, 0o777)
            report, status = self.run_with(root, target)
            self.assertEqual(status, 1)
            details = {(item.get("application"), item.get("code"), item.get("detail"))
                       for item in report["errors"]}
            self.assertIn(("demo-app", "inventory_failed", "package-metadata-directory-refused"),
                          details)

    def test_shared_lock_and_retention_are_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(root)
            config["report_dir"].mkdir(parents=True)
            old_native = config["report_dir"] / "native-scan-old.json"
            old_native.write_text("{}", encoding="utf-8")
            os.chmod(old_native, 0o600)
            old_image = config["report_dir"] / "scan-old.json"
            old_image.write_text("{}", encoding="utf-8")
            os.chmod(old_image, 0o600)
            old_time = 1_600_000_000
            os.utime(old_native, (old_time, old_time))
            os.utime(old_image, (old_time, old_time))
            _prune_reports(config, now=1_800_000_000)
            self.assertFalse(old_native.exists())
            self.assertTrue(old_image.exists())
            with locked(config["state_dir"] / "scan.lock"):
                with self.assertRaises(BlockingIOError):
                    with locked(config["state_dir"] / "scan.lock"):
                        pass

    def test_example_config_binds_the_root_owned_transport(self):
        raw = json.loads((ROOT / "examples/native.json").read_text())
        config = validate_config(raw)
        self.assertEqual(config["email_transport_root"], Path("/usr/local/lib/vps-monitor-transport"))
        raw["email_transport_root"] = str(HOME / "Dev/xbot")
        with self.assertRaisesRegex(MonitorError, "native-scan-path-config-refused"):
            validate_config(raw)

    def test_config_rejects_lower_floor_and_enabled_missing_healthchecks(self):
        raw = {"state_dir": str(HOME / ".local/state/vps-security-scan"),
               "report_dir": str(HOME / ".local/state/vps-security-scan/reports"),
               "email_transport_root": "/usr/local/lib/vps-monitor-transport",
               "trivy_cache_dir": str(HOME / ".cache/trivy"),
               "min_free_bytes": MIN_FREE_BYTES - 1}
        with self.assertRaisesRegex(MonitorError, "bounds"):
            validate_config(raw)
        raw["min_free_bytes"] = MIN_FREE_BYTES
        raw["healthchecks"] = {"enabled": True}
        with self.assertRaisesRegex(MonitorError, "healthchecks"):
            validate_config(raw)


class WatchdogAndHealthcheckTests(unittest.TestCase):
    def test_watchdog_flags_missing_failed_stale_and_inactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 3)
            self.assertEqual(inspect_native_job(root, now=100, run=run),
                             ["native:missing-heartbeat", "native:timer-inactive"])
            atomic_json(root / "native-run.json", {"completed_at": 1, "status": "error"})
            stale_now = MAX_HEARTBEAT_AGE + 100
            self.assertEqual(inspect_native_job(root, now=stale_now, run=run),
                             ["native:stale-heartbeat", "native:failed-run", "native:timer-inactive"])

    def test_watchdog_returns_unhealthy_after_deduplicated_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            issues = ["native:failed-run"]
            sent = []
            config = {"state_dir": state}
            inspect = lambda *_args, **_kwargs: issues
            self.assertEqual(run_watchdog(config, now=100, inspect=inspect,
                                          send=lambda body: sent.append(body) or True), 1)
            self.assertEqual(run_watchdog(config, now=101, inspect=inspect,
                                          send=lambda body: sent.append(body) or True), 1)
            self.assertEqual(len(sent), 1)

    def test_watchdog_recovery_is_quiet_and_next_failure_still_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            config = {"state_dir": state}
            sent = []
            issues = ["native:failed-run"]
            sender = lambda body: sent.append(body) or True
            self.assertEqual(run_watchdog(config, now=100, inspect=lambda *_a, **_k: issues, send=sender), 1)
            self.assertEqual(run_watchdog(config, now=101, inspect=lambda *_a, **_k: [],
                                          send=lambda _body: self.fail("recovery attempted email")), 0)
            self.assertEqual(len(sent), 1)
            self.assertEqual(read_private_json(state / "native-watchdog-notifications.json")["issues"], [])
            self.assertEqual(run_watchdog(config, now=102, inspect=lambda *_a, **_k: issues, send=sender), 1)
            self.assertEqual(len(sent), 2)

    def test_corrupt_watchdog_state_and_symlink_heartbeat_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "native-run.json"
            heartbeat.symlink_to(root / "missing")
            timer_ok = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0)
            self.assertEqual(inspect_native_job(root, now=100, run=timer_ok),
                             ["native:untrusted-heartbeat"])
            state = root / "native-watchdog-notifications.json"
            state.write_text("[]", encoding="utf-8")
            os.chmod(state, 0o600)
            with self.assertRaisesRegex(MonitorError, "state-invalid"):
                run_watchdog({"state_dir": root}, now=100,
                             inspect=lambda *_args, **_kwargs: [], send=lambda _body: True)

    def test_native_wrapper_preserves_command_failure_and_reports_ping_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {"state_dir": str(root / "state"), "report_dir": str(root / "state/reports"),
                      "email_transport_root": str(root), "trivy_cache_dir": str(root / "trivy"),
                      "healthchecks": {"enabled": False}}
            path = root / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            os.chmod(path, 0o600)
            completed = subprocess.CompletedProcess(["/bin/true"], 19)
            with mock.patch("native_healthcheck_wrapper.validate_config", return_value={"healthchecks": {"enabled": False}}):
                self.assertEqual(run_wrapped("native", ["/bin/true"], config_path=path,
                                              runner=lambda *_a, **_k: completed), 19)

    def test_native_wrapper_uses_start_and_completion_suffixes_without_pinging_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{}", encoding="utf-8")
            os.chmod(path, 0o600)
            statuses = []
            checked = {"healthchecks": {"enabled": True,
                                        "native_ping_url": "https://hc-ping.com/private-check"}}
            with mock.patch("native_healthcheck_wrapper.validate_config", return_value=checked):
                result = run_wrapped("native", ["/bin/true"], config_path=path,
                                     runner=lambda *_a, **_k: subprocess.CompletedProcess([], 0),
                                     ping_fn=lambda _url, status: statuses.append(status) or True)
            self.assertEqual(result, 0)
            self.assertEqual(statuses, ["start", "0"])


if __name__ == "__main__":
    unittest.main()
