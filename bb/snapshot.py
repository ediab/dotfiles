#!/usr/bin/env python3
"""Capture allowlisted preferences, never the entire BB settings response."""
import argparse
import json
from pathlib import Path
from common import portable_preferences, run_bb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="Explicit BB server URL")
    parser.add_argument("--bb", default="bb", help="BB CLI executable")
    args = parser.parse_args()
    settings = run_bb(args.bb, args.server, ["settings", "show", "--json"])
    ui = run_bb(args.bb, args.server, ["settings", "ui", "list", "--json"])
    data = portable_preferences(settings, ui)
    path = Path(__file__).with_name("preferences.json")
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {path}. Review the diff before committing; plugin inventory is maintained separately.")


if __name__ == "__main__":
    main()
