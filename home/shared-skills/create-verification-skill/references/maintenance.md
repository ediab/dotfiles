# Maintain an existing verification skill

Keep its instructions and feature map aligned with the running product. This branch is reached only by an explicit maintenance request.

## Scope and outcomes

Locate the project verification skill with launch/drive sections and a feature map. Ask which target when several match; if none exists, report that generation is needed instead. Read its full instructions and map.

Edit only that verification directory and its owned helpers. A product regression is a finding to report, not permission to alter product code or rewrite the map to disguise broken behavior.

Report one outcome:

- **clean:** every mapped feature and listed entry point received source and live coverage, with no corrections needed.
- **changed:** required coverage is complete and a local reviewable diff corrects documentation, map, or harness drift, with affected instructions re-proven.
- **blocked:** required coverage or safe correction could not be completed. Report any partial corrections too; never call a partial pass clean.

## Procedure

1. **Check the index.** Compare README entries with sibling feature files and fix missing/dead/duplicate entries. Read current sources for each feature; cite likely drift and identify a concrete live verification recipe. Sweep recent relevant changes for missing user-facing features, requiring a real source entry point before adding one.
2. **Plan safe coverage.** Reconcile overlapping recipes into a manageable sequence. Follow the target's launch and isolation model. Source reading can use independent help under the host's rules, but this procedure mandates neither delegation nor a per-feature fan-out.
3. **Drive the map.** The owner drives each mapped feature and listed entry point at least once. Doctor before the first drive or each fresh CLI/session, and again after any surprising failure. Reset or relaunch when state is wedged even if the process is healthy. Stop for unsafe shared/live operations or unmet access prerequisites.
4. **Triage.** Wrong instructions are doc drift; working product behavior the harness cannot exercise is a harness gap. Broken product behavior is a product regression: report it, preserve intended behavior in the map, and mark verification blocked. A missing prerequisite in the map is drift even when the feature itself works.
5. **Correct and re-prove.** Fix only within scope, then execute affected instructions live. A doctor failure caused by instruction drift may be corrected and retried once; report persistent failure rather than looping blindly. Document helpers and executable permissions.
6. **Clean up and retain proof.** Clean failed-attempt residue promptly, without killing a shared instance. Final teardown removes only owned resources after all re-proofs. Check every retained artifact still exists outside cleaned scratch state.

Record unreachable routes with the command attempted and missing prerequisite. “Unreachable: entitlement missing” is not a passing verification. Report source-only checks separately from live checks and list uncovered entries.

## Return

Give the outcome, target, feature/entry-point coverage, confirmed corrections or product gaps, evidence paths, unmet prerequisites, and cleanup result. Keep run notes in scratch storage, not the feature map. A changed outcome is a local diff, not automatic permission to commit, push, open a PR, or schedule future runs.
