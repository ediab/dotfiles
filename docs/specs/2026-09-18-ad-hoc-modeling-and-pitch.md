# Plan: ad hoc company modeling and investment pitches in Pi

- Date: 2026-09-18
- Original request: adapt selected skills from Anthropic financial-services and OpenAI public-equity-investing for Pi. After clarification, the user wants to supply existing company Excel models and all external data, adapt those models on an ad hoc basis, then write an investment memo/pitch.
- Working directory: `/Users/eliasdiab/Dev/pi-dotfiles`
- Verified Git branch: `main`
- Status: planning complete; revised 2026-09-18 after review (phased delivery, verified upstream facts, dependency decisions, consolidated helpers). Implemented 2026-09-18 through Unit 5: all three phases delivered, all fixture checkpoints pass, and the real-file trial ran steps 1–6 with the user's recorded decision of **no financial edits** (delivered workbook is the recalculated Evercore baseline; memo is provisional pending supplied price/consensus). See `~/Desktop/Fundaments/VRT-trial/working/approval.md` and `outputs/validation-summary.md`. Independent reviewer pass: completed 2026-09-19 — verdict Approve; the three minor findings (mechanical HTML escaping, recording `allowOtherWorkbooks` permission, `autoNoTable` demotion note) were corrected in `4706ffb` and the affected checkpoint rerun (43 checks pass).
- Canonical location: `docs/specs/2026-09-18-ad-hoc-modeling-and-pitch.md` (outside ignored `docs/plans/`). Saving here makes the file eligible for Git tracking; it does not itself commit or sync it.
- Latest clarification: privacy/provider routing is not a concern for this task. Leave existing model and memory configuration unchanged; do not add provider restrictions or model pinning.

## Context for a fresh implementer

The user is a fundamental long/short equity analyst focused on the AI ecosystem, industrials, semiconductors, and technology: examples are VRT, NVDA, and MSFT. Typical horizon is 6–18 months, with shorter or longer horizons possible. They have not built their own models yet. They will supply inherited broker/company workbooks and want help refreshing actuals, changing forecasts, repairing formulas, adding/extending operating detail, and developing valuation scenarios. The result should support a model-grounded investment memo or long/short pitch.

An earlier discussion proposed twelve skills, public-source research, company coverage folders, earnings workflows, thesis history, and a shared catalyst calendar. **That proposal was superseded. Do not implement it.** This plan is the replacement: ad hoc assignments, seven skills, supplied information only, Excel outputs followed by an HTML memo/pitch.

The user has Microsoft Excel on their Mac. Existing model layouts should be retained where practical. Originals must remain untouched. Work on copies and move toward standalone models by replacing unavailable external dependencies only with approved supplied inputs or explicitly dated cached snapshots. Do not blindly strip links, replace broken formulas with zeros, or silently turn calculations into constants.

Every workbook-changing assignment follows: inspect → propose specific changes → obtain approval → edit a copy → recalculate and validate → report. Approval to implement this toolkit is NOT approval to modify the supplied Vertiv model copies financially; obtain separate approval for the trial's concrete edits.

## User-facing brief

Build seven Pi skills with a shared local Excel toolset. The user supplies a model, supporting files, and a question. Pi explains the model's limitations, proposes changes, obtains approval, edits a copy, validates in Excel, and produces an HTML investment memo/pitch with figures tied to the final workbook.

Deliverables per assignment:

1. Adapted `.xlsx` workbook.
2. Concise before/after change log and validation summary.
3. HTML memo/pitch when requested as the final step, grounded in the workbook and supplied evidence.

All financial information comes from supplied material or explicit user assumptions. Missing inputs are requested or clearly marked, never fetched or fabricated. Models can be adapted substantially, but an automatic wholesale rebuild is not the default.

## Agreed acceptance criteria

1. Audit both supplied Vertiv originals without changing either. Identify dependencies, existing errors, and material limitations.
2. After separate approval of a bounded trial change list, produce one recalculated working copy with a source-linked change log and no unexplained new errors. Explicitly report unresolved inherited issues or blockers; do not claim the whole model is correct because errors did not increase.
3. Produce a long/short memo whose scenario and valuation figures reconcile to the delivered workbook. Missing consensus, prices, or other supplied evidence are explicit.

