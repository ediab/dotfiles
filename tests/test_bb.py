"""Check BB preference boundaries and script behavior without changing a live server."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bb"))
from common import portable_preferences, preference_commands, run_bb


class BBTests(unittest.TestCase):
    def setUp(self):
        self.preferences = json.loads((ROOT / "bb/preferences.json").read_text())

    def test_snapshot_excludes_routing_secrets_and_runtime(self):
        settings = {
            "generalSettings": {"defaultProviderId": "pi", "machineServerUrl": "private",
                                "machineGitCredentialsEnabled": True},
            "appearance": {"themeId": "catppuccin", "faviconColor": "default", "customCss": "private"},
            "auth": {"token": "private"}, "primaryHostId": "private",
        }
        ui = {"preferences": {
            "sidebar.organizationMode": {"value": "chronological", "revision": 1},
            "sidebar.collapsedProjects": {"value": ["private"]},
        }}
        result = portable_preferences(settings, ui)
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(result["general"], {"defaultProviderId": "pi"})
        self.assertEqual(result["ui"], {"sidebar.organizationMode": "chronological"})

    def test_checked_in_preferences_compile(self):
        commands = preference_commands(self.preferences)
        self.assertIn(["theme", "set", "catppuccin"], commands)
        self.assertIn(["settings", "general", "providerOrder", "[]"], commands)
        self.assertIn(["settings", "ui", "set", "sidebar.threadListProvider", "bb-sidebar/inbox"], commands)

    def test_reject_nonportable_fields_before_writes(self):
        for section, key in [("general", "machineServerUrl"), ("ui", "sidebar.collapsedProjects"),
                             ("appearance", "customCss")]:
            bad = copy.deepcopy(self.preferences)
            bad[section][key] = "private"
            with self.assertRaises(ValueError):
                preference_commands(bad)

    def test_preview_does_not_invoke_cli(self):
        result = subprocess.run([sys.executable, str(ROOT / "bb/apply.py"),
                                 "--server", "http://example.invalid", "--bb", "/does/not/exist"],
                                check=True, capture_output=True, text=True)
        self.assertIn("Preview only", result.stdout)

    def test_cli_gets_explicit_server_and_no_thread_context(self):
        with tempfile.TemporaryDirectory() as directory:
            cli = Path(directory) / "bb"
            cli.write_text('#!' + sys.executable + '\nimport os,json\nprint(json.dumps({k:os.environ.get(k) for k in ["BB_SERVER_URL","BB_CLI","BB_THREAD_ID"]}))\n')
            cli.chmod(0o755)
            old = os.environ.copy()
            try:
                os.environ.update(BB_CLI="wrong-cli", BB_THREAD_ID="private")
                result = run_bb(str(cli), "http://explicit.invalid", ["settings", "show"])
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(result, {"BB_SERVER_URL": "http://explicit.invalid", "BB_CLI": None, "BB_THREAD_ID": None})

    def test_install_targets_stable_runtime_without_starting_service(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            bin_dir = directory / "bin"
            bin_dir.mkdir()
            log = directory / "npm-args"
            npm = bin_dir / "npm"
            npm.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$INSTALL_TEST_LOG"\n')
            npm.chmod(0o755)
            node = bin_dir / "node"
            # A real node validates/writes package.json; stub only the final version probe.
            real_node = subprocess.check_output(["which", "node"], text=True).strip()
            node.write_text('#!/bin/sh\nif [ "$1" = "-" ]; then exec ' + real_node + ' "$@"; fi\nprintf "0.45.0\\n"\n')
            node.chmod(0o755)
            runtime = directory / "runtime"
            env = dict(os.environ, PATH=str(bin_dir) + ":" + os.environ["PATH"],
                       BB_RUNTIME_DIR=str(runtime), INSTALL_TEST_LOG=str(log))
            subprocess.run(["bash", str(ROOT / "bb/install.sh")], env=env,
                           check=True, capture_output=True)
            self.assertEqual(log.read_text().splitlines(),
                             ["install", "--prefix", str(runtime), "bb-app@latest", "--no-audit", "--no-fund"])
            package = json.loads((runtime / "package.json").read_text())
            self.assertEqual(set(package["allowScripts"]), {"better-sqlite3", "node-pty", "@parcel/watcher"})
            result = subprocess.run(["bash", str(ROOT / "bb/install.sh"), "nightly"], env=env,
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_apply_with_mock_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            cli = Path(directory) / "bb"
            log = Path(directory) / "calls"
            cli.write_text('#!' + sys.executable + '\nimport json,sys\nfrom pathlib import Path\nwith Path(' + repr(str(log)) + ').open("a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\nprint("{}")\n')
            cli.chmod(0o755)
            subprocess.run([sys.executable, str(ROOT / "bb/apply.py"), "--server", "http://example.invalid",
                            "--bb", str(cli), "--apply"], check=True, capture_output=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(calls[0], ["settings", "show", "--json"])
            self.assertEqual(calls[1:], preference_commands(self.preferences))


if __name__ == "__main__":
    unittest.main()
