# Equity Modelling Handoff

## Current state

The product design is agreed and recorded in `SPEC.md`. No workbook builder, checker, references, tests, or pilot model have been implemented. `SKILL.md` is intentionally excluded from model invocation until the pilot passes.

The existing `company-model` skill remains the production workflow and must stay unchanged through the pilot.

## Locked decisions

- Skill name: `equity-modelling`.
- Company-specific drivers are discovered during each run; none are enforced globally.
- Flexible user-supplied source pack; web evidence may challenge but cannot enter the model until the user supplies it.
- Five to ten primary drivers, eight forecast quarters, same-sheet annual rollups.
- Relevant cash flow and balance-sheet items by default; full three statements only when the investment case needs them.
- Two short gates: blueprint, then forecast assumptions.
- Formula-driven Excel with editable local inputs; Python handles evidence, construction, updates, and independent validation.
- Consensus is a benchmark only.
- Business-event scenarios and mechanical sensitivities are separate.
- Immutable dated model versions; latest reported historical basis with a change log.
- Compact institutional formatting with YoY under material levels and selective two-year stacks.

## Next session

1. Read `SPEC.md` completely.
2. Inspect reusable helpers and lessons in `../company-model/` without modifying that skill.
3. Draft the minimal implemented `SKILL.md` and decide which reference material genuinely needs separate files.
4. Implement only the smallest shared Python helpers required for a pilot; keep company-specific model logic in the generated project.
5. Select and run one real-company pilot.
6. Review the pilot against the acceptance examples and exit criteria in `SPEC.md` before enabling model invocation.

## Guardrails

- Edit the source under `~/Dev/pi-dotfiles/home/skills/equity-modelling/`, then deploy with `~/Dev/pi-dotfiles/rebuild.sh --sync-only`.
- Do not overwrite or rename `company-model` during the pilot.
- Do not treat this design skeleton as a functioning modelling workflow.
- Avoid generic engines, sector templates, dashboards, or additional infrastructure until a pilot proves the need.
