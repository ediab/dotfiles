# Sustained performance improvement

Use this branch for iterative improvement of a measurable behavior against a target. A one-off slowdown or unknown cause belongs in the diagnosis loop first.

## 1. Fix the workload and goal

Read the relevant architecture and name realistic workload dimensions: data size, history, cache state, concurrency, or device constraints. Select a case that reproduces the complaint. If none does, improve the repro rather than optimize an unrelated benchmark.

Agree one metric, its direction of improvement, a checkable target, and a time/effort budget. Correctness and simplicity outrank the number. Do not invent a minimum iteration count; repeated measurement supplies confidence, not a quota of edits.

## 2. Prove the harness and baseline

Build or reuse one repeatable command exercising the actual code path. Run contrasting realistic workloads and confirm the symptom case differs from an easier case in the expected direction. An insensitive harness needs correction before it can justify changes.

Pin the workload and measurement method: setup, warm/cold state, sample count, environment, aggregation, and units. Measure enough repetitions to characterize noise; use a median or another justified statistic, not a single lucky run. Establish a green correctness/regression gate and record the baseline before edits.

Keep the harness and conditions stable across comparisons. If the benchmark changes, rerun a comparable baseline against the unchanged implementation; never compare numbers produced by different workloads as if they were the same experiment.

## 3. Run one hypothesis at a time

Each hypothesis names a mechanism grounded in the traced architecture, such as “move parsing off startup because it delays the first response,” not “try caching.”

For each experiment:

1. Record the hypothesis and prediction in scratch notes. Note the current accepted state and preserve unrelated changes.
2. Make one scoped change. The owner implements, measures, and corrects the experiment; delegation is not required.
3. Measure baseline and candidate under comparable conditions, then run the correctness gate. Include raw samples and enough repeats to distinguish the delta from noise.
4. **Keep** only a demonstrated improvement beyond noise with the gate still green. A simplification that holds performance within noise may be kept for its reduced complexity, but report it as a simplification, not a speedup.
5. **Discard** a failed, inconclusive, or correctness-breaking optimization. Undo only this experiment's changes; avoid broad resets, stashes, or overwriting concurrent work. If changes cannot be separated safely, stop and report that.
6. Record before/after values, delta, checks, verdict, and artifact pointers. Read previous notes before the next experiment to avoid repeating rejected ideas. Do not stack unmeasured changes.

Scratch notes are a lightweight working artifact, not a new logging system or permission to commit. A faster candidate that changes required behavior is rejected even when its metric looks excellent.

## 4. Stop honestly

On a plateau, revisit the architecture and premise, change hypothesis category, or test a remaining cheap idea within the agreed budget. Stop when the target is met, the budget is exhausted, or further ideas cost more than their likely value. Report a blocked experiment or plateau rather than relaxing the target or spinning indefinitely.

Re-run final measurement and correctness checks against the accepted state. Clean owned temporary instrumentation and scratch resources without deleting useful evidence.

Return the workload, metric/target, budget used, baseline and final samples/statistic, noise assessment, accepted changes, rejected/inconclusive attempts, correctness results, evidence paths, and best next hypothesis. Commits, branches, PRs, and deployment remain subject to separate authorization.
