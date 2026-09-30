#!/usr/bin/env bash
# Configuration-only component deployment, isolated from real HOME/network/services.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-app-deploy-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
fail() { echo "FAIL: $*" >&2; exit 1; }

REPO="$WORK/repo"
FAKE_BIN="$WORK/bin"
export CALL_LOG="$WORK/calls.log" FORBIDDEN_LOG="$WORK/forbidden.log"
mkdir -p "$REPO/config/vps" "$REPO/config/druk" "$FAKE_BIN"
cp "$ROOT/config/vps/deploy-vps.sh" "$REPO/config/vps/"
for f in .zshrc .zshenv .p10k.zsh .tmux.conf apps-AGENTS.md; do
    cp "$ROOT/config/vps/$f" "$REPO/config/vps/$f"
done
cp "$ROOT/config/druk/deploy-druk.sh" "$ROOT/config/druk/pi-opener.config.yaml" "$REPO/config/druk/"
printf '{"selected": "repo", "otherSelected": false}\n' > "$REPO/config/druk/settings.partial.json"
printf 'never-install-this-extension\n' > "$REPO/config/druk/extensions.txt"

cat > "$FAKE_BIN/ssh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\n' "$*" >> "$CALL_LOG"
[ "$1" = test-host ] || { echo "unexpected SSH host: $1" >&2; exit 80; }
shift
if [ "${FAIL_STAGE:-}" = yes ] && [[ "$*" == *mktemp* ]]; then exit 81; fi
# SSH joins command arguments and passes stdin to the remote shell.
HOME="$REMOTE_HOME" bash --noprofile --norc -c "$*"
SH
cat > "$FAKE_BIN/scp" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf 'scp %s\n' "$*" >> "$CALL_LOG"
[ "$1" != -q ] || shift
source="$1" destination="$2"
[ "${FAIL_SCP:-}" != "$(basename "$source")" ] || exit 82
case "$destination" in
    test-host:*) destination="${destination#test-host:}" ;;
    *) echo "unexpected SCP destination: $destination" >&2; exit 83 ;;
esac
cp "$source" "$destination"
SH
cat > "$FAKE_BIN/tmux" <<'SH'
#!/usr/bin/env bash
printf 'tmux %s\n' "$*" >> "$CALL_LOG"
# No existing server is an allowed condition, not a reason to launch one.
exit 1
SH
cat > "$FAKE_BIN/forbidden" <<'SH'
#!/usr/bin/env bash
printf '%s %s\n' "$(basename "$0")" "$*" >> "$FORBIDDEN_LOG"
exit 90
SH
chmod +x "$FAKE_BIN/ssh" "$FAKE_BIN/scp" "$FAKE_BIN/tmux" "$FAKE_BIN/forbidden"
for command in curl wget sudo systemctl loginctl apt apt-get npm npx brew pi git druk install service docker; do
    ln -s forbidden "$FAKE_BIN/$command"
done
export PATH="$FAKE_BIN:$PATH"

