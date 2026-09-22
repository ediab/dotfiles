---
name: equity-modelling
description: Draft skill for building or updating source-driven public-equity earnings models. The workflow is specified but not implemented; invoke manually only while the pilot is pending.
disable-model-invocation: true
---

# Equity modelling

**Status: design only.** Do not use this skill to produce a live model yet.

Read `SPEC.md` for the agreed product and workflow. Read `HANDOFF.md` before continuing implementation or running the pilot.

The eventual skill will build or update a formula-driven Excel earnings model from a user-supplied source pack. It will discover company-specific drivers through an interview at invocation time rather than embedding sector assumptions.

Keep the existing `company-model` skill unchanged until this skill passes a real-company pilot.
