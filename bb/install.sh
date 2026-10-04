#!/usr/bin/env bash
# Explicit npm runtime update; never alters the desktop app, services, or BB data.
set -euo pipefail
version="${1:-latest}"
case "$version" in
  latest) ;;
  *) [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Use latest or a stable X.Y.Z version.' >&2; exit 1; } ;;
esac
runtime="${BB_RUNTIME_DIR:-$HOME/apps/bb-runtime}"
mkdir -p "$runtime"
node - "$runtime/package.json" <<'JS'
const fs = require('node:fs');
const path = process.argv[2];
const config = fs.existsSync(path) ? JSON.parse(fs.readFileSync(path, 'utf8')) : { private: true };
config.allowScripts = { ...config.allowScripts, 'better-sqlite3': true, 'node-pty': true, '@parcel/watcher': true };
fs.writeFileSync(path, JSON.stringify(config, null, 2) + '\n');
JS
npm install --prefix "$runtime" "bb-app@$version" --no-audit --no-fund
node "$runtime/node_modules/bb-app/dist/bb.js" --version
printf '\nRuntime installed in %s\nCLI: node %s/node_modules/bb-app/dist/bb.js\n' "$runtime" "$runtime"
printf 'A running service needs an explicit restart to use an updated runtime. The Mac desktop app is updated separately.\n'
