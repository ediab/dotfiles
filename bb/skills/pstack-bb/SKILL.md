---
name: pstack-bb
description: Use inside BB whenever a pstack workflow dispatches, messages, lists, waits for, or stops workers or reviewers. Adapts delegation to BB child threads without changing the upstream workflow. Not for standalone terminal sessions or tasks that need no delegation.
---

# Pstack workers in BB

Read this before delegating inside BB. Keep pstack's workflow, required independent reviews, fresh-worker rules, and model diversity. This skill replaces pstack's native subagent tool mappings, including Pi's `agent` family, Claude Code's Agent/Task tools, and Codex's native agent tools. Use BB child threads instead. Do not call native subagent tools inside BB, even if they are available.

An explicitly requested pstack workflow authorizes the helpers it prescribes. Loading this adapter alone does not authorize delegation or additional work. The parent owns integration and verification. A worker returns requests rather than delegating further. Outside BB, use the upstream runtime mapping instead.

## Resolve the environment and role

1. Read `bb thread show --self --json` for the parent environment and its `hostId`. Read `bb guide threads` and `bb guide thread-messaging` for the current command contract.
2. Resolve the installed pstack plugin root through Pi on the execution host. Run `pi list` in the parent environment, or on the machine that will run the worker, and find the `git:github.com/michael-denyer/pstack-claude@<revision>` entry. Its path is the package root; the plugin root is `<package>/plugins/pstack`. Verify `<plugin root>/.claude-plugin/plugin.json` and `<plugin root>/skills/poteto-mode/SKILL.md` exist. Pi's package manifest points skills at `<plugin root>/skills`; use that path, not a Claude Code or Codex plugin cache.
   If the Pi package or required files are missing, stop and report the missing installation. Do not discover or fall back to a Claude Code or Codex pstack copy.
3. Read the requested role file and pass its absolute path to the worker. Pass absolute paths for every required rubric or workflow skill too, such as `<plugin root>/skills/thermo-nuclear-review/SKILL.md` for `pstack:thermo-nuclear-review-subagent`, or `<plugin root>/skills/poteto-mode/SKILL.md` for `pstack:poteto-agent`. Tell the worker to read those files in full before working. Reading only a role header and then falling back to a generic review is not a successful check. Do not copy upstream role bodies into this skill.

Map pstack agent types as follows:

| Agent type | Worker instructions |
| --- | --- |
| `pstack:poteto-agent`, `pstack:poteto-agent-<level>` | Read `agents/poteto-agent.md`. Express the effort suffix with `--reasoning-level`. |
| `pstack:comment-sicko` | Read `agents/comment-sicko.md`. |
| `pstack:thermo-nuclear-review-subagent` | Read `agents/thermo-nuclear-review-subagent.md` and the rubric at `skills/thermo-nuclear-review/SKILL.md`. |
| `pstack:thermo-nuclear-code-quality-review-subagent` | Read `agents/thermo-nuclear-code-quality-review-subagent.md` and its cited rubric. |
| `pstack:effort-<level>` | Use the task's instructions with `--reasoning-level`. |
| General-purpose, Explore, Plan | Use the task's instructions. State exploration-only or plan-only restrictions explicitly. |

## Resolve models and effort

Use the user's explicit choice first, then the Pi `pstack-models.md` sheet, then the invoked skill's defaults. On the execution host the sheet is `~/.pi/agent/pstack-models.md`; read it there rather than assuming the server and execution host share paths. Its `pi models:` line maps pstack aliases to exact Pi catalog IDs. Do not keep a second model table here.

Every pstack worker is a Pi thread. Pass `--provider pi` and an exact model ID from the Pi catalog. Never pass `claude-code`, `codex`, or another provider, and never fall back to an Anthropic model call when a mapping is missing.

Validate the resolved provider, model, and effort with `bb provider models pi --environment <id> --json`, or `bb provider models pi --machine <parent-host-id> --project "$BB_PROJECT_ID" --json` for a new worktree. Unscoped provider queries inspect the server, not necessarily the execution machine. An environment selector and a machine selector cannot be combined.