These are the end-to-end acceptance criteria for implementation and the independent reviewer. Do not replace them with “files exist” or “tests pass.” All seven skills must also meet the per-skill acceptance matrix in Unit 5. Audit/update/memo is the first integration checkpoint, not a reduction of final scope.

## Verified facts and remaining uncertainty

### Pi and this repository

- Pi supports standard `SKILL.md` skills and explicit `/skill:<name>` invocation.
- Project `.pi/settings.json` is read from the current directory; a root settings entry does not register skills in sessions started from assignment subfolders.
- Pi discovers `.agents/skills/` in the current directory and ancestors, bounded by the Git root (or filesystem root outside a repository). Use `/Users/eliasdiab/Desktop/Fundaments/.agents/skills` as a symlink to the versioned skill directory. Test symlink following and discovery from root and assignment subfolders. Do not assume inheritance across a nested Git repository boundary.
- `/Users/eliasdiab/Dev/pi-dotfiles/rebuild.sh` copies every directory under `home/skills/` into the global `~/.pi/agent/skills/` directory. Therefore these finance skills must NOT live in `home/skills/`.
- Version this implementation separately under `workspaces/investing/`. Keep assignment data out of the repository.
- Verified 2026-09-18: `workspaces/` does not exist yet, `/Users/eliasdiab/Investing` does not exist yet, and `docs/` is currently untracked in git. Pi docs confirm `.agents/skills/` discovery of nested `SKILL.md` files in grouping folders (project discovery applies only after the project is trusted); symlink following still needs a live test.
- This is a local macOS/Excel tool, not a VPS deployment. Do not extend VPS synchronization to ship it.
- The reviewed local `python3` was pyenv Python 3.10.13 and had no `openpyxl`. **Decision (2026-09-18):** `openpyxl` IS a declared, pinned dependency — for workbook inspection and the adapted dcf validation script; hand-rolled stdlib OOXML parsing is false economy. Workbook *writes* to inherited models still go through native Excel, not openpyxl. `requests` is NOT added. Declare the supported/tested Python version in a reproducible environment; do not hardcode the current machine's interpreter path.
- Before implementation, read current repository/ancestor instructions, Pi skills documentation, and the writing-for-agents skill. The docs path inspected during planning was `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/skills.md`.

### Excel

- `/Applications/Microsoft Excel.app` exists.
- `/Applications/Microsoft Excel.app/Contents/Resources/Excel.sdef` exposes local automation commands including `calculate`, `calculate full`, and `calculate full rebuild`, and properties for calculation mode and automation security.
- Full-calculation commands affect all open workbooks. Do not invoke them carelessly against a user's active Excel session.
- **No Excel automation was executed during planning.** Permissions, reliable formula editing, save/reopen behavior, recalculation completion, and feature preservation are unverified. Establish these on disposable synthetic workbooks first.

### Supplied examples: read-only ZIP/XML inspection, not a full audit

Paths:

- `/Users/eliasdiab/Desktop/Citadel Case Study/test/test1.xlsx`
- `/Users/eliasdiab/Desktop/Citadel Case Study/test/test2.xlsx`

Observed structure:

- `test1.xlsx`: Vertiv/Evercore model; sheets `Disclosures` and `Model`; about 7,700 formulas; 20 external-link parts; 31 stored error cells; no VBA part detected.
- `test2.xlsx`: Vertiv/UBS model; financial statement, segment, summary, and quarterly-trend tabs; about 22,500 formulas; hidden `__FDSCACHE__` sheet referring to FactSet functionality; 333 stored error cells; no external-link parts or VBA part detected. Calculation mode was `autoNoTable`.
- Both contain cached formula results. These may be stale. A FactSet cache does not prove active provider functions work. Absence of external-link parts does not prove absence of other dependencies.
- Recompute these facts during implementation; files may have changed. Error counts describe stored cell errors, not materiality, root causes, or fresh Excel recalculation.
- Broker workbooks are private test inputs, not fixtures to commit, publish, or redistribute.

