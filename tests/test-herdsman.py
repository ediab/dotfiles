#!/usr/bin/env python3
"""Pinned Herdsman package, strict portable profiles, leaf policy, and config."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROLES = {'implementer', 'researcher', 'reviewer', 'tester'}
FIELDS = {
    'name', 'enabled', 'description', 'model', 'thinking', 'systemPromptMode',
    'bodyMode', 'noTools', 'noBuiltinTools', 'tools', 'excludeTools', 'permission',
    'noSkills', 'inheritSkills', 'skills', 'noExtensions', 'extensions', 'agents',
    'inheritProjectContext', 'inheritGlobalContext',
}
ARRAYS = {'tools', 'excludeTools', 'skills', 'extensions', 'agents'}
BOOLEANS = {'enabled', 'noTools', 'noBuiltinTools', 'noSkills', 'inheritSkills',
            'noExtensions', 'inheritProjectContext', 'inheritGlobalContext'}
EXPECTED_TOOLS = {
    'implementer': ['read', 'bash', 'edit', 'write', 'grep', 'find', 'ls', 'codemode'],
    'reviewer': ['read', 'bash', 'tool_search', 'mcp__context7__*'],
    'tester': ['read', 'bash', 'tool_search', 'mcp__context7__*'],
    'researcher': ['read', 'grep', 'find', 'ls', 'ffgrep', 'fffind', 'tool_search',
                   'mcp__context7__*', 'web_enable', 'web_search', 'fetch_content',
                   'get_search_content'],
}


def frontmatter(path):
    text = path.read_text()
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError(f'{path}: missing frontmatter')
    block = text[4:].partition('\n---\n')[0]
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(':')
        if not sep or key in fields:
            raise ValueError(f'{path}: malformed or duplicate field: {line}')
        fields[key] = value.strip()
    return fields


class HerdsmanTests(unittest.TestCase):
    def test_package_and_config(self):
        settings = json.loads((ROOT / 'pi/settings.json').read_text())
        self.assertIn('npm:pi-herdsman@0.21.3', settings['packages'])
        for entry in settings['packages']:
            source = entry['source'] if isinstance(entry, dict) else entry
            for retired in ['pi-' + 'herdr', 'pi-subagents']:
                self.assertNotIn(retired, source)
        self.assertNotIn('subagents', settings)
        config = json.loads((ROOT / 'pi/pi-herdsman/config.json').read_text())
        self.assertEqual(config, {'spawnPlacement': 'split', 'autoActivateManager': False})
        self.assertFalse((ROOT / 'pi/herdr.json').exists())

    def test_profiles_are_strict_portable_leaves(self):
        profiles = {p.stem: p for p in (ROOT / 'pi/agents').glob('*.md')}
        self.assertEqual(set(profiles), ROLES)
        for name, path in profiles.items():
            with self.subTest(role=name):
                fields = frontmatter(path)
                self.assertEqual(fields['name'], name)
                self.assertLessEqual(set(fields), FIELDS)
                self.assertEqual(json.loads(fields['agents']), [])
                self.assertIn('agent', json.loads(fields['excludeTools']))
                self.assertEqual(json.loads(fields['tools']), EXPECTED_TOOLS[name])
                self.assertEqual(fields['systemPromptMode'], 'replace')
                for key in ['inheritProjectContext', 'inheritGlobalContext']:
                    self.assertEqual(fields[key], 'true')
                for key in ['noSkills', 'noExtensions']:
                    self.assertEqual(fields[key], 'false')
                self.assertNotIn('model', fields)
                for key in ARRAYS & fields.keys():
                    items = json.loads(fields[key])
                    self.assertIsInstance(items, list)
                    self.assertTrue(all(isinstance(i, str) and i for i in items))
                for key in BOOLEANS & fields.keys():
                    self.assertIn(fields[key], ['true', 'false'])

    def test_no_retired_extension_instructions(self):
        old_package = 'pi-' + 'herdr'
        old_tool = re.compile(r'\bherdr_(?:spawn|get|list|message|interrupt|resume|run|save|send|read|wait)\w*\b')
        files = [ROOT / 'README.md', ROOT / 'agents/AGENTS.md',
                 ROOT / 'agents/ATTRIBUTION.md',
                 ROOT / 'agents/skills/personal-workflow/SKILL.md']
        files += list((ROOT / 'pi/skills').glob('*/SKILL.md'))
        files += list((ROOT / 'pi/agents').glob('*.md'))
        files += list((ROOT / 'bb/skills').glob('bb-pi-*/SKILL.md'))
        for path in files:
            with self.subTest(file=path):
                text = path.read_text()
                self.assertNotIn(old_package, text)
                self.assertIsNone(old_tool.search(text))
        self.assertFalse((ROOT / 'pi/workflows').exists())

    def test_workflow_uses_released_tool_contract(self):
        text = (ROOT / 'pi/skills/orchestrate/SKILL.md').read_text()
        for tool in ['agent_delegate', 'agent_list', 'agent_reply', 'agent_steer',
                     'agent_interrupt', 'agent_continue', 'agent_transcript']:
            self.assertIn(f'`{tool}`', text)
        self.assertIn('Cap active workers at four', text)
        self.assertIn('accepts no `cwd`', text)
        self.assertIn('do not poll', text)
        for role in ['scout', 'generalist']:
            self.assertIn(f'`{role}`', text)
        for retired in ['explorer', 'general-purpose']:
            self.assertNotIn(f'`{retired}`', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
