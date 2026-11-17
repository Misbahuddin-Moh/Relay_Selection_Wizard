# Status against the 2026-11-16 handoff acceptance checklist

Legend: DONE = implemented and tested here. PARTIAL = mechanism built, data missing. OPEN = not started / blocked on inputs.

| Checklist item | Status | Notes |
|---|---|---|
| Confirmed defect reproductions are automated regressions | DONE | git f7a6674 (against baseline) + `tests/test_catalog.py` |
| Exact variants and document revisions explicit; no family substitution | PARTIAL | Exact-id loading, `identity.variants`, `variant_resolved` enforced. Revisions known only for 451-5 (reviewer-reported) and 710 (WI-5180). 487E/751 still generic. |
| Unsupported/malformed rules and incomplete products fail closed | DONE | schema gate + `unsupported`/`unresolved` statuses |
| Literal tokens separated from internal labels/placeholders | PARTIAL | `token_status` enforced and gates export. Nothing is `literal_verified` yet; `internal_option_id` vs `ordering_token` split not introduced (codes are still both). |
| Source artifacts and golden cases carry durable provenance + independent expected meanings | PARTIAL | Golden schema + checks built. **No manufacturer golden case exists**; no raw artifact hashed. |
| Review scope content-bound, invalidated on change | DONE | `verify.py`; tested for product/token/golden/validator changes |
| Layout verification never becomes all-combination/procurement approval | DONE | scoped; `manufacturer_orderable` hard false; `order_string` null |
| Typed analog/digital/slot/function data sufficient for allocation | OPEN | Descriptions are still prose. Needs a coordinated schema/adapter revision with the Wizard (per the contract appendix). |
| SEL-451-5 source-backed positive and negative compatibility examples | PARTIAL | Voltage rule per board at B and C tested (both directions). Fixed-voltage symbol sets per board, empty-board voltage symbol, LEA/coating footnotes unresolved (U-451-3/4). |
| Catalog release passes schema, integrity, rule, external-example, invalidation tests | PARTIAL | All but "external-example" (no manufacturer examples to test against). |
| Wizard integration preserves partial budgets / unresolved evidence | n/a here | Wizard-side work; see CHANGELOG breaking changes. |
| Manufacturer confirmation and engineering/procurement authority stay separate gates | DONE (in this component) | Catalog never grants release. |

## What I could not do, and why
- The shell cannot reach selinc.com; WebFetch returns model summaries of PDFs. So **no raw PDF was retrieved or hashed**, and nothing in
  the catalog has been re-verified against the original artifact. The 451-5 revision/date and the "options 1, 5, 6" voltage statement come
  from the review document (and my earlier extraction note); they are marked reviewer-reported/`unreviewed`, not confirmed.
- I did not fabricate manufacturer golden cases. The tests use clearly labelled `TEST-MECHANISM-ONLY` fixtures in temp directories only.

## Inputs needed to continue (in priority order)
1. Raw SEL-451-5 MOT (WI-8789) as a file -> hash it, reconstruct columns/tokens/widths, resolve U-451-1..4, add page/row locators.
2. 5-10 SEL-issued 451-5 part numbers (quote/nameplate/Configure-and-Order) with their stated meanings -> `data/golden/SEL-451-5.json`.
3. The exact SEL-487E variant(s) in scope (-3/-4/-5) and their MOTs; current SEL-751 MOT in an extractable form.
4. Agreement with the Wizard developer on the typed-capability export (slots, CT/VT channels, DI/DO groups, ratings) before data entry.
