# Task: finish commits, push, sync VPS (dotfiles review fixes)

User instruction ("do it"): commit + push everything, then sync the VPS.

## Current state
- cwd: /Users/eliasdiab/Dev/dotfiles
- Branch: main, tracking origin/main, currently even with 57418ad.
- All review fixes are applied and staged (git add -A already run): 37 files, +372/-184.
- All tests pass: portable-settings 8/8, test-link.sh, herdr 13/13, researcher, app-deploy, bb 7/7, title-in-border 24/24.
- `link.sh` rerun: exit 0, no SKIP/FAIL lines.

## Steps to execute
1. `cd ~/Dev/dotfiles && git commit -F .claude/commit-msg.txt`(inside sandbox; GitGuardian hook works there now)
2. Outside sandbox: `git push` (needs SSH agent + permission prompt)
3. Outside sandbox: `ssh vps 'cd ~/Dev/dotfiles && git pull --ff-only && ./link.sh'` and confirm clean tree/exit 0, no SKIPs.

## Files in the commit
- P1 fixes: config/AGENTS.md + agents/skills/local-env/SKILL.md (VPS IP/user/key removed), tests/test-portable-settings.py (sandbox parity), config/.zshrc (history-substring-search bound), pi/agents/researcher.md + tests/test-researcher.py (tools allowlist)
- P2s: grilling/retro/show-me/agentsmd-for-projects (+3 openai.yaml), ATTRIBUTION.md + frontend-design/LICENSE.txt, bb/README.md + plugins.json, codex/config.linux.toml, config/vps/* deploy docs+scripts, config/druk/extensions.txt, link.sh exit-fail path, statusline cache fix
- P3s: vps-cleanup.sh APPS_DIR/run(), hard-coded VPS paths, Brewfile zsh-syntax-highlighting removed, clawdbot→openclaw, vscode bogus setting, ask-matt description, domain-modeling ADR, config/herdr/config.vps.toml header, herdr/deploy-vps.sh locking
- Cleanup: pi/settings.json drops deviceId + extensions entry (pi/extensions/ removal)

## Tag for provider
pi = true (interrupt/confirm so I can run push + ssh outside the sandbox)
