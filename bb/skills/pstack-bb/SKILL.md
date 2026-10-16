---
name: pstack-bb
description: Use inside BB whenever a pstack workflow dispatches, messages, lists, waits for, or stops workers or reviewers. Adapts delegation to BB child threads without changing the upstream workflow. Not for standalone terminal sessions or tasks that need no delegation.
---

# Pstack workers in BB

Read this before delegating inside BB. Keep pstack's workflow, required independent reviews, fresh-worker rules, and model diversity. This skill replaces its native subagent tool mappings, including Pi's `agent` family, Claude Code's Agent/Task tools, and Codex's native agent tools. Use BB child threads instead. Do not call native subagent tools inside BB, even if they are available.

An explicitly requested pstack workflow authorizes the helpers it prescribes. Loading this adapter alone does not authorize delegation or additional work. The parent owns integration and verification. A worker returns requests rather than delegating further. Outside BB, use the upstream runtime mapping instead.

## Resolve the environment and role

1. Read `bb thread show --self --json` for the parent environment and its `hostId`. Read `bb guide threads` and `bb guide thread-messaging` for the current command contract.
2. Find the installed pstack copy on that execution machine through its provider's plugin/package listing, such as `pi list` or `claude plugin list`. Do not assume the server and execution machine share paths. If required role files are missing, stop and report the missing installation.
3. Read the requested role file and pass its absolute path to the worker. Also pass the absolute path of `skills/poteto-mode/SKILL.md` when the role requires it. Do not copy upstream role bodies into this skill.

Map pstack agent types as follows:

| Agent type | Worker instructions |
| --- | --- |
| `pstack:poteto-agent`, `pstack:poteto-agent-<level>` | Read `agents/poteto-agent.md`. Express the effort suffix with `--reasoning-level`. |
| `pstack:comment-sicko` | Read `agents/comment-sicko.md`. |
| `pstack:thermo-nuclear-review-subagent` | Read `agents/thermo-nuclear-review-subagent.md`. |
| `pstack:thermo-nuclear-code-quality-review-subagent` | Read `agents/thermo-nuclear-code-quality-review-subagent.md`. |
| `pstack:effort-<level>` | Use the task's instructions with `--reasoning-level`. |
| General-purpose, Explore, Plan | Use the task's instructions. State exploration-only or plan-only restrictions explicitly. |

## Resolve models and effort

Use the user's explicit choice first, then the parent runtime's `pstack-models.md`, then the invoked skill's defaults. Read that runtime's installed mapping for model aliases and effort. For Pi, this includes any `pi models:` overrides. Do not keep a second model table here.

Validate the resolved provider, model, and effort on the target machine with `bb provider list` and `bb provider models <provider> --environment <id> --json`. For a new worktree, use `--machine <parent-host-id> --project "$BB_PROJECT_ID"` instead of `--environment`. An environment selector and a machine selector cannot be combined.

Prefer `claude-code` for Claude-family models unless the user explicitly selects another provider. For GPT models, retain the intended runtime/provider when available. BB does not resolve pstack aliases: pass the catalog's exact model ID. Honor `auto` and `inherit-parent` by retaining the parent's actual provider and model, not a remembered project default. For `default effort: session`, retain the parent's actual effort. Resolve unknown parent settings before spawning; do not guess.

Pass provider, model, and reasoning level explicitly. Do not silently substitute an unavailable model or effort, collapse a diverse panel onto one model, or use `ultra`/`ultracode`, which enable additional provider orchestration. Report a blocked role and request a choice when no valid mapping exists. Inherit permissions; do not escalate them to make a worker run.

## Spawn a worker

Use visible child threads by default. Send multiline prompts through a file or quoted heredoc:

```sh
bb thread spawn --project "$BB_PROJECT_ID" --parent-self \
  --environment "$BB_ENVIRONMENT_ID" \
  --provider "$worker_provider" --model "$worker_model" \
  --reasoning-level "$worker_effort" --visibility visible \
  --title "$worker_title" --prompt-file - --json <<'EOF'
Read the absolute role and skill paths supplied below before working.
You are a worker, not the playbook owner. Spawn no threads or native subagents.
Return blockers or requests to your parent. Do only the assigned task.
[Role paths, objective, file pointers, restrictions, checks, expected report.]
EOF
```

Replace the placeholders with a concrete brief. Include the source revision, later directives, relevant prior findings, and the expected deliverable. A code-writing worker reports its commit IDs, checks, and remaining limitations. A reviewer reports findings with file locations and evidence. Explicitly forbid edits for a reviewer.

Choose the environment before running the command:

- **Readers and reviewers:** use the parent's environment as above when they need its uncommitted changes. Keep the reviewed revision stable. BB has no equivalent enforced `readonly` flag. Record tracked diffs, staged diffs, and untracked-file state before and after review; investigate unexpected changes without reverting user work.
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
