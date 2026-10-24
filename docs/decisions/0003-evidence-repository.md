# 0003: qualification evidence lives in ObfuscationEvidence

Date: 2026-10-24. Status: accepted.

## Decision

- Execution receipts, prototype trees, promotion bindings and status snapshots are
  stored in the `ObfuscationEvidence` repository (small text under version
  control, large trees in its ignored `archive/`), keyed by `repository@sha` and
  worktree branch.
- Product repositories hold source, tests and documentation only. A product
  document may cite an evidence path; it does not embed receipts.
- `docs/plans/IMPLEMENTATION_PROGRESS.md` carries one continuation and stays
  under 300 lines; older continuations move to the frozen file in the evidence
  repository. `docs/plans/STATUS.md` is generated from `contracts/ledger.json`.

## Why

The root `build/` tree held about 2,900 prototype and 730 qualification
directories and tens of gigabytes of receipts with no version control, and the
progress log reached 846 KB. The product/process ratio made the repositories hard
to read and the actual state hard to reproduce.
