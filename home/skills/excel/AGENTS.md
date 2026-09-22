# excel skill

Model-invoked skill for creating/editing/validating `.xlsx` files. Users get `SKILL.md`; only touch it when behavior changes.

Layout:
- `SKILL.md` — the workflow. Keep it short and procedural; push detail into `references/`.
- `references/quality-and-formatting.md` — deferred rules; the workflow must stay readable without them.
- `scripts/excel_gate.py` — PEP 723 (uv) script. Deps are pinned in its header; Excel runs in a child process with `--_worker`. Requires `uv run --script` as entrypoint.
- `tests/test_excel_gate.py` — pure-logic unittests, no Excel needed: `python3 -m unittest home/skills/excel/tests/test_excel_gate.py` from repo root.

Rules:
- `asp` CLI is self-describing — check `asp schema <cmd>` before changing command examples; don't trust memorized flags.
- `data_only=True` workbooks are never saved. Originals are immutable; the gate only replaces the draft after a passing verdict.
- No Anthropic xlsx material (license prohibits derivatives). Licenses for the pinned OpenAI sources are bundled; provenance lives in `../ATTRIBUTION.md`.
- macOS limits (documented, not bugs to fix casually): `Chart.to_png` unimplemented, `Range.to_png` hangs/clobbers clipboard → renders go through `asp render`; chart review is via range renders.

After editing, run the unit tests and `./rebuild.sh --sync-only`, then commit.