BB does not resolve pstack aliases: pass the exact catalog ID from the sheet. For `auto` or `inherit-parent`, retain the parent's actual model ID, and pass it only when the Pi catalog lists it; otherwise report a blocker. For `default effort: session`, retain the parent's actual effort, but pass only a level the resolved model lists. If the model does not support that level, use the next supported level and state the adjustment in the child brief and your report; never pass an unsupported level. A role's explicit `@level` wins over the session level.

Do not silently substitute an unavailable model or effort, collapse a diverse panel onto one model, or use `ultra`/`ultracode`, which enable additional provider orchestration. Report a blocked role and request a choice when no valid Pi mapping exists. Inherit permissions; do not escalate them to make a worker run.

## Spawn a worker

Use visible child threads by default. Workers run on the parent's machine; pass `--machine "$parent_host"` with a new worktree. Send multiline prompts through a file or quoted heredoc:

```sh
bb thread spawn --project "$BB_PROJECT_ID" --parent-self \
  --environment "$BB_ENVIRONMENT_ID" \
  --provider pi --model "$worker_model" \
  --reasoning-level "$worker_effort" --visibility visible \
  --title "$worker_title" --prompt-file - --json <<'EOF'
Read the absolute role and skill paths supplied below in full before working.
You are a worker, not the playbook owner. Spawn no threads or native subagents.
Return blockers or requests to your parent. Do only the assigned task.
[Role paths, rubric paths, objective, file pointers, restrictions, checks, expected report.]
EOF
```

Replace the placeholders with a concrete brief. Include the source revision, later directives, relevant prior findings, the expected deliverable, and the absolute role/rubric/workflow paths. A code-writing worker reports its commit IDs, checks, and remaining limitations. A reviewer reports findings with file locations and evidence. Explicitly forbid edits for a reviewer.

Choose the environment before running the command:

- **Readers and reviewers that need uncommitted changes:** use the parent's environment as above. Keep the reviewed revision stable. BB has no equivalent enforced `readonly` flag, and no-edit instructions are not a sandbox. Record `git status --porcelain`, `git diff --cached --binary`, and `git ls-files --others --exclude-standard` before and after the review; investigate unexpected changes without reverting user work.
- **Consequential reviews:** use a separate worktree at an exact checkpoint commit: `--new-environment worktree --machine "$parent_host" --base-branch "$checkpoint"`. Do not commit unrelated parent changes to manufacture a checkpoint. Verify the child environment's host and that `HEAD` equals the checkpoint before dispatch. A worktree isolates edits; it does not constrain process authority or protect credentials.
- **Writers:** replace `--environment` with `--new-environment worktree --machine "$parent_host" --base-branch "$base_ref"`. Use an exact local branch or commit that contains the intended starting state, not BB's default base. Uncommitted parent changes do not follow the worker. Preserve them and prepare the needed committed base before dispatch. Verify the child environment's host and HEAD. Never run dotfiles' `link.sh` from an experimental worktree.

Record the returned thread ID and environment ID. Do not retry a successful spawn because a worker is queued. Respect BB's concurrency limits.

## Collect, steer, and finish

- BB sends child completion and blocker notifications to the parent. When blocked on a result, use `bb thread wait <id>`, then inspect `bb thread output <id>` and relevant logs. An idle status is not proof of success. Do not poll with sleeps.
- Steer necessary corrections with `bb thread tell <id> --message-file -`. For non-urgent messages, use `--mode queue`. Keep pstack's fresh-worker rule for new tasks and fix rounds; reuse only under its documented exceptions.
- List workers with `bb thread list --parent-thread "$BB_THREAD_ID" --include-hidden --json`.
- Stop a worker with `bb thread stop <id>`, then confirm its status with `bb thread show <id> --json`. Stopping the parent does not stop its children. On cancellation, stop each active child explicitly.
- Review worker diffs and checks yourself. Integrate only the intended commits, then verify the combined result. A worker's claim is not verification, and your own review cannot replace a required independent reviewer.
- Before archiving, preserve all useful changes and inspect the environment for uncommitted work. Archive only finished workers whose work is integrated or deliberately retained. Archiving can retire managed workspaces and lose uncommitted files. Never use environment cleanup as a routine completion step.

For questions to the user, prefer BB's question tool. If a required independent reviewer cannot run, keep the review gate blocked and report why.