### Upstream sourcing

- Anthropic repository: `https://github.com/anthropics/financial-services`; Apache-2.0, single root `LICENSE` file (verified 2026-09-18). Preserve the license/notice when copying.
- Verified baseline: commit `35c80df9f4fb` (2026-09-15). Pin to this SHA when copying; do not track `main`.
- Primary directories (verified at that SHA): `plugins/vertical-plugins/financial-analysis/skills/` (audit-xls 6.3KB, 3-statement-model 21KB + 3 references, dcf-model 49KB + TROUBLESHOOTING.md + scripts/validate_dcf.py + requirements.txt, comps-analysis 31KB) and `plugins/vertical-plugins/equity-research/skills/model-update` (3.3KB).
- Porting is mostly Markdown rewriting, not dependency surgery: five of six sources are plain SKILL.md files with no scripts or connectors. The exception is `dcf-model`: its bulk is SEC/analyst data retrieval that must be stripped for supplied-data-only, and its `requirements.txt` pulls `requests` (live HTTP) — do not port that dependency or the fetching code it supports.
- OpenAI source originally discussed: `https://github.com/openai/plugins/tree/main/plugins/public-equity-investing`.
- Its `.codex-plugin/plugin.json` declares `Proprietary`. The user explicitly approved using Anthropic as the licensed foundation and writing original additions instead. **Do not copy OpenAI text, scripts, schemas, or assets.**
- Upstream instructions are not automatically correct. The inspected Anthropic three-statement skill includes a generic retained-earnings roll-forward adding SBC directly; do not carry that over as a universal accounting check. It also references Office JS and a `recalc.py` path whose applicability must not be assumed.

## Proposed implementation layout

Repository root for all new implementation files:

`/Users/eliasdiab/Dev/pi-dotfiles/workspaces/investing/`

```text
workspaces/investing/
├── README.md
├── UPSTREAM.md
├── licenses/
├── setup.sh
├── skills/
│   ├── audit-xls/SKILL.md
│   ├── model-update/SKILL.md
│   ├── 3-statement-model/SKILL.md
│   ├── dcf-model/SKILL.md
│   ├── comps-analysis/SKILL.md
│   ├── scenario-analysis/SKILL.md
│   └── investment-memo/SKILL.md
├── references/
│   ├── workflow-policy.md
│   ├── financial-modeling.md
│   ├── source-policy.md
│   └── sector-drivers.md
├── scripts/
│   ├── inspect_workbook.py
│   └── excel_model.applescript
├── templates/
│   ├── workspace-AGENTS.md
│   └── investment-memo.html
└── tests/
```

Names above are planned targets, not existing APIs. Keep helpers small: do not create a generic approval service, schema framework, report platform, or assignment engine. **Consolidation decision (2026-09-18):** one inspector script — `inspect_workbook.py` with an inspection mode and a diff mode (replacing the previously planned `compare_workbooks.py` and `validate_assignment.py`). Add `pyproject.toml` declaring supported Python and actual dependencies (`openpyxl`, pinned; no `requests`), and document the tested interpreter version and environment setup. Shared references are ordinary Markdown, not extra discoverable skills.

Private runtime workspace: `/Users/eliasdiab/Desktop/Fundaments/` (renamed from `~/Investing` on 2026-09-19).

```text
Investing/
├── .agents/skills -> /Users/eliasdiab/Dev/pi-dotfiles/workspaces/investing/skills
├── AGENTS.md
└── assignment-name/
    ├── inputs/
    ├── working/
    └── outputs/
```

Assignment folders are created when requested, not prepopulated for VRT/NVDA/MSFT. No company database or coverage hierarchy is required. `inputs/` contains untouched supplied originals/copies and evidence; `working/` contains drafts, inspection records, and the approved change specification; `outputs/` contains delivered workbook, memo, and audit/change summaries. Do not automatically commit these folders.

## Ordered implementation units

### 0. Prove local Excel feasibility before porting skills

Files: a minimal `scripts/excel_model.applescript`, disposable synthetic fixtures under `tests/`, `pyproject.toml`, and setup notes in `README.md`.

