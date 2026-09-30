#!/usr/bin/env python3
"""Isolated package, bootstrap and rebuild regression tests; no live Pi/network."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "reconcile-pi-packages.py"
PACKAGE = runpy.run_path(str(HELPER))["package"]


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="dotfiles-packages-test.")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.home = self.root / "home"
        self.agent = self.home / ".pi/agent"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.home.mkdir()
        self.log = self.root / "pi.log"
        self.desired = self.root / "desired.json"
        self.live = self.agent / "settings.json"
        self.pending = self.agent / "settings.json.pre-reconcile"
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        FAKE_PI_HELPER=str(HELPER), FAKE_PI_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        for key in ("FAKE_PI_FAIL_INSTALL", "FAKE_PI_FAIL_REMOVE"):
            self.env.pop(key, None)
        shutil.copyfile(ROOT / "tests/fake-pi.py", self.bin / "pi")
        (self.bin / "pi").chmod(0o755)

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def helper(self, operation, ok=True):
        args = [sys.executable, str(HELPER), operation]
        if operation == "prepare":
            args.append(str(self.desired))
        result = subprocess.run(args, env=self.env, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def reconcile(self, wanted):
        self.write(self.desired, wanted)
        self.helper("prepare")
        self.helper("reconcile")

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def installed(self, name, version):
        self.write(self.agent / "npm/node_modules" / name / "package.json", {"version": version})

    def test_source_identity_and_paths(self):
        cases = [
            ("npm:plain@2.0.0", "npm:plain", "npm/node_modules/plain", "2.0.0"),
            ("npm:@scope/pkg@1.5.3", "npm:@scope/pkg", "npm/node_modules/@scope/pkg", "1.5.3"),
            ("npm:@scope/pkg", "npm:@scope/pkg", "npm/node_modules/@scope/pkg", ""),
            ("git:github.com/owner/repo@v2", "git:github.com/owner/repo", "git/github.com/owner/repo", ""),
            ("https://github.com/owner/repo.git@v1", "git:github.com/owner/repo", "git/github.com/owner/repo", ""),
            ("git:git@github.com:owner/repo.git", "git:github.com/owner/repo", "git/github.com/owner/repo", ""),
        ]
        for source, identity, path, version in cases:
            with self.subTest(source=source):
                self.assertEqual(PACKAGE(source, self.agent), (identity, self.agent / path, version))
        self.assertEqual(PACKAGE("./local", self.agent)[0], "local:" + str(self.agent / "local"))

    def test_fresh_object_pin_and_filter_preservation(self):
        wanted = {"theme": "system", "packages": [{"source": "npm:@lnilluv/pi-opencode-go-rotation@1.5.3", "extensions": ["+dist/index.js"]}]}
        self.reconcile(wanted)
        self.assertEqual(json.loads(self.live.read_text()), wanted)
        self.assertEqual(json.loads((self.agent / "npm/node_modules/@lnilluv/pi-opencode-go-rotation/package.json").read_text())["version"], "1.5.3")
        self.assertFalse(self.pending.exists())
        self.reconcile(wanted)
        self.assertEqual(len(self.calls()), 1, "satisfied exact pin was reinstalled")

    def test_pin_change_and_disk_mismatch_are_installs_not_removals(self):
        self.write(self.live, {"packages": ["npm:@scope/pkg@1.0.0"]})
        self.installed("@scope/pkg", "1.0.0")
        wanted = {"packages": [{"source": "npm:@scope/pkg@2.0.0", "skills": []}]}
        self.reconcile(wanted)
        self.assertEqual([c["argv"][0] for c in self.calls()], ["install"])
        # Even with matching settings, a stale physical pin must be corrected.
        self.installed("@scope/pkg", "1.0.0")
        self.reconcile(wanted)
        self.assertEqual([c["argv"][0] for c in self.calls()], ["install", "install"])

    def test_removed_object_only_and_foreign_package_untouched(self):
        self.write(self.live, {"packages": [{"source": "npm:retired", "skills": []}]})
        self.installed("retired", "1.0.0")
        self.installed("foreign", "1.0.0")
        self.reconcile({"packages": []})
        self.assertEqual(self.calls()[0]["argv"][:2], ["remove", "npm:retired"])
        self.assertFalse((self.agent / "npm/node_modules/retired").exists())
        self.assertTrue((self.agent / "npm/node_modules/foreign").exists())

    def test_failed_removal_survives_prepare_and_another_settings_change(self):
        self.write(self.live, {"packages": ["npm:retired"]})
        self.installed("retired", "1.0.0")
        self.write(self.desired, {"packages": ["npm:intermediate"]})
        self.helper("prepare")
        self.env["FAKE_PI_FAIL_REMOVE"] = "npm:retired"
        self.helper("reconcile", ok=False)
        self.assertTrue(self.pending.exists())
        # A new package may have been auto-installed after the failed deploy.
        self.installed("intermediate", "1.0.0")
        self.env.pop("FAKE_PI_FAIL_REMOVE")
        self.reconcile({"packages": []})
        self.assertEqual([c["argv"][:2] for c in self.calls()], [
            ["remove", "npm:retired"], ["remove", "npm:retired"], ["remove", "npm:intermediate"]])
        self.assertFalse(self.pending.exists())

    def test_successful_removals_are_not_retried_after_later_failure(self):
        self.write(self.live, {"packages": ["npm:first", "npm:second"]})
        self.write(self.desired, {"packages": []})
        self.helper("prepare")
        self.env["FAKE_PI_FAIL_REMOVE"] = "npm:second"
        self.helper("reconcile", ok=False)
        self.env.pop("FAKE_PI_FAIL_REMOVE")
        self.reconcile({"packages": []})
        self.assertEqual([c["argv"][1] for c in self.calls()], ["npm:first", "npm:second", "npm:second"])

    def test_failed_install_preserves_settings_filters_and_retries(self):
        wanted = {"packages": [{"source": "npm:new@1.0.0", "extensions": []}], "defaultThinkingLevel": "high"}
        self.write(self.desired, wanted)
        self.helper("prepare")
        self.env["FAKE_PI_FAIL_INSTALL"] = "npm:new@1.0.0"
        self.helper("reconcile", ok=False)
        self.assertEqual(json.loads(self.live.read_text()), wanted)
        self.assertTrue(self.pending.exists())
        self.env.pop("FAKE_PI_FAIL_INSTALL")
        self.reconcile(wanted)
        self.assertEqual(len(self.calls()), 2)

    def test_git_ref_change_same_identity_is_not_removed(self):
        self.write(self.live, {"packages": ["git:github.com/owner/repo@v1"]})
        (self.agent / "git/github.com/owner/repo/.git").mkdir(parents=True)
        self.reconcile({"packages": [{"source": "https://github.com/owner/repo.git@v2", "skills": []}]})
        self.assertEqual(self.calls()[0]["argv"][:2], ["install", "https://github.com/owner/repo.git@v2"])
        self.reconcile({"packages": []})
        self.assertFalse((self.agent / "git/github.com/owner/repo").exists())

    def test_failed_git_ref_install_is_retried_with_existing_checkout(self):
        self.write(self.live, {"packages": ["git:github.com/owner/repo@v1"]})
        (self.agent / "git/github.com/owner/repo/.git").mkdir(parents=True)
        wanted = {"packages": ["git:github.com/owner/repo@v2"]}
        self.write(self.desired, wanted)
        self.helper("prepare")
        self.env["FAKE_PI_FAIL_INSTALL"] = "git:github.com/owner/repo@v2"
        self.helper("reconcile", ok=False)
        self.env.pop("FAKE_PI_FAIL_INSTALL")
        self.reconcile(wanted)
        self.assertEqual([c["argv"][:2] for c in self.calls()], [
            ["install", "git:github.com/owner/repo@v2"], ["install", "git:github.com/owner/repo@v2"]])

    def test_unsafe_package_paths_are_rejected(self):
        for source in ("npm:..", "npm:../../escape", "git:../owner/repo", "git:github.com/owner/../escape",
                       "https://github.com/owner/%2e%2e/escape"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                PACKAGE(source, self.agent)

    def test_invalid_desired_or_previous_state_stops_before_live_write(self):
        before = {"packages": ["npm:keep"]}
        self.write(self.live, before)
        self.write(self.desired, {"packages": [None]})
        self.helper("prepare", ok=False)
        self.assertEqual(json.loads(self.live.read_text()), before)
        self.assertFalse(self.pending.exists())
        self.write(self.desired, {"packages": []})
        self.write(self.pending, {"packages": [None]})
        self.helper("prepare", ok=False)
        self.assertEqual(json.loads(self.live.read_text()), before)
        self.assertEqual(self.calls(), [])

    def script_repo(self):
        repo = self.root / "repo"
        (repo / "home/agents").mkdir(parents=True)
        for name in ("bootstrap.sh", "rebuild.sh", "reconcile-pi-packages.py"):
            shutil.copyfile(ROOT / name, repo / name)
        for name in ("subagents.json", "open-tui.json", "pi-btw.json", "web-search.json", ".env.example"):
            shutil.copyfile(ROOT / "home" / name, repo / "home" / name)
        for name in ("lint-agent-content.sh", "sync-agent-content.sh"):
            (repo / name).write_text("#!/usr/bin/env bash\nexit 0\n")
            (repo / name).chmod(0o755)
        (self.bin / "gh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (self.bin / "gh").chmod(0o755)
        return repo

    def script(self, repo, name, args=(), ok=True):
        result = subprocess.run(["bash", str(repo / name), *args], env=self.env, cwd=repo, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_bootstrap_fresh_home_installs_object_and_helpers(self):
        repo = self.script_repo()
        wanted = {"packages": [{"source": "npm:rotation@1.5.3", "extensions": ["+dist/index.js"]}], "theme": "system"}
        self.write(repo / "home/settings.json", wanted)
        self.script(repo, "bootstrap.sh")
        self.assertEqual(json.loads(self.live.read_text()), wanted)
        self.assertTrue((self.agent / "pi-btw.json").exists())
        self.assertFalse((self.home / ".config/ponytail").exists())
        self.assertIn(["install", "npm:rotation@1.5.3", "--no-approve"], [c["argv"] for c in self.calls()])

    def test_bootstrap_install_failure_stops_before_content(self):
        repo = self.script_repo()
        self.write(repo / "home/settings.json", {"packages": ["npm:missing"]})
        self.env["FAKE_PI_FAIL_INSTALL"] = "npm:missing"
        self.script(repo, "bootstrap.sh", ok=False)
        self.assertTrue(self.pending.exists())
        self.assertFalse((self.agent / "subagents.json").exists())

    def test_bootstrap_missing_sources_fails_before_pi(self):
        repo = self.script_repo()
        self.script(repo, "bootstrap.sh", ok=False)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.agent.exists())

    def test_rebuild_reconciles_before_updating_wanted_list(self):
        repo = self.script_repo()
        self.write(self.live, {"packages": ["npm:retired", "npm:rotation@1.0.0"]})
        self.installed("retired", "1.0.0")
        self.installed("rotation", "1.0.0")
        wanted = {"packages": [{"source": "npm:rotation@1.5.3", "extensions": []}]}
        self.write(repo / "home/settings.json", wanted)
        self.script(repo, "rebuild.sh")
        calls = self.calls()
        self.assertEqual([c["argv"][0] for c in calls], ["remove", "install", "update"])
        self.assertEqual(calls[-1]["settings"], wanted)
        self.assertEqual(calls[-1]["argv"], ["update", "--all", "--no-approve"])
        self.assertEqual(json.loads(self.live.read_text()), wanted)

    def test_rebuild_failed_removal_prevents_update(self):
        repo = self.script_repo()
        self.write(self.live, {"packages": ["npm:retired"]})
        self.write(repo / "home/settings.json", {"packages": []})
        self.env["FAKE_PI_FAIL_REMOVE"] = "npm:retired"
        self.script(repo, "rebuild.sh", ok=False)
        self.assertTrue(self.pending.exists())
        self.assertEqual([c["argv"][0] for c in self.calls()], ["remove"])

    def test_sync_only_neither_replaces_settings_nor_runs_pi(self):
        repo = self.script_repo()
        live = {"packages": ["npm:live"], "theme": "system"}
        self.write(self.live, live)
        self.write(repo / "home/settings.json", {"packages": ["npm:repo"]})
        self.script(repo, "rebuild.sh", ("--sync-only",))
        self.assertEqual(json.loads(self.live.read_text()), live)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.pending.exists())

    def test_config_copy_failure_is_fatal(self):
        repo = self.script_repo()
        self.write(repo / "home/settings.json", {"packages": []})
        (repo / "home/subagents.json").unlink()
        self.script(repo, "bootstrap.sh", ok=False)
        self.assertFalse((self.agent / "pi-btw.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
