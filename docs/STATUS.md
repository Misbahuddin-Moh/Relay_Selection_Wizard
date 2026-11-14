# Relay Selection Wizard — status / handoff

Date: 2026-11-13. Delivery: foundation alpha, first implementation slice.

- Source baseline: `main` at `9b1c6a9706324c3c47c86b38865a702b94c9711c`; clean clone, no inherited working changes.
- Observed production: Render `relay-selection-wizard`, Ohio, live deploy `dep-dbo8583rjlhs73am7l9g`, commit `d72c35a589352b5c60d5fbf7a894a70697b2adbf`. It differs from source baseline. Production is not the target of this release.
- Target branch: `staging/quality-foundation`; CI promotes passing commits to `staging/release`; target service: `relay-selection-wizard-staging`, free plan, Ohio. Confirm resulting deploy revision before claiming success.
- Baseline: 15 backend tests, frontend production build and local HTTP smoke passed. Keys unset; provider tests mocked.
- New behavior: versioned assessment/fingerprint, per-count CT origin sidecars, all evidence unreviewed; positive counts are modeled presence, never confirmation. Partial digital budget blocks complete-fit/ordering readiness. API hardware candidates suppressed outside the three-breaker reference or for measured auxiliary taps.
- Provider operations: all three public paid endpoints fail closed with HTTP 403. Status endpoints and UI report disabled. No production credentials are copied to staging. This is a temporary alpha boundary, not implemented authentication or pilot security.
- New tests: independent HTTP quality gates, pure digital-budget tests and browser workflow checks. `bash scripts/verify.sh` is the release gate. CI verifies pushes/PRs. Docker repeats backend and frontend unit/build gates, so a failing image does not replace a healthy service.
- Release: stage reviewed changes, run `bash scripts/release-staging.sh 'message'`. It refuses the wrong branch, unstaged/untracked work, or edits during verification; commits only after gates pass, then pushes normally. Render deploy acceptance is not success: verify health, static assets, provider denial and exact commit.

## Remaining gates

This is **not** G1 Honest Study or G2 Fully Traced Configuration. Stable equipment/role IDs, fact history, complete topology representation, autosave/save/import/undo, complete signal ownership, backend digital allocator, verified manufacturer catalog and order codes, project authorization/cost limits, exports and engineering approvals remain open. No source document is sent to a provider in this alpha.

Next slice: stable project/equipment/role contracts and revision ownership, followed by recoverable project persistence. Resolve manufacturer scope and complete reference signal ownership before attempting catalog-validated T60 status. Fourth collector breaker and LV main remain later scope expansions.

## Verification checkpoint before CI

27 backend tests and four frontend digital-budget tests pass; TypeScript/Vite production build passes. The local Chromium process is blocked by the execution environment before page creation, and bundled browser downloads are truncated. This is **blocked browser verification**, not a pass. The initial source-branch commit is therefore a CI candidate only. CI must run the browser gate and advance `staging/release` before Render can deploy it. Local `release-staging.sh` correctly refuses to release while a required check cannot run.


## Identity and recovery slice — candidate checkpoint

Stable study/bay IDs, backend role identities, semantic option keys and lifted user choices are implemented. Portable schema-1 JSON, fresh analysis on recovery, browser autosave with cooperative locks/conflict detection, staged imports and pending-input undo are implemented. See PROJECTS.md for the bounded recovery scope (after first analysis; active study and pending edits only). Added independent project/identity HTTP tests, frontend reconciliation tests and a required second browser recovery gate. Candidate must pass both browser suites in CI before staging promotion. Full G1 remains open; manufacturer/catalog and complete signal derivation remain later gates.