- Run the first automation test visibly from the main terminal session with the user available to answer macOS Automation permission prompts. Do not dispatch this first run to an unattended background agent.
- Establish the supported/tested Python interpreter and reproducible dependency setup. Resolve the interpreter through that environment, not an absolute pyenv path.
- On a disposable workbook, demonstrate input edit → dependent formula change → save → recalculate → close/reopen → verified formula and result. Verify safe opening without external-link updates, settings restoration, and preservation of the fixture's workbook features.
- Ensure unrelated workbooks are not affected. Request exclusive Excel use if the tested calculation method requires it.
- Record actual commands/capabilities that worked and any limitations. Do not fabricate an automation API from memory.

Done: the core Excel path is proven. If blocked, report the blocker before investing in seven skill ports; do not substitute another calculation engine silently.

### 1. Register finance skills only in the investing workspace

Files: `setup.sh`, `README.md`, `templates/workspace-AGENTS.md`, and runtime `.agents/skills`/`AGENTS.md`.

- Read current Pi documentation to verify ancestor discovery and symlink behavior.
- Make setup create `/Users/eliasdiab/Desktop/Fundaments/.agents/skills` as a symlink to the repository's `workspaces/investing/skills/` directory. If the path exists and is not the intended link, report the conflict rather than overwriting it. Do not also register the same skills in `.pi/settings.json`.
- Make setup repeatable. Preserve unrelated existing project settings and instructions; report conflicts instead of overwriting them.
- Document starting Pi at the workspace root as the simplest workflow. Test root and assignment-subfolder discovery, including relative references in symlinked skills. Do not claim nested discovery if the actual installation fails it; report that limitation.
- Leave existing model/provider and memory package configuration unchanged. No privacy override or workspace model pin is required.
- Do not edit global skill settings, `rebuild.sh`, bootstrap scripts, or VPS sync behavior to install this toolkit.

Done: skills are discoverable in the verified investing session path and absent from unrelated coding sessions. Running setup twice does not duplicate settings or destroy files.

### 2. Adapt the seven skills and shared finance policies

Files: all seven `SKILL.md` files, `references/*`, `UPSTREAM.md`, and `licenses/*`.

Delivery is phased; report to the user at each phase boundary (report, not re-authorization):

- **Phase 1 (Unit 0):** Excel feasibility gate. Nothing else is built until this passes.
- **Phase 2 (Units 1–4, thin slice):** shared references first (`workflow-policy.md`, `source-policy.md` — all seven skills cite them; writing skills first means rewriting them), then `audit-xls`, `model-update`, `investment-memo`, the shared helpers, and workspace registration. Prove the checkpoint on synthetic fixtures, then run real-file trial steps 1–4 (hash/audit originals, baseline recalculation of copies, proposed change list) and stop for the user's separate approval of the concrete Vertiv edits.
- **Phase 3 (remaining four skills):** start only after the Phase 2 trial is applied and reported. Order: `scenario-analysis` and `comps-analysis` (cheap, no data sourcing), then `3-statement-model`, then `dcf-model` last — it is the heaviest port (strip the SEC/analyst retrieval core; do not port `requirements.txt`).

The seven-skill scope remains approved as a whole; phase boundaries are reporting checkpoints, not permission gates. A pending user decision on the real-model trial must not prevent useful synthetic testing.

Suggested licensed bases:

| Local skill | Anthropic source |
| --- | --- |
| `audit-xls` | `financial-analysis/skills/audit-xls` |
| `model-update` | `equity-research/skills/model-update` |
| `3-statement-model` | `financial-analysis/skills/3-statement-model` |
| `dcf-model` | `financial-analysis/skills/dcf-model` |
| `comps-analysis` | `financial-analysis/skills/comps-analysis` |
| `scenario-analysis` | Original instructions with appropriate licensed modeling references |
| `investment-memo` | Original combined buy-side memo/pitch instructions |

