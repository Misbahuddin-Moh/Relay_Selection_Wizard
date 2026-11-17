# SEL ordering knowledge base: review and developer handoff

Review date: November 16, 2026. Project: Relay Selection Wizard.

## Decision

Reuse the knowledge base as a version-pinned reference and extraction starting point. Do not treat its existing validator, parser or promotion flag as evidence that a relay configuration is manufacturer-orderable. Preserve all current unverified states while improving the data and controls.

The Wizard is preparing a read-only integration boundary. The KB developer can complete manufacturer data independently; the application will ingest reviewed releases through that boundary. This review does not authorize changes to the application's protection philosophy, signal budgets, topology or provider controls.

## Reviewed baseline and reproducibility

Repository: https://github.com/Misbahuddin-Moh/Relay_Selection_Wizard

KB branch: `add-sel-ordering-kb`, commit `3cda2bcc36450d9bbf6470b7a78ad54d251bcedf`.

Source directory: `sel_ordering_kb/`.

Reviewed files: README, grammar, all nine product JSON records, parser/validator/assembler, promotion script, indexing and generation logic, and the 12 KB tests. All 12 existing tests passed in an isolated copy. Read-only adversarial probes exposed additional problems described below. The outside developer should begin from this exact baseline or explicitly document changes since it.

Application baseline for this work: staging release `966bffd4716203081277c0db4393849798de660a`. It has six protection arrangements, partial reference signal accounting, preliminary analog/digital screens and no procurement release or supported order-code generation. Provider routes remain disabled. This document does not describe the KB as already merged into that release.

## What exists and what is useful

| Record | Fields | Current recorded status | Relevance and next action |
|---|---:|---|---|
| SEL-451-5 | 16 | Extracted, unverified | First useful target for feeder/BF hardware work. Resolve exact symbols, field order/width and board/electrical restrictions. |
| SEL-411L | 17 | Extracted, unverified | Relevant to optional POI line terminal. Resolve channel/communications fields and distinguish ordering compatibility from an actual two-terminal 87L application. |
| SEL-487E | 0 | Header only | Critical transformer/shared/combined target, but requires full exact-variant ordering data. Generic family notes cannot approve -3/-4/-5 configurations. |
| SEL-751 | 0 | Source not text extractable | Current feeder-family target. Obtain the exact MOT and recover layout from the original PDF/image rather than guessing from an LLM summary. |
| SEL-751A | 10 | Extracted, unverified | Legacy evidence; avoid substituting its fields for current SEL-751. |
| SEL-710 | 7 | Legacy, possibly superseded | Useful parser fixture, low priority for our collector-substation scope. Do not substitute it for SEL-710-5. |
| SEL-311L-0/-6 | 10 | Legacy, possibly superseded | Useful family-difference example; file name SEL-311L is not an exact variant identifier. |
| SEL-351S | 0 | Header only | Not a complete configuration catalog. |
| SEL-700G | 0 | Header only | Not a complete configuration catalog. |

All nine records have `layout_verified=false`. There is no current evidence-backed issuable product. GE hardware is not covered. SEL-487B, SEL-787 variants and SEL-735 are not complete entries in this package.

Useful foundations include per-product mappings, confidence/open-question annotations, a small rule vocabulary, self-consistency tests, and the distinction between whole-relay ordering strings and replacement-card part numbers. The SQLite index is useful for research search; it must remain a derived index, not a separate editable authority.

## Priority findings

### P0: promotion is not proof of manufacturer origin

Location: `tools/promote.py`, especially reading golden strings and final assignment of `layout_verified`/`doc_status`.

The script accepts a plain text list, parses it with the same KB being validated, evaluates the same rules, counts distinct strings and checks whether at least two options per multivalued field are represented. It neither authenticates the origin of those examples nor stores their provenance. Comments are discarded.

Five synthetic SEL-710 strings, constructed from the KB rather than obtained from SEL, satisfy the current executable promotion predicates:

```text
071001A0000X0X0X810
071001B0101A1A1A821
071001C0000X0X0X810
071001D0000X0X0X810
071001G0000X0X0X810
```

These are synthetic negative-test fixtures, NOT manufacturer codes for use in a BOM. Their ability to satisfy the gate demonstrates internal self-consistency, not manufacturer acceptance.

Required correction:

