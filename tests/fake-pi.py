#!/usr/bin/env python3
"""Network-free Pi CLI fixture; deliberately rewrites filters to test restoration."""
import json
import os
from pathlib import Path
import runpy
import shutil
import sys

sys.dont_write_bytecode = True
helper = runpy.run_path(os.environ["FAKE_PI_HELPER"])
agent = Path.home() / ".pi/agent"
settings = agent / "settings.json"
data = json.loads(settings.read_text()) if settings.exists() else {}
argv = sys.argv[1:]
with open(os.environ["FAKE_PI_LOG"], "a") as stream:
    stream.write(json.dumps({"argv": argv, "settings": data}) + "\n")
if argv == ["--version"]:
    print("0.99.1")
    sys.exit(0)
command = argv[0]
if command in ("list", "update"):
    sys.exit(0)
source = argv[1]
if source == os.environ.get("FAKE_PI_FAIL_" + command.upper()):
    print("simulated " + command + " failure", file=sys.stderr)
    sys.exit(1)
identity, installed, version = helper["package"](source, agent)
entries = data.get("packages", [])
entries = [entry for entry in entries if helper["package"](entry if isinstance(entry, str) else entry["source"], agent)[0] != identity]
if command == "install":
    installed.mkdir(parents=True, exist_ok=True)
    if identity.startswith("npm:"):
        (installed / "package.json").write_text(json.dumps({"version": version or "1.0.0"}))
    elif identity.startswith("git:"):
        (installed / ".git").mkdir(exist_ok=True)
    entries.append(source)
elif command == "remove":
    if not identity.startswith("local:") and installed.exists():
        shutil.rmtree(installed)
else:
    raise SystemExit("unexpected command: " + command)
data["packages"] = entries
helper["write_json"](settings, data)