- Verify these source paths at the pinned revision (`35c80df9f4fb`). Record repository URL, commit SHA, copied files, and adaptation notes in `UPSTREAM.md`.
- Read each selected source and every retained linked reference/script. Copy only dependencies actually needed and permitted by license.
- Replace unavailable connectors, automatic web retrieval, Office JS assumptions, tool names, absolute runtime paths, and broken cross-skill links.
- Use one shared approval workflow. After approval, perform the approved sequence without asking permission after every statement. Ask again only for changed scope, material ambiguity, or a new financial assumption.
- Normalization is supporting guidance, not an eighth skill. Distinguish reported and adjusted figures; document adjustments and avoid double-counting.
- Support industrials/orders/backlog/capacity, semis/product and mix cycles, and cloud/software/segment/capex drivers without assuming every company uses every metric.
- Comps must work only with supplied peer and market data. Request missing data; do not imply access to a live consensus database.
- Do not force a complete DCF or three-statement rebuild when the requested change is narrow. Do not overwrite an inherited model's conventions just to apply a preferred template.

Done: exactly seven usable finance workflows, all references resolve, and none requires unavailable services or silently fetches financial data.

### 3. Implement and prove the Excel toolset

Files: `scripts/inspect_workbook.py` (inspection + diff modes), `scripts/excel_model.applescript`, associated tests, `pyproject.toml`, and reproducible environment documentation. Extend the proven Unit 0 helpers rather than building a second automation path.

Start with disposable fixtures, not the user's workbooks.

Inspection:

- Read OOXML safely without modifying it. Inventory sheets, formulas, stored results/errors, external links, names, hidden content, calculation mode, provider functions, and unsupported features.
- Produce a bounded machine-readable record plus a readable summary. Report counts as observations, not proof of financial correctness.
- Map significant workbook cells/sections through an assignment-specific record rather than hardcoding VRT row numbers into reusable tools.

Controlled changes:

- Capture an input hash and proposed cell/formula/structural changes, with old/new content, reason, supplied source or explicit assumption, and expected downstream effects.
- Obtain explicit user approval in chat for the concrete change list. The agent records that actual approval with a session/message reference when available and the approved scope; the user need not author a machine-readable file. This is an audit trail and behavioral requirement, not independent authorization enforcement. Do not claim an agent-written record proves consent or build a separate authorization service.
- Retain mechanical hash checking: refuse edits when the workbook no longer matches the inspected/approved input. A changed input needs a new inspection and approval of the resulting change list.
- Write only to a distinct working/output copy. Never write to an original path.
- Prefer native Excel editing for inherited workbooks. Verify preservation before adopting another library for workbook writes; do not assume `openpyxl` round-trips arbitrary broker workbooks without loss.
- Preserve calculation formulas and linkages unless replacing them is specifically approved. Cached snapshots must include their actual known as-of date or an explicit unknown-date warning; do not use today's date as the data date.
- Prevent automatic external refresh and macro execution when opening unfamiliar files. Determine supported controls from installed Excel documentation/dictionary, not guessed commands.
- Do not close, save, or recalculate unrelated user workbooks without permission. If reliable calculation requires exclusive Excel use, stop and request it rather than silently disrupting the user's session.
- Restore altered application settings on success and failure; never kill Excel to escape an error.

Validation:

- Establish three explicit states for each real trial: A = original saved/cached workbook; B = unedited disposable copy recalculated in the tested Excel environment with external refresh disabled; C = approved edited copy recalculated under the same settings. Preserve A's cached evidence before opening any copy in Excel.
- Compare A→B to identify environment/recalculation drift, including missing add-ins and unresolved external references. Compare B→C to identify edit-related changes. Create C from a fresh copy of A so failed baseline calculation has not destroyed cached inputs; record any approved snapshots extracted from A before recalculation.
- If B has unusable key outputs, do not proceed as though the baseline is sound. Identify dependencies, seek supplied replacements/approved snapshot treatment, and document residual limitations. Baseline drift is not permission to tolerate unexplained edit effects.
- Save, reopen, and confirm formulas and output values. Prove actual recalculation, not just a nonempty cached result.
- Account explicitly for sensitivity tables and `autoNoTable`; do not present unchanged table caches as fresh sensitivities.
- Compare old/new cells, formulas, names, sheets, and errors. Explain expected propagated output changes separately from direct edits.
- Check relevant balance-sheet, cash-flow, segment, and valuation linkages using mapped cells and appropriate rounding tolerances. Do not enforce an invalid universal accounting identity.
- Test scenario changes propagate and restore the intended delivered scenario.
- Report technical validation (open/save/recalculate, formula/feature preservation) separately from financial validation (accounting linkages, valuation math, scenario economics). Neither a successful recalculation nor zero new Excel error cells proves financial correctness.
- Do not promise universal broker-workbook support. Protected sheets, unavailable add-ins, circular calculations, and unsupported objects require an explicit capability assessment. Stop or narrow scope when safe handling cannot be demonstrated; do not remove protection, flatten objects, or improvise repairs.

