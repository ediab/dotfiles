# Earnings update

Use this branch when new actuals arrive or an approved model's evidence set changes. The prior
source pack and workbook are immutable; write a new dated workbook.

## Sequence

1. **Preflight.** Hash the existing workbook and supplied files. Inventory sheets, actual and
   forecast periods, driver ids, approved defaults, local overrides, designated Outlook text,
   formulas, defined names, and disallowed workbook features. Refuse in-place editing.

2. **Capture user-owned values by identity.** Record each local override by `(driver_id, fiscal
   period)` and each designated Outlook text block by stable field id (`thesis`, `key_debate`,
   `catalysts`, `risks`, `falsifying_evidence`). Cell coordinates are not identities. Blank text is
   a valid value; zero is a valid numeric override.

3. **Inventory the new pack.** Reparse actuals and guidance from the newly supplied evidence. Never
   copy actuals out of the old workbook. Compare the old and new source registers; log restatements,
   definition changes, and replaced forecasts on the latest reported basis.

4. **Roll the grid.** Move the reported quarter into actuals, add a new eighth forecast quarter,
   and derive annuals from the resulting quarters. A retired-quarter override is dropped, not moved
   forward.

5. **Restore cautiously.** Restore an override only when its driver id, fiscal period, unit, and
   definition still match. Report removed drivers, retired periods, and changed definitions; never
   guess a rename or silently remap a value. Restore designated Outlook text by field id.

6. **Re-open the gates as needed.** Repeat the blueprint gate only if segments, driver equations,
   statement depth, scenarios, or valuation changed materially. Always present the new quarter and
   every material carried or changed assumption in one forecast-approval package. A new forecast
   quarter requires approval before activation.

7. **Explain estimate changes.** Bridge the previous approved forecast to the new one: reported
   variance, changed evidence, driver revisions, mix/margin effects, capital/cash effects, and
   valuation impact. Keep forecast-versus-actual history available.

8. **Rebuild and validate.** Build to a fresh path, run the normal independent checks, recalculate,
   render, and compare the original hash with its preflight hash. Deliver both the new path and the
   update/change log.

**Done when:** the old workbook and source pack are byte-for-byte unchanged; new actuals reconcile
to the supplied pack; every preserved value was restored by identity; withheld values are listed;
new assumptions are approved; and the complete validation contract passes.

## Pilot implementation rule

Keep update code in the generated company project until two projects prove the same helper is
needed. If override migration is required during the pilot, adapt the identity-based logic already
ported into this skill's `scripts/overrides.py` into that project. (Its ancestor, the archived
`company-model` skill, is at `~/Downloads/archive/company-model-2026-09-22/`.)
Do not create a shared update framework pre-emptively.
