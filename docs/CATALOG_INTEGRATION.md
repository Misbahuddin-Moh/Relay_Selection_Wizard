# Read-only catalog integration contract

The first catalog integration consumes inert, version-pinned records from `backend/data/sel_ordering_kb`. It does not execute upstream tooling, perform network downloads, parse/assemble order codes, select variants or allocate hardware.

## Upstream and package identity

Initial source: `Misbahuddin-Moh/Relay_Selection_Wizard`, `sel_ordering_kb`, commit `3cda2bcc36450d9bbf6470b7a78ad54d251bcedf`. Nine raw product records are preserved, including their unresolved/legacy statuses. An exact source-record identity is not evidence that the record suits a selected relay role.

`manifest.json` contains `contract_version:1`, a pinned `source_release_sha`, source URL and product entries `{file,model,product_sha256}`. The product digest is SHA-256 of UTF-8 JSON encoded with Python `json.dumps(product,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)`. It is a semantic JSON hash, not a byte hash of a PDF. Ordering of JSON object keys is immaterial; array order and every data value remain significant.

The manifest source is the reviewed KB release; underlying manufacturer artifact hashes remain separate evidence. A SHA is provenance/version binding, not proof of correctness or authorization.

## Adapter

`assess_catalog(product, requested_model, source_release_sha, expected_product_sha256=None)` inspects the record without importing KB code. Runtime consumers always provide the manifest's expected hash. `docs/catalog-contract.schema.json` documents the documentary record shape; semantic checks in `backend/catalog_readiness.py` additionally validate ordering, option widths, references, source pins and unsupported rule vocabulary.

Output includes exact requested/catalog model strings, source release, canonical product hash, adapter/contract versions, three independent tracks, and structured blockers. Each blocker identifies a code, data path, explanation and affected tracks.

| Track | Meaning |
|---|---|
| `code_layout` | Required ordering grammar/evidence is absent or documentary references have been recorded. No generated code is certified. |
| `hardware_compatibility` | Required compatibility evidence is absent or documentary references have been recorded. No joint resource allocation is established. |
| `application_review` | Required application references are absent or recorded. No project engineering approval is granted. |

Track status is `blocked` or `evidence_recorded`. The latter means references passed presence/shape checks, not that their content/authenticity has been independently established. Every result retains `catalog_evidence_only:true`, `complete_fit:false`, `procurement_ready:false`, `order_code:null`.

Legacy records without versioned evidence remain inspectable and blocked. Inferred/high-confidence extraction labels do not become manufacturer verification. Unsupported fields/rule types, malformed data, absent/incorrect hashes, unknown widths, unresolved tokens, missing provenance and incomplete products produce blockers. Generic family identifiers cannot match a different exact variant.

Optional v1 `readiness_evidence` has source_revision, layout_review, hardware_review and application_review documentary references, plus golden_cases. Each reference includes source_id, source_sha256, locator, revision, exact model, reviewer and reviewed_on. Golden references additionally require an accepted independent source_type; generated fixtures are blocked. These checks cannot authenticate a claimed source by themselves.

## API and UI

`/api/engineering/io` returns `catalog_readiness` alongside existing partial engineering results. Package identity includes the manifest, all assessed products, adapter and loader code. The package fingerprint participates in the engineering result fingerprint. Catalog changes invalidate old results without changing existing point-accounting arithmetic or turning saved decisions into approvals.

No catalog readiness/approval object is imported into portable project decisions. Future product selection will need an explicit exact-variant/configuration workflow; it is not inferred from display labels.

The shortlist shows package source, all product tracks and detailed blockers. It is bound to the current backend result and disappears while a changed requirement is recalculating. No new order-code input or purchase action exists.

A missing/corrupt/unsupported package produces a controlled unavailable response with an empty product list, issue code and content-sensitive fingerprint. Existing engineering accounting remains available and partial. A hash mismatch in an otherwise readable product is shown as a blocker on that product.

## Next contract boundary

The current JSON schema is a strict documentary ingestion contract, not the typed hardware allocator schema. Adding capabilities, slot matrices or new predicate types requires a coordinated schema/adapter revision and tests; do not silently relax the parser. The KB developer should deliver typed source-backed resources and compatibility constraints for agreed exact variants. The Wizard will then add exact-variant selection, signal-to-terminal assignment and joint physical allocation. Manufacturer-accepted configurations and project release remain separate evidence gates.

See `docs/SEL_KB_REVIEW.md` for defect reproductions, outside-developer scope and acceptance criteria. All current imported records remain blocked; there is no manufacturer-validated ordering path yet.
