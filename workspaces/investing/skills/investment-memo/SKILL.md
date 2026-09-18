---
name: investment-memo
description: Write a model-grounded investment memo or long/short pitch as a self-contained HTML file whose figures reconcile to the delivered workbook, using only supplied evidence. Use when asked for an investment memo, write-up, pitch, thesis summary or long/short case for a company after the model work is done.
---

# Investment memo / pitch

The last step of an assignment, not a substitute for one. The memo's numbers
come from the delivered workbook and supplied documents; its judgment comes from
the analysis already done in this assignment.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md) and
[`source-policy.md`](../../references/source-policy.md). Template:
[`../../templates/investment-memo.html`](../../templates/investment-memo.html).

## Environment

Derive the toolset root (scripts, policies, venv) once, so every command below
works from any directory:

```sh
TOOLSET="$(dirname "$(readlink -f ~/Investing/.agents/skills)")"   # investing toolset root
```

## 1. Evidence record first

Write `outputs/<assignment>-evidence.json` before drafting. Every material
figure the memo will state gets an entry — the workbook hash, the sheet and
cell, the value, its units, and where a supplied source document states it:

```json
{
  "workbook": "VRT-model-C.xlsx",
  "workbook_sha256": "<hash of the delivered workbook>",
  "scenario": "base",
  "items": [
    {"label": "FY26E revenue", "sheet": "Model", "cell": "E12", "expected": 9876.5,
     "tolerance": 0.01, "units": "USD m", "source": "Q3 press release (supplied)"}
  ]
}
```

Then, against the file that will actually be delivered:

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" \
    verify --workbook outputs/<C>.xlsx --evidence outputs/<assignment>-evidence.json
```

Every item must reconcile before the memo is called model-grounded. A mismatch
is either a wrong memo figure or a wrong workbook — resolve it, do not round it
away. A filename alone is not provenance.

## 2. Draft the memo

Copy the template and fill it. Self-contained HTML: inline CSS, no CDN, no
framework — it must open from disk on any machine.

Required sections, in this order:

1. **Verdict** — long or short, position size intention if supplied, horizon
   (default 6–18 months unless the assignment says otherwise), and the one-line
   reason.
2. **Thesis** — the causal chain from the supplied facts to the expected
   outcome, with the assumptions it rests on named.
3. **Differentiated view** — what the supplied evidence says the market is
   missing. Only claim a difference from consensus when supplied estimates
   support it; a single broker file is one view, not consensus. If no
   comparison is possible, write that plainly.
4. **Operating assumptions** — the drivers the model runs on, sourced, with
   reported and adjusted figures distinguished.
5. **Valuation** — the methods the model implements, the inputs behind them, and
   the output per share. Name the conventions (period, net debt, share count)
   that the number depends on.
6. **Bull / base / bear** — the drivers that differ, the resulting values, and
   what has to be true for each. Scenario probabilities only if supplied;
   illustrative scenarios labelled as illustrative.
7. **Catalysts** — from supplied material, with dates as supplied. Anything
   reasoned from the model says so.
8. **Risks and disconfirmers** — what would prove the thesis wrong, specific
   enough to check, including the model's known weak points from the audit.
9. **Missing evidence** — the absent inputs that block a decision-ready label
   (price, consensus, share count, borrow, catalyst dates), stated as a list.
10. **Provenance** — delivered workbook name and hash, scenario, and the
    sources behind the material figures.

## 3. Language discipline

- Facts, assumptions, calculations and judgment stay visibly distinct.
- Escape supplied text when it goes into HTML; quoted passages carry their file
  and location.
- Never state a price, borrow fee, consensus figure, probability or catalyst
  that was not supplied. There is no "roughly", "approximately" or "the market
  implies" standing in for a missing input.
- A material missing valuation input means the memo is **provisional** and says
  so in the verdict, not in a footnote.

## 4. Deliver

In `outputs/`, beside the workbook:

- the memo HTML,
- the evidence record it was checked against,
- the change log and validation summary from the model work,
- the diff records that show what changed.

Report the reconciliation result explicitly: how many evidence items were
checked, and that all of them agreed — or which ones did not and what was done
about it. State which figures are unverified or missing; a memo that reconciles
to the workbook is still only as good as the model and the evidence behind it.