new_case() {
    [ ! -s "$FORBIDDEN_LOG" ] || fail 'previous case ran a forbidden operational command'
    CASE="$WORK/$1"
    export HOME="$CASE/local" REMOTE_HOME="$CASE/remote"
    mkdir -p "$HOME" "$REMOTE_HOME"
    : > "$CALL_LOG"
    : > "$FORBIDDEN_LOG"
    unset FAIL_SCP FAIL_STAGE
}
run_vps() { VPS_HOST=test-host bash "$REPO/config/vps/deploy-vps.sh" "$@"; }
run_druk() { DEPLOY_DRUK_HOST="${DRUK_HOST:-}" bash "$REPO/config/druk/deploy-druk.sh" "$@"; }
expect_failure() {
    if "$@" > "$CASE/failure.out" 2>&1; then fail "unexpected success: $*"; fi
    [ ! -s "$FORBIDDEN_LOG" ] || fail "forbidden commands ran"
}
assert_no_stage() {
    [ -z "$(find "$REMOTE_HOME" -maxdepth 1 -name '.dotfiles-*' -print)" ] || fail "remote stage leaked"
}
seed_druk() {
    mkdir -p "$1/.config/druk/extensions/foreign" "$1/.config/pi-opener"
    printf '{"selected": "live", "otherSelected": 0, "theme": "local-theme", "windowState": {"x": 4}}\n' > "$1/.config/druk/config.json"
    chmod 640 "$1/.config/druk/config.json"
    printf 'old opener\n' > "$1/.config/pi-opener/config.yaml"
    printf 'foreign extension\n' > "$1/.config/druk/extensions/foreign/extension.json"
}
assert_druk() {
    python3 - "$1" "$REPO/config/druk/pi-opener.config.yaml" <<'PY'
import json, pathlib, stat, sys
home = pathlib.Path(sys.argv[1])
settings = home / '.config/druk/config.json'
assert json.loads(settings.read_text()) == {
    'selected': 'repo', 'otherSelected': False,
    'theme': 'local-theme', 'windowState': {'x': 4}}
assert json.loads(settings.read_text())['otherSelected'] is False
assert stat.S_IMODE(settings.stat().st_mode) == 0o640
backups = list(settings.parent.glob('config.json.backup.*'))
assert len(backups) == 1
assert json.loads(backups[0].read_text())['selected'] == 'live'
opener = home / '.config/pi-opener/config.yaml'
assert opener.read_bytes() == pathlib.Path(sys.argv[2]).read_bytes()
backups = list(opener.parent.glob('config.yaml.backup.*'))
assert len(backups) == 1 and backups[0].read_text() == 'old opener\n'
assert (home / '.config/druk/extensions/foreign/extension.json').read_text() == 'foreign extension\n'
assert not (home / '.config/druk/extensions/never-install-this-extension').exists()
PY
}

# Shell/app-root copy, backups, private zshrc mode, and maintenance untouched.
new_case vps
mkdir -p "$REMOTE_HOME/apps" "$REMOTE_HOME/bin" "$REMOTE_HOME/.config/systemd/user" "$REMOTE_HOME/apt"
for f in .zshrc .zshenv .p10k.zsh .tmux.conf; do printf 'old %s\n' "$f" > "$REMOTE_HOME/$f"; done
printf 'old apps\n' > "$REMOTE_HOME/apps/AGENTS.md"
for f in bin/vps-cleanup.sh bin/vps-update-images.sh .config/systemd/user/vps-cleanup.timer .config/systemd/user/herdr-server.service apt/51-vps-auto-updates; do
    printf 'existing operational asset\n' > "$REMOTE_HOME/$f"
done
run_vps > "$CASE/success.out" 2>&1 || { cat "$CASE/success.out"; fail 'VPS configuration deploy'; }
for f in .zshrc .zshenv .p10k.zsh .tmux.conf; do
    cmp "$REPO/config/vps/$f" "$REMOTE_HOME/$f" || fail "VPS $f copy"
done
cmp "$REPO/config/vps/apps-AGENTS.md" "$REMOTE_HOME/apps/AGENTS.md" || fail 'app-root copy'
python3 - "$REMOTE_HOME" <<'PY'
from pathlib import Path
import stat, sys
home = Path(sys.argv[1])
assert stat.S_IMODE((home / '.zshrc').stat().st_mode) == 0o600
for name in ('.zshrc', '.zshenv', '.p10k.zsh', '.tmux.conf', 'apps/AGENTS.md'):
    path = home / name
    backups = list(path.parent.glob(path.name + '.backup.*'))
    assert len(backups) == 1
    expected = 'old apps\n' if name == 'apps/AGENTS.md' else 'old %s\n' % name
    assert backups[0].read_text() == expected
for name in ('bin/vps-cleanup.sh', 'bin/vps-update-images.sh', '.config/systemd/user/vps-cleanup.timer', '.config/systemd/user/herdr-server.service', 'apt/51-vps-auto-updates'):
    assert (home / name).read_text() == 'existing operational asset\n'
PY
[ ! -s "$FORBIDDEN_LOG" ] || fail 'VPS operational command ran'
grep -Fq 'tmux source-file' "$CALL_LOG" || fail 'tmux reload not attempted'
assert_no_stage
run_vps > "$CASE/repeat.out" 2>&1 || fail 'repeat VPS deploy'
[ "$(find "$REMOTE_HOME" -name '*.backup.*' | wc -l | tr -d ' ')" = 5 ] || fail 'unchanged VPS copies created backups'