- Store independently obtained golden cases as structured records, with exact model/variant, source artifact identity and SHA-256, revision/date, page/locator, expected decoded selections, reviewer and review date.
- Label synthetic cases explicitly and prohibit them from authorizing verification.
- Separate data extraction review, code-layout verification, compatibility-rule verification and exact configuration evidence.
- Treat five cases or two options per field as a coverage metric, not a universal proof threshold. It does not cover all options or cross-field interactions.

Acceptance: a synthetic-only golden set must not promote a product. Manufacturer-issued cases should be accepted only within a stated evidence scope. A field/option/constraint change must invalidate the affected proof.

### P0: a product-wide boolean can authorize unreviewed combinations

Location: `tools/selpn.py`, `assemble()`, and promotion output.

An isolated in-memory change setting SEL-710 `layout_verified=True` lets the first-option selection return `issuable=True` and no warnings, despite medium-confidence fields and three open questions. This is not a current production release—the checked-in record remains false—but it reveals what future promotion would permit.

The assembler blocks low-confidence fields but does not consistently block medium/inferred evidence, product questions, stale source revisions or unreviewed combinations. A small golden set cannot establish that every generated combination is valid.

Required correction: replace the single approval concept with independent statuses and an exact evidence scope. Keep procurement release outside the catalog engine. Resolve which open questions block layout, hardware compatibility or application use; do not rely on prose questions being noticed by a reviewer.

Acceptance: toggling a JSON flag alone cannot make a configuration orderable. A source/KB/golden/validator change invalidates relevant verification. Output must identify its verified scope and remaining limitations.

### P0: missing SEL-451-5 board/voltage compatibility rule

Reproduction:

```python
p = selpn.load('SEL-451-5')
s = {f['id']: f['options'][0]['code'] for f in p['fields']}
s.update(chassis='2', io_b='2', io_b_voltage='X', io_c='0')
selpn.validate('SEL-451-5', s)  # currently []
```

The cited MOT allows user-settable pickup voltage only on I/O options 1, 5 and 6. The existing notes acknowledge this restriction, but executable rules do not enforce it.

Manufacturer source: https://selinc.com/api/download/7423 — WI-8789, revision/date 20190711; I/O position input-voltage sections. Preserve the original PDF and exact page/row reference. The current KB records the date as null despite the document carrying it.

Required correction: encode a source-backed board/voltage compatibility table, including both B/C positions, empty-board positional symbols, chassis eligibility and the distinction between user-settable and fixed-voltage options. Do not infer a universal rule from one board family.

Acceptance: test each supported board against allowed and forbidden voltage choices. The reproduction above must be rejected or explicitly unresolved, never validated as compatible.

### P0: unsupported rules are silently ignored

Location: `tools/selpn.py`, `validate()` constraint dispatch.

The evaluator implements `requires` and `max_per_chassis`, but no final rejection for an unknown rule type. Adding an unsupported constraint can still yield no problems. Invalid/malformed rule shapes also lack a complete schema gate.

Required correction: validate the entire KB before evaluating any selection. Reject unsupported versions, types, operators, missing fields, nonexistent option references, duplicated identifiers and malformed values. Unknown information must produce a blocking catalog error; it must not be interpreted as no restriction.

Acceptance: unknown rule types and malformed predicates fail closed without crashes. Every executable rule has independently expected passing and failing cases.

### P1: SEL-411L channel rule contradicts its stated purpose

The current rule note/ID says differential protection needs a channel, but its executable implication allows `diff_ch1='0'` and `diff_ch2='0'`; validation returns no problems.

Required correction: re-read the exact manufacturer MOT/footnote. Separate an orderable relay without differential channels from an application that requires 87L. Do not reject a potentially legitimate channel-2-only configuration merely because an inferred rule assumed otherwise.

Acceptance: with an explicit 87L requirement, a no-channel selection is blocked. Ordering-only constraints and protection-application constraints have separate source-backed tests. Peer model, firmware compatibility, channel medium and remote clearing remain application inputs.

### P1: empty product records return successful-looking validation

`validate(model, {})` returns `[]` for header-only SEL-351S, SEL-487E, SEL-700G and the unextracted SEL-751. Assembly remains non-issuable today, but a caller using only the validator could mistake this for validity.

Required correction: structured validation statuses such as `invalid`, `unresolved`, `unsupported`, and `validated_within_scope`. An empty list of detected violations must not mean a complete valid configuration.

Acceptance: incomplete products return explicit unsupported/unresolved status and identify missing data.

### P1: symbols, boundaries and provenance need source-level reconstruction

Examples:

