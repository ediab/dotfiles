#!/usr/bin/env python3
"""Check the researcher profile's restricted tool scope and its web-tool provider."""
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'pi/agents/researcher.md'
EXPECTED_EXCLUDES = ['bash', 'edit', 'write']


def frontmatter(path):
    """Return the leading --- block as a field mapping (inline lists only)."""
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


class ResearcherTests(unittest.TestCase):
    def setUp(self):
        self.fields = frontmatter(PROFILE)

    def test_restricted_tools(self):
        # pi-subagents 0.74.0 cannot honour a `tools` allowlist on Pi 0.99.2, so the
        # researcher's scope is a denylist over the child's default tools.
        self.assertNotIn('tools:', PROFILE.read_text())
        self.assertEqual(listed(self.fields['excludeTools']), EXPECTED_EXCLUDES)

    def test_web_tools_come_from_ambient_providers(self):
        # Foreground children cannot load providers, so the researcher runs as a
        # background child, where pi-web-access registers the web tools.
        self.assertEqual(self.fields['async'], 'true')
        self.assertNotIn('extensions', self.fields)

    def test_no_tintin_extension_selectors(self):
        self.assertIsNone(re.search(r'"ext:', PROFILE.read_text()))

    def test_source_check_stays_disabled(self):
        # web-search.json disables source_check; the profile must not require it.
        self.assertNotIn('source_check', PROFILE.read_text().partition('---\n')[2].partition('\n---')[0])
        self.assertIn('inspect the original source directly', PROFILE.read_text())

    def test_web_provider_is_installed(self):
        provider = Path(os.path.expanduser('~/.pi/agent/npm/node_modules/pi-web-access/dist/index.js'))
        if not provider.exists():
            self.skipTest(f'Installed pi-web-access is required for this check (missing {provider})')
        self.assertTrue(provider.is_file())

    def test_web_enable_is_documented(self):
        self.assertIn('web_enable', PROFILE.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