new_case vps-new
run_vps > "$CASE/success.out" 2>&1 || fail 'VPS deploy into missing apps directory'
cmp "$REPO/config/vps/apps-AGENTS.md" "$REMOTE_HOME/apps/AGENTS.md" || fail 'missing apps directory not created'

new_case vps-transfer-failure
printf 'original zshrc\n' > "$REMOTE_HOME/.zshrc"
export FAIL_SCP=.p10k.zsh
expect_failure run_vps
[ "$(cat "$REMOTE_HOME/.zshrc")" = 'original zshrc' ] || fail 'failed upload changed live zshrc'
[ ! -e "$REMOTE_HOME/.zshenv" ] || fail 'failed upload changed another live file'
assert_no_stage

new_case vps-invalid-target
mkdir "$REMOTE_HOME/.zshrc"
expect_failure run_vps
[ -d "$REMOTE_HOME/.zshrc" ] || fail 'directory destination replaced'
[ -z "$(find "$REMOTE_HOME/.zshrc" -type f -print)" ] || fail 'configuration moved into directory destination'
assert_no_stage

new_case vps-missing-source
mv "$REPO/config/vps/apps-AGENTS.md" "$CASE/apps-AGENTS.md"
expect_failure run_vps
[ ! -s "$CALL_LOG" ] || fail 'missing source contacted remote'
mv "$CASE/apps-AGENTS.md" "$REPO/config/vps/apps-AGENTS.md"

# Local merge preserves non-selected keys, foreign extensions, and originals.
new_case druk-local
seed_druk "$HOME"
run_druk > "$CASE/success.out" 2>&1 || { cat "$CASE/success.out"; fail 'local druk'; }
assert_druk "$HOME"
[ ! -s "$CALL_LOG" ] || fail 'local druk contacted remote'
run_druk > "$CASE/repeat.out" 2>&1 || fail 'repeat local druk'
assert_druk "$HOME"
[ ! -s "$FORBIDDEN_LOG" ] || fail 'druk installation attempted'

new_case druk-json-types
seed_druk "$HOME"
printf '{"selected": "repo", "otherSelected": 0}\n' > "$HOME/.config/druk/config.json"
run_druk > "$CASE/success.out" 2>&1 || fail 'druk JSON type change'
python3 - "$HOME/.config/druk/config.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1]))['otherSelected'] is False
PY

new_case druk-matching-format
seed_druk "$HOME"
printf '{ "selected":"repo", "otherSelected":false, "theme":"local-theme", "windowState":{"x":4} }\n' > "$HOME/.config/druk/config.json"
cp "$HOME/.config/druk/config.json" "$CASE/original.json"
run_druk > "$CASE/success.out" 2>&1 || fail 'matching druk settings'
cmp "$CASE/original.json" "$HOME/.config/druk/config.json" || fail 'matching settings reformatted'
[ -z "$(find "$HOME/.config/druk" -name 'config.json.backup.*' -print)" ] || fail 'matching settings backed up'

new_case druk-remote
seed_druk "$HOME"
seed_druk "$REMOTE_HOME"
DRUK_HOST=test-host run_druk > "$CASE/success.out" 2>&1 || { cat "$CASE/success.out"; fail 'remote druk'; }
assert_druk "$HOME"
assert_druk "$REMOTE_HOME"
assert_no_stage
[ ! -s "$FORBIDDEN_LOG" ] || fail 'remote druk installation attempted'

new_case druk-new
DRUK_HOST=test-host run_druk > "$CASE/success.out" 2>&1 || fail 'druk missing config'
for home in "$HOME" "$REMOTE_HOME"; do
    cmp "$REPO/config/druk/pi-opener.config.yaml" "$home/.config/pi-opener/config.yaml" || fail 'new opener config'
    python3 - "$home/.config/druk/config.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1])) == {'selected': 'repo', 'otherSelected': False}
PY
done
assert_no_stage