- SEL-451-5 Ethernet labels A1/C0 are author-created labels, not confirmed literal SEL ordering symbols.
- SEL-451-5 has unresolved Ethernet and I/O B widths and open questions about voltage width/position.
- SEL-411L has unresolved communications/channel widths and header/firmware questions.
- Some field positions and family conventions are inferred from text extraction that lost table alignment.
- Product-level `source.doc_id` is not sufficient provenance: a text value saying no direct MOT was found passes the existing provenance test.

Required correction: retrieve the original MOT, record its revision and hash, reconstruct columns and token positions from the layout, then verify with independent examples. Keep `internal_option_id` separate from literal `ordering_token`. Give fields, options, rules and capabilities explicit source locators and review states. Unknown widths remain unknown; never pad/truncate until a code looks plausible.

Acceptance: exported tokens contain only verified manufacturer symbols. Every operative mapping can be traced to a specific artifact and location. OCR/LLM confidence is distinct from evidence-review status.

### P1: verification is not durably bound to the reviewed data

Promotion writes a flag and status but no KB hash, source hash, golden-set hash, validator version or reviewer record. The generator skips promoted products; that avoids overwriting them, but does not establish whether their approval became stale.

Required correction: immutable release manifests and content-bound review records. Any meaningful change to fields, options, constraints, capabilities, firmware applicability or source revision requires invalidation/review. Preserve release history instead of treating a mutable filename as identity.

Acceptance: modifying an ordering token or capability causes old proof to stop applying. Rebuilding an index does not change the canonical data. Identical data and versions produce repeatable fingerprints.

### P1: current tests are necessary but insufficient

The 12 tests cover duplicate codes, some widths/references, self-roundtrip, unknown-code rejection, one chassis rule, family differences, unverified assembly and garbage golden rejection. The promotion test name suggests more coverage than its body exercises: it tests garbage rejection, not a valid external-golden promotion path.

Add tests for the reproductions above; positive/negative rule coverage; external versus synthetic cases; partial records; medium/inferred evidence; exact variant matching; malformed schemas; provenance completeness; stale verification; normalization of leading-zero representations; and golden cases not generated by the same code under test.

Passing tests must not be described as manufacturer approval or project engineering acceptance.

## Data needed for a real hardware allocator

The existing option descriptions contain useful facts, but prose is not a sufficient allocator input. Extend the KB with typed, source-backed data. Unknown is null/unresolved; zero means explicitly none.

| Domain | Required structure |
|---|---|
| Identity | Manufacturer, exact model/variant, hardware revision, firmware/function applicability, lifecycle status and source release |
| Code grammar | Prefix, field order, literal token, width or supported variable-width grammar, reserved/empty symbols, representation convention |
| Slots/chassis | Available physical slots, board identities, slot eligibility, mutually exclusive options, chassis-dependent capacities and required base boards |
| Analog | Physical phase/neutral CT channels, valid grouping/reuse, nominal current ratings, sensitive-neutral restrictions, VT channels/banks and electrical limits |
| Digital inputs | Physical count, independent/common grouping, voltage/threshold choices, isolation and any board-dependent restrictions |
| Digital outputs | Physical contact groups, Form A/C, high-speed and interrupting properties, make/carry/break ratings with duty/time/voltage conditions |
| Functions | Exact options for simultaneous differential elements, measurement routing, REF, BF and communications; firmware applicability |
| Communications | Physical ports, protocols, feature licenses, media and peer/firmware restrictions where documented |
| Accessories | Whole-relay items versus separately ordered kits, quantities and compatibility; do not substitute a kit PN for relay MOT tokens |
| Evidence | Artifact hash/revision/page/table/row/footnote, extraction method, reviewer status, and explicit uncertainty |

A Form C contact is one physical contact group, not two independent DOs. “Fast” and “trip-coil duty” are different properties. If one output satisfies several requirements, consume it once. A function being listed does not establish the required simultaneous function/input configuration.

The KB must describe manufacturer hardware, not decide the station's CT cores, independence, trip targets, source clearing, settings, coordination or approval. Those remain in the Wizard/project requirements and engineering review.

## Recommended delivery sequence for the KB developer

