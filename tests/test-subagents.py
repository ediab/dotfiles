#!/usr/bin/env python3
"""Migration contract: pi-subagents (Nico) replaces @tintinweb/pi-subagents, and the
five specialist profiles carry the intended scope in the new frontmatter format."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / 'pi/agents'
ROLES = ['general-purpose', 'explorer', 'researcher', 'worker', 'reviewer']
PACKAGE = 'npm:pi-subagents@0.74.0'

TINTIN_SYNTAX = ['prompt_mode:', 'inherit_context:', 'tools: all', 'extensions: true',
                 'extensions: false', 'skills: false']
TINTIN_SELECTOR = re.compile(r'"ext:')


def frontmatter(path):
    block = path.read_text().partition('---\n')[2].partition('\n---')[0]
    fields = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, _, value = line.partition(':')
        fields[key.strip()] = value.strip()
    return fields


def listed(value):
    if not value.startswith('['):
        return [value]
    return [item.strip().strip('"\'') for item in value[1:-1].split(',') if item.strip()]


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / 'pi/settings.json').read_text())

    def test_package_declaration(self):
        entries = [entry if isinstance(entry, str) else entry.get('source')
                   for entry in self.settings['packages']]
        self.assertIn(PACKAGE, entries)
        self.assertFalse([entry for entry in entries if 'tintinweb' in str(entry)])

    def test_package_keeps_guidance_skill_and_drops_prompt_templates(self):
        entry = next(entry for entry in self.settings['packages']
                     if isinstance(entry, dict) and entry.get('source') == PACKAGE)
        self.assertEqual(entry.get('prompts'), [])
        self.assertTrue(entry.get('skills'))

    def test_builtin_roles_and_watchdog_disabled(self):
        subagents = self.settings['subagents']
        self.assertIs(subagents['disableBuiltins'], True)
        self.assertIs(subagents['watchdog']['enabled'], False)
        self.assertIs(subagents['watchdog']['children']['enabled'], False)


class RuntimeConfigTests(unittest.TestCase):
    def test_concurrency_and_depth(self):
        config = json.loads((ROOT / 'pi/extensions/subagent/config.json').read_text())
        self.assertIs(config['asyncByDefault'], False)
        self.assertEqual(config['globalConcurrencyLimit'], 4)
        self.assertEqual(config['parallel']['concurrency'], 4)
        self.assertEqual(config['maxSubagentDepth'], 2)
        self.assertEqual(config['toolDescriptionMode'], 'compact')


class ProfileTests(unittest.TestCase):
    def test_roles_present_without_retired_files(self):
        for role in ROLES:
            self.assertTrue((AGENTS / f'{role}.md').is_file(), role)
        for retired in ['Explore.md', 'Plan.md']:
            self.assertFalse((AGENTS / retired).exists(), retired)
        self.assertFalse((ROOT / 'pi/subagents.json').exists())

    def test_no_tintin_frontmatter_syntax(self):
        for role in ROLES:
            text = (AGENTS / f'{role}.md').read_text()
            for pattern in TINTIN_SYNTAX:
                self.assertNotIn(pattern, text, f'{role}.md still uses {pattern!r}')
            self.assertIsNone(TINTIN_SELECTOR.search(text), f'{role}.md still uses an ext: selector')

    def test_scope_per_role(self):
        explorer = frontmatter(AGENTS / 'explorer.md')
        self.assertEqual(explorer['model'], 'openai/gpt-6-luna')
        self.assertEqual(explorer['async'], 'true')
        self.assertEqual(listed(explorer['excludeTools']), ['edit', 'write'])

        researcher = frontmatter(AGENTS / 'researcher.md')
        self.assertEqual(researcher['async'], 'true')
        self.assertEqual(listed(researcher['excludeTools']), ['bash', 'edit', 'write'])

        worker = frontmatter(AGENTS / 'worker.md')
        self.assertEqual(listed(worker['extensions']), [])
        self.assertEqual(worker['defaultContext'], 'fork')

        reviewer = frontmatter(AGENTS / 'reviewer.md')
        self.assertEqual(listed(reviewer['extensions']), [])
        self.assertEqual(listed(reviewer['excludeTools']), ['edit', 'write'])
        self.assertEqual(reviewer['defaultContext'], 'fresh')

        general = frontmatter(AGENTS / 'general-purpose.md')
        self.assertEqual(general['allowNestedSubagents'], 'true')
        self.assertEqual(general['maxSubagentDepth'], '2')
        self.assertEqual(general['allowedAgents'], 'explorer, researcher, worker, reviewer')

    def test_no_tool_allowlists(self):
        # pi-subagents 0.74.0 fails any child launch on Pi 0.99.2 when a profile
        # declares `tools`; the scope is declared with excludeTools instead, which
        # discovery reports but this host does not enforce at child runtime.
        for role in ROLES:
            self.assertNotIn('tools:', (AGENTS / f'{role}.md').read_text(), role)

    def test_each_profile_inherits_project_context(self):
        for role in ROLES:
            self.assertIn('inheritProjectContext: true', (AGENTS / f'{role}.md').read_text(), role)


class SkillAndLinkTests(unittest.TestCase):
    def test_code_review_uses_workflow_dispatch(self):
        text = (ROOT / 'pi/skills/code-review/SKILL.md').read_text()
        self.assertIn('subagent({ workflow: true, async: false })', text)
        self.assertIn('runs.all', text)
        self.assertNotIn('inherit_context', text)

    def test_link_sh_retires_subagents_json(self):
        text = (ROOT / 'link.sh').read_text()
        self.assertIn('for f in settings web-search open-tui pi-btw mcp; do', text)
        self.assertIn('remove retired', text)

    def test_readme_names_the_runtime_config(self):
        self.assertIn('pi/extensions/subagent', (ROOT / 'README.md').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