Done: fixtures demonstrate formula preservation, actual recalculation, controlled edits, and failure handling. If Excel automation cannot meet these requirements, report the blocker before trialing the real model; do not silently substitute a weaker engine.

### 4. Create the model-to-memo handoff

Files: `templates/investment-memo.html`, `skills/investment-memo/SKILL.md`, and shared source/workflow policies. Memo/workbook agreement checks live in the inspector's diff mode rather than a separate `validate_assignment.py`.

- Build an evidence/output record identifying the final workbook filename/hash, scenario, sheet/cell references, values, units, and supplied source locations.
- Produce an HTML memo with thesis, differentiated view, operating assumptions, valuation, bull/base/bear cases, catalysts, risks/disconfirmers, and missing evidence.
- Default horizon is 6–18 months but use an assignment-specific override when supplied.
- Do not assert a view is different from consensus unless supplied estimates support that comparison. Distinguish a single broker's forecast from consensus.
- Do not fabricate current prices, borrow fees, consensus, scenario probabilities, or catalysts. Unsupported scenarios may be explicitly illustrative; material missing valuation inputs block a decision-ready label.
- Keep HTML self-contained for portability and reliable viewing; no CDN dependency or elaborate frontend framework is needed. Escape supplied text in HTML.
- Tie material modeled figures to workbook outputs. A filename alone is not sufficient provenance.
- Store a concise change log and validation summary beside the output. Avoid mandatory dashboards or elaborate report frameworks.

Done: a generated memo's figures match the saved workbook and clearly separate facts, assumptions, calculations, and judgment.

### 5. Run end-to-end acceptance and independent review

Files: `tests/`, implementation README, and private trial assignment outputs.

Automated/synthetic checks:

- Project-only skill registration and repeatable setup.
- No broken skill references or accidental unsupported connector dependencies.
- Original-file protection and stale-input hash rejection; chat-approval traceability without pretending the audit record independently enforces consent.
- Accurate formula/error/dependency inspection.
- Approved edit application, save/reopen preservation, and actual Excel recalculation.
- Missing-input behavior: ask/flag, no web research.
- Scenario propagation and memo/workbook numeric agreement.
- Safe handling of Excel permission denial or unsupported workbook features.

Per-skill acceptance matrix (all seven required):

| Skill | Concrete check |
| --- | --- |
| `audit-xls` | Seed a fixture with a broken reference, inconsistent formula, and failed statement tie-out; report their locations and distinguish them from harmless hardcoded assumptions. |
| `model-update` | Apply an approved supplied actual/forecast change to a copy; verify source mapping, old/new values, dependent outputs, and unchanged original. Reject stale input hashes. |
| `investment-memo` | Generate a memo from the saved model and supplied evidence; reconcile all material modeled figures and explicitly flag absent consensus or price inputs. |
| `3-statement-model` | On a small linked fixture, change an operating driver; show the change flows through IS/BS/CF while balance sheet and cash tie-outs remain within declared rounding tolerance. |
| `dcf-model` | Independently calculate expected discounted cash flows, terminal value, enterprise-to-equity bridge, and per-share value for a small known-input fixture. Compare workbook outputs, with explicit timing, net-debt, and share-count conventions. |
| `comps-analysis` | Supply a small peer dataset with declared units and fiscal periods; verify enterprise values, multiples, and summary statistics against independent expected values. Flag incompatible periods/units and nonmeaningful denominators rather than silently mixing them. |
| `scenario-analysis` | Toggle base/bull/bear on a linked model, verify only intended drivers change and outputs recompute, independently check a small sensitivity grid, then restore and save the declared delivery case. |

