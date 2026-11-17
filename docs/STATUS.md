# Relay Selection Wizard — current status

Updated 2026-11-15. Feature target: `staging/quality-foundation`, promoted by passing CI to `staging/release` and deployed to `relay-selection-wizard-staging`. The original app receives security fixes separately.

## Current implementation scope

A single transformer, straight collector bus, no LV main. Reference hardware screening requires the three-collector-breaker envelope; measured auxiliary taps and unsupported voltage relationships are blocked from reference screening. Collector CT inventory is uniform across breakers. This is preliminary engineering software, not an approved station design or purchasing system.

The coverage extension retains the three earlier options and adds redundant separate zones, dual combined zones, and combined Primary plus separate transformer/bus Secondary. Shared hardware remains a hosting choice with separate electrical zones. Each option derives semantic relay roles and explains modeled transformer/bus functions remaining after either system is removed. Those statements do not establish independent CT cores, DC supplies, trip coils or effective clearing.

Corrected diagrams retain feeder overcurrent boxes, show bus-side sensing and circuit-side differential boundaries around collector breakers, and distinguish illustrative overcurrent areas from differential boundaries. Secondary assignments and auxiliary treatment must remain explicitly unresolved where project evidence is missing.

The backend owns phase/neutral/VT screening and reference digital accounting, output classes and spares. Expanded budgets are derived examples, not approved complete project wiring. Hardware evidence gates separate nominal analog/digital capacity from exact simultaneous functions, module slots, electrical ratings, output duty, firmware and order-code compatibility. No complete fit or procurement release is granted.

## Persistence and privacy

Persistent equipment/role identities, portable schema-1 projects, browser autosave, conflict handling and recovery are implemented within the documented exclusions in PROJECTS.md. Studies are not a secure shared-project service.

Provider keys were cleared on both deployments. Public drawing extraction, requirements extraction and AI options routes are blocked independently of credential presence. Only engineering facts may enter any future provider flow; identifier removal, consent, access and cost controls remain reopening requirements. The owner reports Anthropic account work completed.

## Release and verification

`bash scripts/verify.sh` runs backend tests, frontend tests/build and four browser suites. CI must pass before staging promotion. Confirm the exact Render revision, health, static assets, expanded API behavior and provider denial before calling a candidate live. Prior promotions have required explicit Render deploy triggers.

The coverage extension is a candidate until that verification completes; consult GitHub and Render for authoritative revision state. Test counts are recorded in the release result rather than retained as stale status claims.

## Remaining engineering gates

- Reviewed project topology, approved protection philosophy, fault sources and clearing paths.
- Full signal ownership, mechanical/supervision/control interfaces and electrical duties.
- Independent CT core, DC and trip-path assignments; CT performance and coordination studies.
- Manufacturer-backed joint analog/digital slot allocation and exact supported order codes.
- Consistent selected station relay schedule/BOM and engineering release authority.
- Accepted real-project backtests and named engineering/manufacturer review.
- Privacy-safe document extraction, authenticated shared persistence and broader topology coverage.

Software checks establish reproducible modeled behavior only. The tool cannot establish missing engineering facts, owner acceptance or manufacturer approval by inference.

## Read-only SEL catalog preparation

The catalog continuation adds a pinned nine-record SEL reference snapshot, a strict
readiness adapter, three separate evidence tracks and a visible catalog package
panel. Source commit, canonical product hashes and adapter/loader content enter
result fingerprints. All existing records remain blocked. No variant is selected,
no role mapping or joint allocation is performed, and no ordering/procurement
permission is imported. Corrupt/unsupported packages leave partial signal
accounting usable with catalog use unavailable. See CATALOG_INTEGRATION.md and
SEL_KB_REVIEW.md for the developer handoff and remaining manufacturer-data work.
