# Upstream provenance

## Anthropic financial-services (licensed foundation)

- Repository: <https://github.com/anthropics/financial-services>
- Pinned commit: `35c80df9f4fb` (2026-09-15, "access_policies: document and validate the file_path identifier (#352)")
- Licence: Apache-2.0, single root `LICENSE` file → copied verbatim to
  [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt); the upstream `README.md`
  is kept at [`licenses/UPSTREAM-README.md`](licenses/UPSTREAM-README.md) for the
  same reason.
- Cloned read-only for this port; `git checkout 35c80df9f4fb`. `main` is never
  tracked.

Files read at that revision (adaptation sources):

| Local skill | Upstream path | Local status |
| --- | --- | --- |
| `audit-xls` | `plugins/vertical-plugins/financial-analysis/skills/audit-xls/SKILL.md` | ported |
| `model-update` | `plugins/vertical-plugins/equity-research/skills/model-update/SKILL.md` | ported |
| `investment-memo` | — | original; no upstream source |
| `scenario-analysis` | — | original, uses licensed modelling conventions |
| `3-statement-model` | `plugins/vertical-plugins/financial-analysis/skills/3-statement-model/` (SKILL.md + `references/{formulas,formatting,sec-filings}.md`) | ported, SEC retrieval dropped |
| `comps-analysis` | `plugins/vertical-plugins/financial-analysis/skills/comps-analysis/SKILL.md` | ported |
| `dcf-model` | `plugins/vertical-plugins/financial-analysis/skills/dcf-model/` (SKILL.md, `TROUBLESHOOTING.md`, `scripts/validate_dcf.py`, `requirements.txt`) | ported with the data-retrieval core stripped |

Nothing else from the repository was copied: no other skills, no
`claude-for-*` packages, no agent-plugins variants.

## OpenAI public-equity-investing

**Not used, in any part.** Its plugin manifest declares `Proprietary`, so no
text, script, schema or asset from it appears in this workspace. The
`investment-memo`, `scenario-analysis` and `model-update` texts here are written
for this toolset.

## What changed in the ports

Every port had the same class of upstream assumptions removed, because they
cannot hold in a supplied-data-only, local-Excel tool:

1. **Retrieval.** Upstream skills assume live data access (SEC filings, analyst
   estimates, consensus, prices) and, for `dcf-model`, ship `requirements.txt`
   with `requests` plus fetching code. All of it is gone: no `requests`
   dependency, no fetching module, no network client in `pyproject.toml`. Data
   arrives from the user; anything absent is requested or marked `MISSING`
   (see `references/source-policy.md`).
2. **UI-assumption scoping.** Upstream `audit-xls` scopes by active selection or
   sheet. This toolset inspects *files* read-only, so scope is a workbook (or a
   named sheet/range) and every finding carries an explicit sheet + cell.
3. **Tool names and paths.** Upstream references to Office JS, `recalc.py`, and
   cross-skill links that do not exist here are replaced by this toolset's
   `scripts/inspect_workbook.py` and `scripts/excel_model.applescript`, whose
   measured behaviour and limits are recorded in `README.md`.
4. **One shared workflow.** The approval, hash-gating, A→B→C baseline and
   reporting contract lives once in `references/workflow-policy.md` and is
   cited, not restated, by each skill.
5. **Accounting checks.** Upstream's generic retained-earnings roll-forward
   (which adds SBC directly) is **not** carried over as a universal check: the
   port checks RE only using the model's own line items, and never imposes an
   identity the workbook is not built to satisfy.
6. **Unverified upstream claims.** Assumptions were tested rather than
   inherited; where the local environment could not do what upstream implied
   (for example, per-workbook recalculation), the limit is documented in
   `README.md` and the skill is written to work with it.

## Licence obligations

Apache-2.0 requires the licence text and notices to travel with derived
material; `licenses/` holds them. Adapted skill files state nothing about
authorship they cannot support: the upstream text is the licensed base, and the
adaptations above are described here rather than claimed as wholly original.
