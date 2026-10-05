#!/usr/bin/env python3
"""pi-herdr contract: @andrewjacop/pi-herdr is the only delegation package, the
worker definitions carry valid pi-herdr frontmatter, and no pi-subagents
configuration remains."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / 'pi/agents'
ROLES = ['general-purpose', 'implementer', 'explorer', 'researcher', 'reviewer', 'tester']
READ_ONLY = {
    'explorer': ['read', 'grep', 'find', 'ls'],
    'tester': ['read', 'bash'],
    'reviewer': ['read', 'bash'],
}
DENY = {
    'reviewer': ['write', 'edit'],
}


def frontmatter(path):
    block = path.read_text().partition('---\n')[2].partition('\n---')[0]
    fields = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith('#') or line[:1].isspace():
            continue
        key, _, value = line.partition(':')
        fields[key.strip()] = value.strip()
    return fields


def listed(value):
    if not value.startswith('['):
        return [item.strip() for item in value.split(',') if item.strip()]
    return [item.strip().strip('"\'') for item in value[1:-1].split(',') if item.strip()]


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / 'pi/settings.json').read_text())

    def test_herdr_package_declared(self):
        self.assertIn('npm:@andrewjacop/pi-herdr', self.settings['packages'])

    def test_subagents_package_gone(self):
        for entry in self.settings['packages']:
            source = entry['source'] if isinstance(entry, dict) else entry
            self.assertNotIn('pi-subagents', source)

    def test_no_stale_subagents_settings_block(self):
        self.assertNotIn('subagents', self.settings)

    def test_herdr_defaults_are_conservative(self):
        herdr = json.loads((ROOT / 'pi/herdr.json').read_text())
        self.assertEqual(herdr['max_parallel_agents'], 4)
        self.assertEqual(herdr["max_spawn_depth"], 2)
        self.assertEqual(herdr['notifications'], 'normal')
        self.assertTrue(herdr['workflows_enabled'])
        self.assertNotIn('agents_kill_switch', herdr)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.files = {p.stem: p for p in AGENTS.glob('*.md')}

    def test_roles_present(self):
        for role in ROLES:
            self.assertIn(role, self.files, f'missing agent definition: {role}')

    def test_worker_role_retired(self):
        self.assertNotIn('worker', self.files, 'worker merged into implementer')

    def test_spawn_disabled_everywhere(self):
        for name, path in self.files.items():
            fields = frontmatter(path)
            self.assertEqual(fields.get('spawning'), 'false', f'{name} must not spawn')
            self.assertEqual(fields.get('auto-exit'), 'true', f'{name} must auto-exit')
            self.assertEqual(fields.get('interactive'), 'false', f'{name} must be non-interactive')
            self.assertEqual(fields.get('kind'), 'pi', f'{name} must be a pi agent')

    def test_no_model_pins(self):
        # routing falls through to the parent session's model
        for name, path in self.files.items():
            self.assertNotIn('model', frontmatter(path), f'{name} must not pin a model')

    def test_read_only_roles_allowlisted(self):
        for name, expected in READ_ONLY.items():
            self.assertEqual(listed(frontmatter(self.files[name])['tools']), expected)

    def test_reviewer_denies_writes(self):
        self.assertEqual(listed(frontmatter(self.files['reviewer'])['deny-tools']), DENY['reviewer'])

    def test_no_stale_pi_subagents_keys(self):
        stale = ['advertise', 'async', 'excludeTools', 'systemPromptMode',
                 'inheritProjectContext', 'inheritGlobalContext', 'inheritSkills',
                 'defaultContext', 'allowNestedSubagents', 'allowedAgents', 'maxSubagentDepth']
        for name, path in self.files.items():
            block = path.read_text().partition('---\n')[2].partition('\n---')[0]
            for key in stale:
                self.assertFalse(re.search(rf'^{key}:', block, re.M), f'{name}: stale key {key}')

    def test_custom_workflow_retired(self):
        self.assertFalse((ROOT / 'pi/workflows/implement-review.js').exists())

    def test_no_stale_shell_config(self):
        self.assertNotIn('PI_SUBAGENT_', (ROOT / 'config/.zshrc').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
