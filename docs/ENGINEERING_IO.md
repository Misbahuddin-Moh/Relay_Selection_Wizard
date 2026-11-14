# Backend I/O service — first reference path

The backend now owns the reference digital ledger, point arithmetic, class-group reserves and nominal card screening. The browser edits input decisions and renders one current result across the signal budget, shortlist point table and manufacturer request text. There is no remaining browser I/O calculator or independent card-capacity comparison. Analog-family screening remains preliminary and is not a verified module allocator.

## Input and result

`POST /api/engineering/io` accepts a stable-ID study, one supported scheme and digital settings. Settings contain the wiring variant, DI/DO reserve percentages/basis, optional edited signal rows and optional fast/form-C requirements by variant and signal ID. Input is capped at 2 MiB. Unknown fields, client totals/readiness/capacities, duplicate signal IDs, invalid methods/points/classes and internal interfaces crossing relays are rejected. Legacy station objects must first migrate through project validation to obtain persistent IDs.

The response includes:

- Scope and measurement prerequisites, solver/policy/matrix versions and fingerprints.
- Editable interfaces and a complete reference ledger, including external lockout contacts, breaker coil drives and conditional analog/communications rows.
- Stable relay identities, including dedicated HV and feeder BF devices where modeled.
- Per-relay used/required DI and output groups, category-review gaps and unresolved ownership/routes.
- Nominal card examples with capacities, shortages, actual available spare percentages and evidence/compatibility limits. Unknown capacities remain null.

A fingerprint depends on study/decisions, policy and assessment, normalized ledger data, editor/card data and solver source hash. Changing one of these invalidates the result. The UI immediately hides previous totals/fit when inputs change; a retained editor is not a retained engineering result. Failed/initial requests expose retry. Obsolete responses cannot replace a newer revision.

## Source and endpoint accounting

The reference source is the earlier illustrative `Relay_Wizard_Per_Relay_Signal_Matrix.zip/signal_matrix.csv`. Its SHA-256 is retained in `backend/data/ledger_manifest.json`. The 5,033 source rows across 30 cases are represented by deduplicated templates plus original per-case order. Each returned row retains its original case/row number, owner, inclusion condition, authority and source-document tags. The existing 239 editable digital templates and 50 historical card examples moved into backend data. No private project drawing or actual owner approval was supplied.

Drawing tags (DC86, TRIP, BF, AC, etc.) identify required documents, not verified drawing citations. Every row remains unreviewed. User overrides are labeled explicitly; their external field consumption/ownership becomes unknown where no reviewed endpoint evidence exists. Excluded baseline rows remain visible as exclusions if omitted from a replacement edit list. Repeated identical interfaces produce a review finding instead of silent deduplication.

Relay DO, relay DI, external source contacts, field coil drives and external discrete inputs are distinct quantities. For example, an 86 contact starting BF consumes an external source contact and the receiving relay's DI; it does not consume another DO on the initiating protection relay. Multiple independent drives to one coil do not establish multiple physical coils. The full ledger defaults to all endpoints, with an optional selected-relay filter.

## Reserves and output classes

Used-based required capacity is `ceil(used × (100 + percent) / 100)`. Installed-based is `ceil(used × 100 / (100 − percent))`. Integer arithmetic covers 0–99% without floating-point rounding. DI is a separate resource. Output demands are grouped by their exact conjunctive capability set: ordinary, coil, fast, form-C or their intersections. Reserves round independently within each such group; required physical outputs are the sum of those disjoint groups. This is an explicit preliminary reserve policy, not a universal owner requirement.

A contact that must be both fast and form-C is one demand requiring both properties. Two independent signals remain two demands even if a contact supports both. Grouped integer max-flow allocates each physical contact only once and can reroute flexible ordinary demands around scarce qualified contacts. This mechanism is tested with independent synthetic cases.

The historical card examples do not establish fast/form-C capacity, voltage thresholds, make/carry/break duty, isolation, watchdog form or simultaneous slot/chassis/firmware compatibility. These remain unknown. A missing class cannot be replaced by ordinary surplus. Unknown evidence produces an unverified allocation, not proven infeasibility. Nominal shortages are still reported where known counts establish them. Actual spare percentages are unavailable for unknown/zero capacity or over-capacity use; overload points are separate.

## Completeness and purchasing boundary

Every budget is partial. Category review shows enumerated-but-unreviewed or unresolved trip, BF, status, mechanical, control, supervision, alarm, interlock and communication categories. Resolving routes, adding reserves or fitting nominal card counts does not establish completeness. All complete-fit flags remain false, electrical/module compatibility remains unverified, and no order code or procurement release is generated.

The first fully traced purchasing path still requires approved project signal ownership and exact manufacturer/module/firmware evidence. This service exposes those gaps rather than filling them with guessed DI/DO. Outside the three-breaker reference envelope or with an unreviewed measured auxiliary tap, the service returns explicit scope reasons and no usable budget/card fit.

## Persistence and verification

Schema-1 projects retain input edits and output-class requirements, not derived budgets. All saved variants receive the same semantic wiring validation. Changing breaker order or line scope clears positional edits and class overrides with a notice before applying a new case. Existing source excerpts and credentials remain excluded.

Independent regression fixtures cover all 217 researched per-relay totals over 30 cases; they establish reproduction of illustrative examples, not engineering approval. Unit/HTTP tests also cover endpoints, reserves, class overlap, missing evidence, scope, manipulated inputs, import semantics and dependency invalidation. The third browser gate verifies one backend result across the budget/shortlist/request text, class persistence, failure/retry and delayed-response protection. The prior foundation and recovery browser suites remain required.
