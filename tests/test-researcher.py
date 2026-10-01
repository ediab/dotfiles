#!/usr/bin/env python3
"""Check restricted researcher configuration against the installed extension matcher."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResearcherTests(unittest.TestCase):
    def test_restricted_tools(self):
        text = (ROOT / 'pi/agents/researcher.md').read_text()
        tools = next(line for line in text.splitlines() if line.startswith('tools:'))
        self.assertEqual(tools, 'tools: [read, "ext:pi-web-access/web_search", "ext:pi-web-access/fetch_content", "ext:pi-web-access/get_search_content", "ext:pi-web-access/source_check"]')
        self.assertIn('skills: false', text)
        self.assertIn('disabled, unavailable, or fails', text)

    def test_entry_matches_extension_selectors(self):
        installed = Path.home() / '.pi/agent/npm/node_modules'
        runner = installed / '@tintinweb/pi-subagents/dist/agent-runner.js'
        if not runner.exists() or not shutil.which('node'):
            self.skipTest('Installed pi-subagents and Node are required for the matcher check')
        # Isolate the actual pure matcher. Importing the whole runner outside Pi would
        # require Pi's host-supplied peer dependency resolver and create a false failure.
        script = r'''
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
const profile = readFileSync(process.env.PROFILE, 'utf8');
const field = profile.split('\n').find(line => line.startsWith('extensions:'));
const entries = JSON.parse(field.slice('extensions:'.length));
assert.equal(entries.length, 1);
const entry = entries[0].replace(/^~\//, process.env.HOME + '/');
assert(existsSync(entry), 'Research extension source entry is missing');
const source = readFileSync(process.env.RUNNER, 'utf8');
const start = source.indexOf('export function extensionCanonicalName(');
const end = source.indexOf('export function parseExtensionsSpec(', start);
assert(start >= 0 && end > start, 'Installed matcher changed; recheck its contract');
const prefix = 'import {readFileSync} from "node:fs"; import {basename,dirname,resolve} from "node:path";\n';
const module = await import('data:text/javascript;base64,' + Buffer.from(prefix + source.slice(start, end)).toString('base64'));
assert(module.extensionCanonicalNames(entry).includes('pi-web-access'), 'Web extension cannot match the profile tool selectors');
'''
        result = subprocess.run(['node', '--input-type=module'], input=script, text=True,
                                capture_output=True, env=dict(os.environ,
                                PROFILE=str(ROOT / 'pi/agents/researcher.md'), RUNNER=str(runner)))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
