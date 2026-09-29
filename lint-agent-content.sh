#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
shared = root / "home/shared-skills"
pi_only = root / "home/skills"
shared_names = {p.name for p in shared.iterdir() if p.is_dir() and not p.name.startswith(".")}
pi_names = {p.name for p in pi_only.iterdir() if p.is_dir() and not p.name.startswith(".")}
errors = []

for name in sorted(shared_names & pi_names):
    errors.append(f"skill has two source owners: {name}")

# Keep this list specific to Pi's invocation syntax, tool names, and profiles.
pi_only_patterns = [
    (r"/skill:", "Pi /skill: invocation syntax"),
    (r"~/.pi/agent/", "Pi-only installation path"),
    (r"\b(?:SubagentWorkflow|TaskCreate|TaskUpdate|TaskList|TaskGet|TaskExecute|TaskStop|TaskOutput)\b", "Pi-only task/workflow tool"),
    (r"\b(?:personal-workflow|reviewer|researcher)\s+(?:skill|profile|subagent)\b", "Pi-only skill or profile dependency"),
]

skill_path = re.compile(r"((?:\.\./)+[A-Za-z0-9_-]+/SKILL\.md)")

for skill_dir in sorted(p for p in shared.iterdir() if p.is_dir() and not p.name.startswith(".")):
    for path in sorted(p for p in skill_dir.rglob("*") if p.is_file() and p.name != "ATTRIBUTION.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root).as_posix()
        for pattern, reason in pi_only_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                errors.append(f"{rel}: contains {reason}")
        for match in skill_path.finditer(text):
            ref = match.group(1)
            target = (path.parent / ref).resolve()
            if not target.is_file() or target.parent.parent != shared.resolve():
                errors.append(f"{rel}: cross-skill path {ref} leaves home/shared-skills")

for skill_dir in sorted(p for p in pi_only.iterdir() if p.is_dir() and not p.name.startswith(".")):
    for path in sorted(p for p in skill_dir.rglob("*") if p.is_file() and p.name != "ATTRIBUTION.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root).as_posix()
        for match in skill_path.finditer(text):
            ref = match.group(1)
            target = (path.parent / ref).resolve()
            referenced_name = ref.split("/")[-2]
            if referenced_name in shared_names:
                errors.append(f"{rel}: use ~/.agents/skills/{referenced_name}/SKILL.md instead of {ref}")
            elif not target.is_file() or target.parent.parent != pi_only.resolve():
                errors.append(f"{rel}: cross-skill path {ref} does not resolve to a home/skills sibling")

if errors:
    print("Agent content lint failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    sys.exit(1)

print(f"Agent content lint passed ({len(shared_names)} shared, {len(pi_names)} Pi-only skills).")
PY
