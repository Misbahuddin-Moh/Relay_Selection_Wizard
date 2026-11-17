#!/usr/bin/env python3
"""Immutable-style release manifest: pins every canonical record by SHA-256 of canonical JSON
(UTF-8, sorted keys, compact separators, ensure_ascii, non-finite rejected).

  python3 tools/manifest.py write    # regenerate data/manifest.json
  python3 tools/manifest.py check    # exit 1 if any record/grammar/index drifted from the manifest

Release history: bump KB_VERSION and append to CHANGELOG.md; never reuse a version for different content.
The manifest cannot contain its own commit id; the upstream commit is pinned by the consumer.
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import canon, index, selpn, verify

KB_VERSION = "2.0.0"
DATA = selpn.DATA
MANIFEST = DATA / "manifest.json"


def build(data_dir=DATA):
    prods = {}
    for m in selpn.list_models(data_dir):
        p = selpn.load(m, data_dir)
        t = verify.track_states(m, product=p, data_dir=data_dir)
        prods[m] = {"sha256": canon.sha256_obj(p), "schema_version": p["schema_version"],
                    "catalog_errors": len(selpn.validate_catalog(p)),
                    "tracks": {k: v["state"] for k, v in t.items()},
                    "n_fields": len(p["fields"]), "n_unresolved": len(p["unresolved"]),
                    "source": {k: p["source"].get(k) for k in ("kind", "doc_id", "revision", "doc_date", "sha256", "retrieval")}}
    g = json.loads((pathlib.Path(data_dir) / "grammar.json").read_text())
    return {"manifest_version": 1, "kb_version": KB_VERSION, "validator_version": selpn.VALIDATOR_VERSION,
            "schema_version": selpn.SCHEMA_VERSION, "baseline_commit": "3cda2bcc36450d9bbf6470b7a78ad54d251bcedf",
            "products": prods, "grammar_sha256": canon.sha256_obj(g),
            "derived": {"sqlite_rows_sha256": index.rows_digest(pathlib.Path(data_dir) / "sel_kb.sqlite")},
            "release_flags": {"manufacturer_orderable": False, "procurement_ready": False,
                              "note": "Catalog data is documentary. No product is manufacturer-confirmed."}}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    cur = build()
    if cmd == "write":
        MANIFEST.write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n"); print("wrote", MANIFEST)
    else:
        old = json.loads(MANIFEST.read_text())
        if old != cur:
            print("DRIFT: manifest does not match canonical data"); sys.exit(1)
        print("manifest OK")