# Malformed JSON or non-object settings fail, never replace preferences with {}.
for value in '{bad json' '[]' 'null' '42' '{"number": NaN}'; do
    new_case "druk-invalid-${value//[^a-zA-Z0-9]/_}"
    seed_druk "$HOME"
    printf '%s\n' "$value" > "$HOME/.config/druk/config.json"
    cp "$HOME/.config/druk/config.json" "$CASE/original.json"
    expect_failure run_druk
    cmp "$CASE/original.json" "$HOME/.config/druk/config.json" || fail 'invalid live JSON changed'
    [ "$(cat "$HOME/.config/pi-opener/config.yaml")" = 'old opener' ] || fail 'invalid JSON changed opener'
    [ ! -s "$CALL_LOG" ] || fail 'invalid local JSON contacted remote'
done

for value in '{bad json' '[]'; do
    new_case "druk-invalid-partial-${value//[^a-zA-Z0-9]/_}"
    seed_druk "$HOME"
    cp "$REPO/config/druk/settings.partial.json" "$CASE/partial.json"
    cp "$HOME/.config/druk/config.json" "$CASE/original.json"
    printf '%s\n' "$value" > "$REPO/config/druk/settings.partial.json"
    expect_failure run_druk
    cmp "$CASE/original.json" "$HOME/.config/druk/config.json" || fail 'invalid partial changed live settings'
    [ "$(cat "$HOME/.config/pi-opener/config.yaml")" = 'old opener' ] || fail 'invalid partial changed opener'
    mv "$CASE/partial.json" "$REPO/config/druk/settings.partial.json"
done

for value in 'not json' '[]'; do
    new_case "druk-invalid-remote-${value//[^a-zA-Z0-9]/_}"
    seed_druk "$HOME"
    seed_druk "$REMOTE_HOME"
    printf '%s\n' "$value" > "$REMOTE_HOME/.config/druk/config.json"
    expect_failure env DEPLOY_DRUK_HOST=test-host bash "$REPO/config/druk/deploy-druk.sh"
    [ "$(cat "$REMOTE_HOME/.config/druk/config.json")" = "$value" ] || fail 'invalid remote JSON changed'
    [ "$(cat "$REMOTE_HOME/.config/pi-opener/config.yaml")" = 'old opener' ] || fail 'invalid remote JSON changed opener'
    assert_druk "$HOME" # local and remote actions are independent, not a distributed transaction
    assert_no_stage
done

new_case druk-unreadable-live
seed_druk "$HOME"
rm "$HOME/.config/druk/config.json"
mkdir "$HOME/.config/druk/config.json" # A non-readable-as-file destination is not missing JSON.
expect_failure run_druk
[ -d "$HOME/.config/druk/config.json" ] || fail 'unreadable live path was replaced'
[ "$(cat "$HOME/.config/pi-opener/config.yaml")" = 'old opener' ] || fail 'read failure changed opener'

new_case druk-remote-transfer-failure
seed_druk "$HOME"
seed_druk "$REMOTE_HOME"
cp "$REMOTE_HOME/.config/druk/config.json" "$CASE/original.json"
export FAIL_SCP=pi-opener.config.yaml
expect_failure env DEPLOY_DRUK_HOST=test-host bash "$REPO/config/druk/deploy-druk.sh"
cmp "$CASE/original.json" "$REMOTE_HOME/.config/druk/config.json" || fail 'failed upload changed remote settings'
[ "$(cat "$REMOTE_HOME/.config/pi-opener/config.yaml")" = 'old opener' ] || fail 'failed upload changed remote opener'
assert_no_stage

new_case invalid-arguments
expect_failure run_vps --typo
expect_failure run_druk --typo
[ ! -s "$CALL_LOG" ] || fail 'invalid argument contacted remote'
[ ! -d "$HOME/.config" ] || fail 'invalid argument wrote config'

new_case staging-failure
export FAIL_STAGE=yes
expect_failure run_vps
[ ! -e "$REMOTE_HOME/.zshrc" ] || fail 'staging failure changed remote config'
expect_failure env DEPLOY_DRUK_HOST=test-host bash "$REPO/config/druk/deploy-druk.sh"
[ ! -d "$REMOTE_HOME/.config" ] || fail 'staging failure changed remote druk'

# Check actual sources as well as command execution: inventories/assets remain intact.
python3 - "$ROOT/config/druk/settings.partial.json" <<'PY'
import json, sys
assert isinstance(json.load(open(sys.argv[1])), dict)
PY
[ -f "$ROOT/config/druk/extensions.txt" ] || fail 'extension inventory removed'
echo 'app deployment tests passed.'
