#!/usr/bin/env python3
"""Preview portable preference restoration; --apply explicitly performs writes."""
import argparse
import json
import shlex
from pathlib import Path
from common import preference_commands, run_bb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="Explicit target BB server URL")
    parser.add_argument("--bb", default="bb", help="BB CLI executable")
    parser.add_argument("--apply", action="store_true", help="Write preferences (default: preview)")
    args = parser.parse_args()
    preferences = json.loads(Path(__file__).with_name("preferences.json").read_text())
    commands = preference_commands(preferences)
    print(f"Target: {args.server}")
    if args.apply:
        run_bb(args.bb, args.server, ["settings", "show", "--json"])
    for command in commands:
        print(shlex.join([args.bb, *command]))
        if args.apply:
            run_bb(args.bb, args.server, command, capture=False)
    print("Applied preferences." if args.apply else "Preview only. Add --apply to write. Install required plugins first.")


if __name__ == "__main__":
    main()
