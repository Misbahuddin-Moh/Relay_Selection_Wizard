# SEL Relay Ordering-Code Knowledge Base

Indexed, source-attributed model of how SEL builds part numbers (Model Option Tables, "MOTs"), for a
SLD -> relay BOM web app where an EOR reviews the output.

## Principle: never emit a part number the KB cannot prove
Every product has `layout_verified` (default `false`). While false, `assemble()` returns a **spec**
(field -> code -> description, with confidence + warnings) and `issuable=false`. A product is promoted
only by `tools/promote.py`, which requires real SEL-issued part numbers (`data/golden/<model>.txt`) to
decode cleanly and to exercise >=2 options per field. `build_kb.py` will not overwrite a promoted product.

## Layout
- `data/products/*.json` one file per relay: fields (order, width, options, extra-cost flag, confidence),
  constraints (stated vs inferred), accessories, open questions, source doc + date.
- `data/grammar.json` cross-product conventions, cross-family traps, SELect card sub-part-number pattern.
- `data/sel_kb.sqlite` built index (FTS5 over every option). `tools/index.py search "48-125"`.
- `tools/selpn.py` validate / assemble / parse.  `tools/promote.py` verification gate.  `tests/` 12 tests.

## Coverage today (honest)
| Product | Status | Notes |
|---|---|---|
| SEL-451-5 | extracted, unverified | 16 fields; widths of `sec_voltage`, `eth_ports` unresolved; LEA code garbled |
| SEL-411L | extracted, unverified | 17 fields; several doubled-char widths unresolved |
| SEL-751A | extracted, unverified | position order inferred; legacy product |
| SEL-710 | legacy doc (2018, not -5) | widths explicit; needs the 710-5 MOT |
| SEL-311L-0/-6 | legacy doc (2013) | channel X/Y order inferred |
| SEL-751 (current) | **not extractable** | MOT PDF (WI-9222, 2026-05-20) is image-only; datasheet gives Slot E = digits 12-13, Z = 14-15 |
| SEL-487E/-3/-4/-5, 351S, 700G | header only | MOT link not found / not yet ingested |
| 487B, 421, 401, 735, 787-2/3/4, 710-5, 2414/2411, 3555, ... | not started | |

`SEL-787` legacy doc was extracted but dropped from KB (low confidence, superseded by 787-2/-3/-4 WI-12174).

## Findings that matter for BOM accuracy
1. **Digits are not portable across families.** PS digit `4` = 48-125 V (400-series) but 125/250 V (311L); conformal coat is X/2 vs 0/1; letters A-H mean DI voltage in 700-series, card type elsewhere. Mappings are per-product, never global.
2. **Two part-number layers.** (a) whole-relay MOT string; (b) field-installable SELect card kits `97xxL<slot code><coat>` (e.g. `9717LA0_`). The card kit PN embeds the MOT slot code, but the `97xx` platform digits vary per relay. See `grammar.json`.
3. **Relay-stored PART NUM may omit the MOT leading zero** (SEL-751 example `751001B5X1X7086020X`, 19 chars). Decide which form the BOM carries.
4. Constraints marked `inferred` are my reading, not SEL's text; `stated` ones come from MOT footnotes.

## Why not "complete" yet - and the fastest way to get there
The shell here is blocked from selinc.com and WebFetch returns an LLM summary of each PDF, which loses table
column alignment. Fixes, best first:
1. **Golden part numbers** - 5-10 real SEL PNs per relay (past quotes, nameplates, or SEL's own *Configure and Order*
   output). These settle widths/order/leading-zero questions deterministically and unlock `promote.py`.
2. **Raw MOT PDFs** attached or placed in a connected folder -> I can parse with a layout-aware extractor instead of a summary,
   and OCR the image-only SEL-751 MOT.
3. **SEL Popular Models** - SEL publishes pre-configured part numbers per product page. For PV-substation scope, restricting
   the first release to Popular Models (+ golden PNs) is the most defensible accuracy anchor.
4. Treat SEL's Configure-and-Order / your SEL rep as the final authority; the EOR review should compare against it.

## Usage
```
python3 tools/build_kb.py && python3 tools/index.py && python3 tests/test_kb.py
python3 tools/selpn.py assemble SEL-710 '{"slot_a":"1A","slot_b":"000","slot_c":"0X","slot_d":"0X","slot_e":"0X","slot_z":"85","conformal":"0"}'
python3 tools/index.py search '"arc-flash"'
python3 tools/promote.py SEL-710 --min 5      # after adding data/golden/SEL-710.txt
```
