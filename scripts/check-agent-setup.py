#!/usr/bin/env python3
"""Read-only consistency check for the linked agent setup.

Reports configured and installed versions, expected symlink targets, missing
native skills, and pstack model-map drift. It never installs, repairs, writes a
snapshot, or prints credentials. Exit status is 1 when it finds a problem.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
IS_MAC = platform.system() == "Darwin"
PSSTACK_REF = re.compile(r"git:github\.com/michael-denyer/pstack-claude@([0-9a-f]{7,40})")
PSSTACK_SKILLS = (
    "poteto-mode",
    "blast-radius",
    "benchmark-checklist",
    "tdd",
    "fix-ci",
    "interrogate",
)
PSTACK_FORBIDDEN_PROVIDERS = ("claude-code", "codex", "anthropic/")
problems = []
notes = []


def problem(message):
    problems.append(message)


def run(*command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    return result, None


def first_line(command):
    result, error = run(*command)
    if error or result is None:
        return f"unavailable ({error})"
    if result.returncode != 0:
        return f"unavailable (exit {result.returncode})"
    return (result.stdout or result.stderr).strip().splitlines()[0]


def read_json(relative):
    return json.loads((ROOT / relative).read_text())


def check_version():
    print("Versions")
    for name, command in (
        ("pi", ["pi", "--version"]),
        ("claude", ["claude", "--version"]),
        ("codex", ["codex", "--version"]),
        ("opencode", ["opencode", "--version"]),
        ("bb", ["bb", "--version"]),
    ):
        print(f"  {name:9} {first_line(command)}")


def check_pstack():
    settings = read_json("pi/settings.json")
    pin = None
    filtered = []
    for package in settings.get("packages", []):
        source = package if isinstance(package, str) else package.get("source", "")
        match = PSSTACK_REF.search(source)
        if not match:
            continue
        pin = match.group(1)
        if isinstance(package, dict):
            filtered = [Path(pattern).parent.name for pattern in package.get("skills", []) if pattern.endswith("/SKILL.md")]
    if pin is None:
        problem("pi/settings.json has no pstack git package")
        return
    print(f"  pstack pin {pin}")
    package = HOME / ".pi/agent/git/github.com/michael-denyer/pstack-claude"
    if not package.exists():
        problem(f"pstack package is not installed at {package}")
        return
    result, error = run("git", "-C", str(package), "rev-parse", "HEAD")
    if error or result is None or result.returncode != 0:
        problem("could not read the installed pstack revision")
    elif not result.stdout.strip().startswith(pin):
        problem(f"installed pstack revision {result.stdout.strip()[:12]} does not match pin {pin[:12]}")
    version = (package / "VERSION").read_text().strip() if (package / "VERSION").exists() else "unknown"
    print(f"  installed pstack {version}")
    expected = sorted(PSSTACK_SKILLS)
    actual = sorted(filtered)
    if actual != expected:
        problem(f"pstack skill filter is {actual}; expected {expected}")
    for name in PSSTACK_SKILLS:
        if not (package / "plugins/pstack/skills/name".replace("name", name) / "SKILL.md").exists():
            problem(f"pstack skill file is missing: {name}")


def check_links():
    print("Links")
    expected = [
        ("agents/AGENTS.md", ".pi/agent/AGENTS.md"),
        ("pi/settings.json", ".pi/agent/settings.json"),
        ("pi/web-search.json", ".pi/agent/web-search.json"),
        ("pi/mcp.json", ".pi/agent/mcp.json"),
        ("pi/pi-title.jsonc", ".pi/agent/pi-title.jsonc"),
        ("pi/pstack-models.md", ".pi/agent/pstack-models.md"),
        ("pi/extensions", ".pi/agent/extensions"),
        ("pi/themes", ".pi/agent/themes"),
        ("agents/skills", ".agents/skills"),
        ("opencode/opencode.json", ".config/opencode/opencode.json"),
    ]
    if (HOME / ".claude").exists():
        expected += [
            ("agents/AGENTS.md", ".claude/CLAUDE.md"),
            (f"claude/settings.{'json' if IS_MAC else 'linux.json'}", ".claude/settings.json"),
            ("claude/statusline-command.sh", ".claude/statusline-command.sh"),
        ]
        for source in sorted((ROOT / "agents/skills").iterdir()):
            if source.name != "impeccable":
                expected.append((f"agents/skills/{source.name}", f".claude/skills/{source.name}"))
    if (HOME / ".codex").exists():
        expected += [
            ("agents/AGENTS.md", ".codex/AGENTS.md"),
            (f"codex/config.{'toml' if IS_MAC else 'linux.toml'}", ".codex/config.toml"),
            ("codex/hooks.json", ".codex/hooks.json"),
            ("codex/agents/reviewer.toml", ".codex/agents/reviewer.toml"),
        ]
    if IS_MAC:
        expected += [
            ("config/.zshrc", ".zshrc"),
            ("config/.zprofile", ".zprofile"),
            ("config/.zshenv", ".zshenv"),
            ("config/starship.toml", ".config/starship.toml"),
            ("config/ghostty/config", ".config/ghostty/config"),
            ("config/herdr/config.toml", ".config/herdr/config.toml"),
            ("config/vscode/settings.json", "Library/Application Support/Code/User/settings.json"),
            ("config/vscode/keybindings.json", "Library/Application Support/Code/User/keybindings.json"),
        ]
    for source, destination in expected:
        source_path = ROOT / source
        destination_path = HOME / destination
        if not source_path.exists():
            problem(f"tracked source is missing: {source}")
        elif not destination_path.is_symlink():
            problem(f"{destination} is not a symlink (expected {source})")
        elif Path(os.path.realpath(destination_path)) != Path(os.path.realpath(source_path)):
            problem(f"{destination} points to {os.readlink(destination_path)}, expected {source}")
    print(f"  checked {len(expected)} expected links")


def check_skills():
    print("Skills")
    native = {
        "Pi Impeccable": HOME / ".pi/agent/skills/impeccable/SKILL.md",
        "Claude Impeccable": HOME / ".claude/skills/impeccable/SKILL.md",
        "shared Codex Impeccable": ROOT / "agents/skills/impeccable/SKILL.md",
        "shared Interface Design": ROOT / "agents/skills/interface-design/SKILL.md",
        "shared diff-review": ROOT / "agents/skills/diff-review/SKILL.md",
    }
    for name, path in native.items():
        if not path.exists():
            problem(f"missing native skill: {name} ({path})")
    pi_settings = read_json("pi/settings.json")
    if "-~/.agents/skills/impeccable/SKILL.md" not in pi_settings.get("skills", []):
        problem("pi/settings.json no longer excludes the shared Codex Impeccable build")

def check_models():
    print("Models")
    sheet = (ROOT / "pi/pstack-models.md").read_text()
    alias_line = re.search(r"^pi models:\s*(.+)$", sheet, re.MULTILINE)
    if not alias_line:
        problem("pi/pstack-models.md has no `pi models:` line")
        return
    aliases = {}
    for pair in alias_line.group(1).split(","):
        alias, _, model = pair.strip().partition("=")
        if alias and model:
            aliases[alias.strip()] = model.strip()
    for alias, model in aliases.items():
        if model.startswith(PSTACK_FORBIDDEN_PROVIDERS):
            problem(f"pstack alias {alias} maps to forbidden provider model {model}")
    result, error = run("pi", "--list-models")
    catalog = set()
    if error or result is None or result.returncode != 0:
        problem("could not list Pi models")
    else:
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 2 and not fields[0].startswith("provider"):
                catalog.add(f"{fields[0]}/{fields[1]}")
    store_path = HOME / ".pi/agent/models-store.json"
    store = json.loads(store_path.read_text()) if store_path.exists() else {}
    for alias, model in aliases.items():
        if catalog and model not in catalog:
            problem(f"pstack alias {alias} maps to {model}, which is not in the Pi catalog")
        provider, _, model_id = model.partition("/")
        entry = next((item for item in store.get(provider, {}).get("models", [])
                      if item.get("id") == model_id), None) if store else None
        if entry is None:
            notes.append(f"no effort metadata for {model}")
    role_efforts = []
    for line in sheet.splitlines():
        if ":" not in line or "`" in line or line.startswith(("#", "pi models:", "default effort:", "session hook:")):
            continue
        role, _, entries = line.partition(":")
        if not role.strip() or role.strip().startswith("These aliases"):
            continue
        for entry in entries.split(","):
            entry = entry.strip()
            if not entry:
                continue
            model, _, effort = entry.partition("@")
            if model not in aliases and model not in ("inherit-parent", "auto"):
                problem(f"pstack role line {role.strip()} uses unknown alias {model}")
            if effort:
                role_efforts.append((role.strip(), model, effort))
    for role, model, effort in role_efforts:
        resolved = aliases.get(model)
        if not resolved:
            continue
        provider, _, model_id = resolved.partition("/")
        entry = next((item for item in store.get(provider, {}).get("models", [])
                      if item.get("id") == model_id), None) if store else None
        if entry is not None:
            supported = entry.get("thinkingLevelMap", {}).get(effort)
            if supported is None:
                problem(f"pstack role {role} asks {model} for unsupported effort {effort}")
    print(f"  {len(aliases)} aliases, {len(role_efforts)} explicit panel efforts")


def check_config():
    print("Config")
    mcp = read_json("pi/mcp.json")
    if mcp.get("mcpServers", {}).get("fastmail", {}).get("enabled") is not False:
        problem("Fastmail is not disabled in pi/mcp.json")
    settings = read_json("pi/settings.json")
    if settings.get("defaultModel") != "gpt-6.1-sol" or settings.get("defaultThinkingLevel") != "medium":
        problem("Pi default model/effort drift from openai/gpt-6.1-sol at medium")
    for name in ("claude/settings.json", "claude/settings.linux.json"):
        path = ROOT / name
        if path.exists() and "link.sh" in path.read_text():
            problem(f"{name} still runs link.sh at startup")
    for name in ("claude/settings.json", "claude/settings.linux.json"):
        path = ROOT / name
        if path.exists() and "pstack-claude" in path.read_text():
            problem(f"{name} still references native pstack")
    for name in ("codex/config.toml", "codex/config.linux.toml"):
        path = ROOT / name
        if path.exists() and re.search(r"pstack", path.read_text(), re.IGNORECASE):
            problem(f"{name} still references native pstack")
    data_dir = HOME / ".bb-machines/diab.getbb.app"
    if data_dir.exists():
        if (data_dir / "AGENTS.md").exists() and (data_dir / "AGENTS.md").read_bytes() != (ROOT / "bb/AGENTS.md").read_bytes():
            problem("BB server AGENTS.md differs from bb/AGENTS.md")
        skills = data_dir / "skills"
        for source in sorted((ROOT / "bb/skills").iterdir()):
            target = skills / source.name / "SKILL.md"
            if not target.exists() or target.read_bytes() != (source / "SKILL.md").read_bytes():
                problem(f"BB server skill differs or is missing: {source.name}")
        if (skills / "diff-review").exists():
            problem("BB server still has the obsolete diff-review skill copy")


def main():
    print(f"Repository {ROOT}")
    print(f"Platform   {platform.system()}")
    check_version()
    check_pstack()
    check_links()
    check_skills()
    check_models()
    check_config()
    if notes:
        print("Notes")
        for note in notes:
            print(f"  {note}")
    if problems:
        print("Problems")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("OK: no drift found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
