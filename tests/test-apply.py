#!/usr/bin/env python3
"""Configuration-only apply regression tests: temporary HOME, no live effects."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ('settings.json', 'web-search.json', 'subagents.json', 'open-tui.json', 'pi-btw.json')


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='dotfiles-apply-test.')
        self.addCleanup(self.work.cleanup)
        self.base = Path(self.work.name)
        self.repo = self.base / 'repo'
        self.home = self.base / 'home'
        self.live = self.home / '.pi/agent'
        self.repo.mkdir()
        (self.repo / 'home').mkdir()
        self.home.mkdir()
        shutil.copyfile(ROOT / 'apply.sh', self.repo / 'apply.sh')
        for name in CONFIGS:
            self.write(self.repo / 'home' / name, {'name': name})
        for helper in ('lint-agent-content.sh', 'sync-agent-content.sh'):
            (self.repo / helper).write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HELPER_LOG"\n')
        bin_dir = self.base / 'bin'
        bin_dir.mkdir()
        for name in ('pi', 'npm', 'brew', 'apt-get', 'git', 'ssh', 'curl', 'launchctl'):
            p = bin_dir / name
            p.write_text('#!/bin/sh\necho forbidden-command >> "$FORBIDDEN_LOG"\nexit 99\n')
            p.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                        HELPER_LOG=str(self.base / 'helper.log'), FORBIDDEN_LOG=str(self.base / 'forbidden.log'))

    def tearDown(self):
        self.assertFalse((self.base / 'forbidden.log').exists(), 'Apply invoked a forbidden command')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def run_apply(self, *args, ok=True):
        result = subprocess.run(['bash', str(self.repo / 'apply.sh'), *args], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_requires_explicit_scope_and_rejects_unknown_flags(self):
        self.run_apply(ok=False)
        self.run_apply('--sync-onyl', ok=False)
        self.run_apply('--file', '../auth.json', '--yes', ok=False)
        self.run_apply('--file', 'auth.json', '--yes', ok=False)
        self.assertFalse(self.live.exists())

    def test_preview_is_read_only_and_scope_is_exact(self):
        self.write(self.live / 'web-search.json', {'old': True})
        before = (self.live / 'web-search.json').read_bytes()
        self.run_apply('--file', 'web-search.json')
        self.assertEqual((self.live / 'web-search.json').read_bytes(), before)
        self.assertFalse((self.home / '.local').exists())
        self.assertEqual(list(self.live.iterdir()), [self.live / 'web-search.json'])

    def test_selected_file_and_backup_preserve_unrelated_content(self):
        self.write(self.live / 'web-search.json', {'old': True})
        self.write(self.live / 'settings.json', {'theme': 'local'})
        self.run_apply('--file', 'web-search.json', '--yes')
        self.assertEqual(json.loads((self.live / 'web-search.json').read_text()), {'name': 'web-search.json'})
        self.assertEqual(json.loads((self.live / 'settings.json').read_text()), {'theme': 'local'})
        backups = list((self.home / '.local/state/pi-dotfiles/backups/apply').rglob('web-search.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), {'old': True})

    def test_settings_preserve_machine_state_and_package_declarations(self):
        self.write(self.repo / 'home/settings.json', {'theme': 'repo', 'deviceId': 'other',
                   'lastChangelogVersion': 'old', 'packages': ['npm:new']})
        self.write(self.live / 'settings.json', {'theme': 'local', 'deviceId': 'this-machine',
                   'lastChangelogVersion': 'current', 'packages': ['npm:keep'], 'sessionDir': '/local/sessions'})
        result = self.run_apply('--file', 'settings.json', '--yes')
        live = json.loads((self.live / 'settings.json').read_text())
        self.assertEqual(live, {'theme': 'repo', 'deviceId': 'this-machine',
                         'lastChangelogVersion': 'current', 'packages': ['npm:keep'], 'sessionDir': '/local/sessions'})
        self.assertIn('packages', result.stdout)
        self.run_apply('--file', 'settings.json', '--include-packages', '--yes')
        self.assertEqual(json.loads((self.live / 'settings.json').read_text())['packages'], ['npm:new'])

    def test_fresh_settings_do_not_copy_identity_or_auto_enable_packages(self):
        self.write(self.repo / 'home/settings.json', {'theme': 'repo', 'deviceId': 'other', 'packages': ['npm:new']})
        self.run_apply('--file', 'settings.json', '--yes')
        live = json.loads((self.live / 'settings.json').read_text())
        self.assertNotIn('deviceId', live)
        self.assertNotIn('packages', live)

    def test_validate_all_targets_before_writing(self):
        self.write(self.live / 'web-search.json', {'old': True})
        (self.repo / 'home/subagents.json').write_text('{broken')
        self.run_apply('--file', 'web-search.json', '--file', 'subagents.json', '--yes', ok=False)
        self.assertEqual(json.loads((self.live / 'web-search.json').read_text()), {'old': True})
        self.assertFalse((self.home / '.local').exists())

    def test_json_constants_and_nonobjects_are_rejected(self):
        for invalid in ('{"bad": NaN}', '{"bad": Infinity}', '[]', 'null'):
            (self.repo / 'home/web-search.json').write_text(invalid)
            self.run_apply('--file', 'web-search.json', '--yes', ok=False)
            self.assertFalse(self.live.exists())

    def test_preview_reports_added_null_and_boolean_type_changes(self):
        self.write(self.repo / 'home/web-search.json', {'enabled': False, 'optional': None})
        self.write(self.live / 'web-search.json', {'enabled': 0})
        result = self.run_apply('--file', 'web-search.json')
        self.assertIn('changed keys: enabled, optional', result.stdout)

    def test_invalid_live_json_is_not_replaced(self):
        p = self.live / 'web-search.json'
        p.parent.mkdir(parents=True)
        p.write_text('{broken')
        self.run_apply('--file', 'web-search.json', '--yes', ok=False)
        self.assertEqual(p.read_text(), '{broken')

    def test_symlink_destination_and_parent_are_not_followed(self):
        outside = self.base / 'outside'
        self.write(outside / 'web-search.json', {'outside': True})
        self.live.mkdir(parents=True)
        (self.live / 'web-search.json').symlink_to(outside / 'web-search.json')
        self.run_apply('--file', 'web-search.json', '--yes', ok=False)
        (self.live / 'web-search.json').unlink()
        self.live.rmdir()
        self.live.symlink_to(outside, target_is_directory=True)
        self.run_apply('--file', 'web-search.json', '--yes', ok=False)
        self.assertEqual(json.loads((outside / 'web-search.json').read_text()), {'outside': True})

    def test_single_profile_and_themes_preserve_foreign_files(self):
        profile = self.repo / 'home/agents/researcher.md'
        profile.parent.mkdir()
        profile.write_text('restricted profile\n')
        self.write(self.repo / 'home/themes/terminal.json', {'name': 'terminal'})
        (self.repo / 'home/themes/LICENSE').write_text('license\n')
        self.write(self.live / 'themes/foreign.json', {'name': 'foreign'})
        self.run_apply('--file', 'agents/researcher.md', '--group', 'themes', '--yes')
        self.assertEqual((self.live / 'agents/researcher.md').read_text(), 'restricted profile\n')
        self.assertTrue((self.live / 'themes/foreign.json').exists())
        self.assertTrue((self.live / 'themes/LICENSE').exists())
        self.assertFalse((self.live / 'settings.json').exists())

    def test_agent_content_preflight_before_copies_and_explicit_apply(self):
        self.run_apply('--group', 'agent-content', '--file', 'web-search.json')
        log = (self.base / 'helper.log').read_text()
        self.assertIn('--dry-run', log)
        self.assertNotIn('--yes', log)
        helper = self.repo / 'sync-agent-content.sh'
        helper.write_text('#!/bin/sh\nexit 1\n')
        self.run_apply('--group', 'agent-content', '--file', 'web-search.json', '--yes', ok=False)
        self.assertFalse(self.live.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
