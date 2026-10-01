#!/usr/bin/env python3
"""Portable configuration and optional integration behavior, using a fake HOME."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PortableSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dotfiles-portable-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home with spaces'
        self.home.mkdir()
        self.bin = Path(self.temp.name) / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin))

    def hook(self, *args, input='{}'):
        return subprocess.run(['/bin/bash', str(ROOT / 'scripts/agent-hook.sh'), *args],
                              input=input, text=True, capture_output=True, env=self.env)

    def test_absent_optional_integrations_are_noops(self):
        for helper in ['gh-axi', 'lavish-axi', 'chrome-devtools-axi', 'claude', 'codex']:
            result = self.hook(helper, 'session')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')

    def test_installed_helper_receives_arguments_and_hook_input(self):
        helper = self.bin / 'gh-axi'
        helper.write_text('#!/bin/bash\nprintf "%s\\n" "$1"\nIFS= read -r line; printf "%s\\n" "$line"\n')
        helper.chmod(0o755)
        result = self.hook('gh-axi', 'session', input='{"session_id":"test"}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'session\n{"session_id":"test"}\n')

    def test_installed_herdr_hook_uses_home_path(self):
        self.env['PATH'] = '/usr/bin:/bin'
        for client, rel in [('claude', '.claude/hooks/herdr-agent-state.sh'),
                            ('codex', '.codex/herdr-agent-state.sh')]:
            hook = self.home / rel
            hook.parent.mkdir(parents=True)
            hook.write_text('printf "%s\\n" "$1"\n')
            result = self.hook(client, 'session')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'session\n')

    def test_unknown_hook_is_an_error(self):
        self.assertEqual(self.hook('typo').returncode, 2)

    def test_linux_claude_keeps_shared_behavior_without_mac_server(self):
        mac = json.loads((ROOT / 'claude/settings.json').read_text())
        linux = json.loads((ROOT / 'claude/settings.linux.json').read_text())
        mac.pop('mcpServers')
        self.assertEqual(mac, linux)
        self.assertNotIn('/Users/', json.dumps(linux))
        self.assertNotIn('/opt/homebrew/', json.dumps(linux))

    def test_linux_codex_keeps_shared_settings_and_vps_trust(self):
        mac = tomllib.loads((ROOT / 'codex/config.toml').read_text())
        linux = tomllib.loads((ROOT / 'codex/config.linux.toml').read_text())
        for key in ['model', 'model_reasoning_effort', 'plan_mode_reasoning_effort',
                    'features', 'memories']:
            self.assertEqual(mac[key], linux[key], key)
        self.assertEqual(linux['projects']['/home/diab']['trust_level'], 'trusted')
        self.assertEqual(set(linux['mcp_servers']), {'context7'})
        text = json.dumps(linux)
        for prefix in ['/Users/', '/opt/homebrew/', '/Applications/']:
            self.assertNotIn(prefix, text)

    def test_context7_header_helper_reads_host_env_not_fixed_home(self):
        linux = tomllib.loads((ROOT / 'codex/config.linux.toml').read_text())
        self.env['PATH'] = '/usr/bin:/bin'
        (self.home / '.env').write_text('OTHER_KEY=irrelevant\nCONTEXT7_API_KEY=test-only-key\n')
        result = subprocess.run(linux['mcp_servers']['context7']['http_headers_helper'],
                                shell=True, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'CONTEXT7_API_KEY': 'test-only-key'})

    def test_statusline_renders_git_on_host_platform_and_reruns(self):
        env = dict(os.environ, HOME=str(self.home), TMPDIR=self.temp.name, CC_SL_NERD='0')
        payload = json.dumps({'workspace': {'current_dir': str(ROOT)},
                              'model': {'display_name': 'test-model'}})
        for _ in range(2):
            result = subprocess.run(['/bin/bash', str(ROOT / 'claude/statusline-command.sh')],
                                    input=payload, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            self.assertIn('test-model', result.stdout)
            self.assertIn('⎇', result.stdout)  # Git segment rendered, not just the model.


if __name__ == '__main__':
    unittest.main(verbosity=2)
