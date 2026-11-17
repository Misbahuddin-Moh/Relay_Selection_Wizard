# SEL Relay Ordering-Code Knowledge Base

Indexed, source-attributed model of how SEL builds part numbers (Model Option Tables, "MOTs"), for a
SLD -> relay BOM web app where an EOR reviews the output.

## Principle: fail closed, verify by evidence, release elsewhere
`selpn.check()` returns one of `unsupported | invalid | unresolved | validated_within_scope`. An empty problem list never means valid.
Nothing in catalog JSON can assert verification (the validator rejects it). Verification is four independent tracks
(data extraction review, code layout, compatibility rules review, configuration evidence) recorded in content-bound files under
`data/reviews/` and invalidated (`stale`) when the product record, golden set or validator version changes.
`manufacturer_orderable` is always `false` here: manufacturer confirmation and engineering/procurement release are outside this component.
Canonical data is `data/products/*.json`; SQLite and the manifest are derived/pinned. See `CHANGELOG.md` and `HANDOFF_STATUS.md`.

## Layout
- `data/products/*.json` schema-v2 records (fields, widths, options with `token_status`, typed rules with `scope`, `unresolved`, provenance).
- `data/grammar.json` cross-product conventions and traps. `data/manifest.json` release pins. `data/sel_kb.sqlite` derived FTS index.
- `data/golden/<model_id>.json` manufacturer-origin examples (none yet). `data/reviews/<model_id>.json` content-bound review records (none yet).
- `tools/`: `selpn.py` engine, `verify.py` evidence tracks, `canon.py` hashing, `index.py`, `manifest.py`, `build_kb.py` (seed only).
- `tests/test_catalog.py` 55 tests. Passing tests are NOT manufacturer approval or engineering acceptance.

## Coverage today (honest)
Unchanged from v1: SEL-451-5, 411L, 751A (extracted, unverified), 710 and 311L (legacy documents), 751/487E/351S/700G (no field data).
No product has a verified layout, a reviewed extraction, or a manufacturer golden case. All current states remain unverified.

## Findings that matter for BOM accuracy
1. **Digits are not portable across families.** PS digit `4` = 48-125 V (400-series) but 125/250 V (311L); conformal coat is X/2 vs 0/1; letters A-H mean DI voltage in 700-series, card type elsewhere. Mappings are per-product, never global.
2. **Two part-number layers.** (a) whole-relay MOT string; (b) field-installable SELect card kits `97xxL<slot code><coat>` (e.g. `9717LA0_`). The card kit PN embeds the MOT slot code, but the `97xx` platform digits vary per relay. See `grammar.json`.
3. **Relay-stored PART NUM may omit the MOT leading zero** (SEL-751 example `751001B5X1X7086020X`, 19 chars). Decide which form the BOM carries.
4. Constraints marked `inferred` are my reading, not SEL's text; `stated` ones come from MOT footnotes.

## Usage
```
python3 tests/test_catalog.py
python3 tools/selpn.py check SEL-451-5 '{...selection...}'
python3 tools/index.py [search "48-125"|status|digest]     # derived index
python3 tools/manifest.py write|check
python3 tools/verify.py status SEL-451-5 | layout SEL-451-5 | review <model> <track> <reviewer> <YYYY-MM-DD> <sha256,...> "<note>"
```
