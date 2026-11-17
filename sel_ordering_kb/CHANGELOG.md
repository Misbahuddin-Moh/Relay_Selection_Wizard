# Changelog

## 2.0.0 - response to the 2026-11-16 review (baseline 3cda2bcc36450d9bbf6470b7a78ad54d251bcedf)

Regressions reproducing the review's defects are in git history (commit f7a6674, run against the untouched baseline:
5 of 6 reproduced; the 6th - unknown rule type silently ignored - was confirmed by hand). The v1 tests are removed;
their intent is covered by `tests/test_catalog.py` (55 tests).

### BREAKING for the Wizard's raw-JSON adapter (coordinate before ingesting)
- Product records are **schema v2**. Added: `schema_version`, `model_id`, `identity{variants,variant_resolved}`,
  `source{kind,revision,date_basis,retrieval,sha256,...}`, per-option `token_status`, per-rule `scope`,
  structured `unresolved[{id,text,blocks}]` (replaces prose `open_questions`), `max_per_chassis.match_codes` (replaces `match_prefix`).
- **Removed `layout_verified`** (and `doc_status: verified_*`). The validator *rejects* any catalog record asserting
  `layout_verified`, `verified`, `review_state`, `issuable` or `orderable`. Verification lives only in content-bound review records.
- `selpn.assemble()` no longer returns `issuable`; returns `manufacturer_orderable: false` (always), `order_string` (null unless
  every token is literal-verified AND layout is verified within scope AND the selection is inside that scope - currently never),
  and a clearly named `unverified_preview` (debug aid, not a part number).
- `selpn.validate()` is a compat shim: non-empty for anything other than `validated_within_scope`. Use `selpn.check()`.
- `tools/promote.py` removed -> `tools/verify.py`. Golden files are now JSON with provenance (`data/golden/<model_id>.json`).
- SQLite column/table renames (`model` -> `model_id`; `open_questions` -> `unresolved`; `layout_verified` dropped; `token_status` added).
- Canonical hash (unchanged contract): UTF-8, sorted keys, compact separators, ensure_ascii, non-finite rejected (`tools/canon.py`).
  Hashes of every record changed with this release.

### Fixed
- P0 promotion not proof of origin: synthetic cases (incl. the review's five SEL-710 strings) can never verify anything.
  Manufacturer cases need artifact sha256, revision, locator, reviewer, date and **expected meanings stated from the source**, not parser output.
- P0 product-wide boolean: replaced by four independent tracks bound to product/golden/validator hashes; any change -> `stale`.
  Layout verification is scoped to the field/option values actually exercised and never implies orderability.
- P0 SEL-451-5 voltage rule: user-settable pickup (`X`) rejected on I/O options other than 1, 5, 6, at positions B and C
  (WI-8789, reviewer-reported rev 20190711; **not yet re-verified against the raw PDF**).
- P0 unknown rules: full catalog schema gate runs before any selection is evaluated; unknown rule types, malformed predicates,
  dangling field/option references and duplicate ids make the product `unsupported` (no crash, no "no restriction").
- P1 411L: the inferred "needs channel" rule is now an **application-scope** rule (`requires_87l`), evaluated only when the
  application supplies that input; ordering-only checks no longer imply it; channel-2-only is not rejected.
- P1 empty/partial products: `check()` returns `unsupported` with reasons (`VARIANT_UNRESOLVED`, `NO_FIELD_DATA`, `NO_SOURCE`).
- P1 provenance: structured `source.kind`; free-text "no direct MOT found" no longer passes. Author-created labels
  (SEL-451-5 Ethernet `A1/C0...`) and the LEA placeholder are `token_status` author_label/placeholder and are never exported.
- P1 manifest + derived index: `data/manifest.json` pins every record hash; SQLite is rebuilt from JSON and parity-tested;
  `build_kb.py` is a seed tool that refuses to overwrite canonical JSON without `--force`.

### Not done (needs data this environment cannot obtain - see HANDOFF_STATUS.md)
Raw MOT PDFs/hashes, literal symbols/widths, typed hardware capabilities, SEL-487E/751/487B/787/735 ingestion, manufacturer-issued examples.