1. Preserve the reviewed baseline and add regressions for each confirmed defect before changing data.
2. Introduce strict schema/version validation and structured unresolved/invalid results. Reject unknown rule vocabulary.
3. Complete exact SEL-451-5 MOT reconstruction and revision provenance first; verify the user's actual variant rather than silently substituting a newer family member.
4. Encode board/chassis/voltage restrictions and typed capabilities. Audit every MOT footnote, including LEA/conformal-coating and output-class restrictions.
5. Obtain independently sourced SEL-issued examples; record expected field meanings from the source, not merely parser output. Mark synthetic fixtures permanently non-promoting.
6. Separate verification scopes and bind them to release/source/KB/golden/validator hashes. Remove any product-wide “all combinations issuable” implication.
7. Complete the selected SEL-487E variant next for transformer/combined roles. Treat SEL-411L and its peer/channel requirements as a subsequent bounded scope.
8. Export an inert versioned catalog release with a changelog, evidence manifest, machine-readable schema and complete tests. Regenerate SQLite from canonical JSON and verify parity.

GE catalogs remain a separate workstream. Completing SEL-451-5 will not finish transformer Primary or the station BOM.

## Application integration being prepared in parallel

The Wizard's initial consumer is deliberately read-only. It bundles the nine existing raw JSON records with the pinned source commit and canonical product hashes. It does not execute `build_kb.py`, `selpn.py`, `promote.py` or SQLite, and does not download vendor data at runtime.

The preparation separates three evidence tracks: code layout, hardware compatibility, and application review. A track may report blocked or documentary evidence recorded; neither state is procurement approval. Exact model matching has no family aliases. A generic 487E record cannot become a 487E-4 configuration by inference.

The application shows the source release, per-product blockers and the lack of role mapping. Its engineering result fingerprint includes the catalog package and adapter version/content, so changed catalog data cannot silently reuse old results. Existing partial I/O, analog screening, complete-fit=false, no order code and procurement-ready=false policies remain in force.

This is an integration boundary, not the finished joint hardware allocator. The later allocator must map reviewed station requirements to exact typed hardware resources, validate simultaneous slots/functions/ratings, and keep project acceptance separate.

## Handoff acceptance checklist

- [ ] All confirmed defect reproductions are automated regressions.
- [ ] Exact model variants and document revisions are explicit; no generic-family substitution.
- [ ] Unsupported/malformed rules and incomplete products fail closed.
- [ ] Literal manufacturer tokens are separated from internal labels and extraction placeholders.
- [ ] Source artifacts and golden cases carry durable provenance and independent expected meanings.
- [ ] Review scope is content-bound and invalidated when relevant data changes.
- [ ] Code-layout verification never becomes automatic all-combination or procurement approval.
- [ ] Typed analog/digital/slot/function data is sufficient for allocation without parsing prose.
- [ ] At least the selected SEL-451-5 scope has source-backed positive and negative compatibility examples.
- [ ] Catalog release passes schema, integrity, rule, external-example and invalidation tests.
- [ ] Wizard integration preserves partial project budgets and unresolved application evidence.
- [ ] Manufacturer configuration confirmation and engineering/procurement authority remain separate release gates.

## Ownership and boundaries

KB developer: source reconstruction, exact symbols, typed capabilities, manufacturer constraints, provenance, examples, verification scope and release artifacts.

Wizard work: catalog ingestion, exact-variant selection workflow, requirement mapping, resource allocation, consistent diagrams/BOM, stale-result protection and explicit unresolved decisions.

Engineering/manufacturer reviewers: source applicability, approved protection philosophy, actual core/DC/trip independence, electrical duties, configuration acceptance and procurement release.

The immediate objective is a dependable handoff between those responsibilities. A catalog can prove documented product facts within a reviewed scope; it cannot manufacture missing station facts or grant engineering approval.

## Consumer contract appendix

The application-side reference contract is documented in `docs/CATALOG_INTEGRATION.md`, with a version-1 structural schema in `docs/catalog-contract.schema.json` and semantic checks in `backend/catalog_readiness.py`.

Package manifests pin the exact upstream commit and per-record SHA-256 of canonical JSON: UTF-8, sorted object keys, compact separators, ensure_ascii=true, nonfinite numbers rejected. Manufacturer PDF hashes are separate. The API returns independent track states, structured blocker codes/paths and conservative release flags; it does not evaluate or authenticate documents merely because their references are populated.

The first integration is a documentary reference contract. Typed hardware capabilities and new predicates require a coordinated schema/adapter revision; they cannot be added as unrecognized fields and silently treated as supported. Plan that export boundary with the application developer before broad data entry. Catalog corruption/unavailability must leave existing project accounting usable and partial, with catalog use blocked.