Use the actual skills to carry out these fixture tasks, not just their helper scripts. Expected financial results must be independently calculated, not read back from the same generated formulas. Keep tests focused on financial behavior, not report styling or internal file structure.

Real-file trial:

1. Hash and audit both supplied Vertiv originals locally. Do not add them to source control or redistribute them.
2. Preserve original cached results, then recalculate unedited disposable copies. Report original→baseline drift separately from stored errors, with dependencies and materiality where possible. Protect unrelated open workbooks during the baseline run too.
3. Choose the most suitable workbook for a bounded trial based on baseline and inspection; do not assume the workbook with fewer stored errors is necessarily safer.
4. Present the exact change list, baseline limitations, and any missing user-supplied inputs. Wait for separate approval.
5. Apply approved edits to a fresh working copy, recalculate under the same baseline environment, compare baseline→edited results, and verify original hashes are unchanged. Report technical and financial validation separately.
6. Produce the model-grounded HTML pitch using available supplied evidence. If the user has not supplied enough evidence for a complete pitch, identify the missing material and label the result provisional rather than fabricating content.

After substantial implementation, dispatch a fresh independent reviewer with this plan, the exact diff, acceptance criteria, and validation results. Review should cover financial correctness safeguards, recalculation baseline separation, workbook preservation, honest approval behavior, all seven skill acceptance checks, and workspace-only routing. Correct findings and rerun affected checks before reporting completion.

Done: report each end-to-end criterion and each of the seven per-skill checks as passed, failed, or blocked, with evidence. Separate fixture success from live Excel and real-workbook success, and technical correctness from financial correctness. Do not call seven skills usable after testing only audit/update/memo.

## Explicit exclusions and constraints

- No public financial-data search, scraping, paid connectors, or automatic data refresh.
- No earnings-specific skills, coverage tracking, thesis-history system, catalyst calendar, scheduled jobs, or portfolio management.
- No trading or account-specific execution automation.
- No copied OpenAI proprietary implementation.
- No changes to global finance skill registration, global research-tool behavior, VPS config, or unrelated working-tree files.
- No automatic rebuilding of entire supplied models, automatic repair of all inherited errors, or cosmetic restyling unrelated to the task.
- Keep supplied models/research out of Git and do not redistribute broker materials. This is repository hygiene and licensing discipline, not a new provider/privacy policy.
- Privacy/provider routing is not a blocker. Existing model and memory extensions may process conversation content; leave their configuration unchanged. Do not add privacy controls, provider allowlists, or model pinning. Local Excel remains the calculation tool for fidelity, not because offline processing is required.
- Supplied-data-only remains a functional requirement: do not fetch financial data. This does not forbid library documentation research during implementation. Do not add a security extension or claim hard network isolation.
- Follow repository Git policy during later implementation. Do not push, deploy, or publish. This planning-only request authorizes saving the plan, not implementation or Git operations.

## Risks / decisions that must not be guessed

- Excel automation permission or calculation limitations may block validation. Report them explicitly.
- External links and provider functions can be unavailable even when cached outputs look plausible. Preserve known cached evidence before recalculation and disclose its freshness limitations.
- Excel save operations can alter workbook metadata; distinguish harmless serialization changes from lost formulas, names, features, or financial meaning.
- Some inherited errors may be outside the approved scope. Document them; do not quietly broaden the repair job.
- If supplied information is insufficient for an economic assumption, ask the user. Routine technical implementation choices remain the implementer's responsibility.

## Next action

Wait for explicit implementation approval. Once approved, deliver in the three phases described in Unit 2 without repeated “shall I continue?” questions, reporting at each phase boundary. The ultimate success metric is that the user can trust the numbers in a memo produced from an edited Vertiv copy — not that seven skills exist or that their checks pass. The trial-model financial change list still requires its own approval.
