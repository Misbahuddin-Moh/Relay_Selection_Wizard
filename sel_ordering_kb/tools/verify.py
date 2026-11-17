#!/usr/bin/env python3
"""Evidence-bound verification. Replaces tools/promote.py.

Four INDEPENDENT tracks, each bound to content hashes (never a boolean in product JSON):
  data_extraction_review      human attests fields/options match the raw manufacturer artifact  (record_review)
  code_layout                 computed: manufacturer-origin golden cases decode to reviewer-stated meanings (verify_layout)
  compatibility_rules_review  human attests constraints match manufacturer footnotes/tables      (record_review)
  configuration_evidence      out of scope for the catalog (manufacturer confirmation / engineering release)

A track is `stale` when the product record, golden set, validator version or recorded source hashes change.
Synthetic cases can never authorise anything. A review record is an attestation with provenance, not
authentication of the artifact; the Wizard/engineering release gates remain separate.

Golden file: data/golden/<model_id>.json
{"schema_version":1,"model_id":"SEL-451-5","cases":[{
  "case_id":"...", "origin":"manufacturer"|"synthetic",
  "string":"<code>", "expected_selections":{"<field>":"<code>",...},   # taken from the SOURCE, not from the parser
  "source_artifact":{"doc_id":"...","sha256":"<64 hex>","revision":"...","locator":"page/table/row","path":"<optional local file to re-hash>"},
  "reviewer":"...", "review_date":"YYYY-MM-DD"}]}

CLI:  verify.py status <model_id> | layout <model_id> | review <model_id> <track> <reviewer> <date> <sha256,...> "<note>"
"""
import datetime, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import canon, selpn

HEX64 = re.compile(r"^[0-9a-f]{64}$")
TRACKS = ["data_extraction_review", "code_layout", "compatibility_rules_review", "configuration_evidence"]
HUMAN_TRACKS = {"data_extraction_review", "compatibility_rules_review"}


def _dd(data_dir):
    return pathlib.Path(data_dir or selpn.DATA)


def _review_file(model_id, data_dir):
    return _dd(data_dir) / "reviews" / f"{model_id}.json"


def _golden_file(model_id, data_dir):
    return _dd(data_dir) / "golden" / f"{model_id}.json"


def _load_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def _bindings(model_id, product, data_dir):
    g = _load_json(_golden_file(model_id, data_dir))
    return {"product_sha256": canon.sha256_obj(product), "validator_version": selpn.VALIDATOR_VERSION,
            "golden_sha256": canon.sha256_obj(g) if g is not None else None}


def track_states(model_id, product=None, data_dir=None):
    p = product if product is not None else selpn.load(model_id, data_dir)
    rec = (_load_json(_review_file(model_id, data_dir)) or {}).get("tracks", {})
    b = _bindings(model_id, p, data_dir)
    out = {}
    for t in TRACKS:
        r = rec.get(t)
        if t == "configuration_evidence":
            out[t] = {"state": "out_of_catalog_scope"}
        elif not r:
            out[t] = {"state": "not_started"}
        else:
            keys = ["product_sha256", "validator_version"] + (["golden_sha256"] if t == "code_layout" else [])
            stale = [k for k in keys if r.get(k) != b[k]]
            ok = "layout_verified_within_scope" if t == "code_layout" else "reviewed"
            out[t] = {"state": "stale" if stale else ok, "stale_because": stale,
                      "reviewer": r.get("reviewer"), "review_date": r.get("review_date"), "scope": r.get("scope")}
    return out


def record_review(model_id, track, reviewer, review_date, source_sha256s, note="", data_dir=None, product=None):
    """Human attestation, bound to the current product hash. Cannot be used for code_layout."""
    if track not in HUMAN_TRACKS:
        raise ValueError(f"track must be one of {sorted(HUMAN_TRACKS)}")
    if not reviewer or not reviewer.strip():
        raise ValueError("reviewer required")
    datetime.date.fromisoformat(review_date)
    if not source_sha256s or not all(HEX64.match(h) for h in source_sha256s):
        raise ValueError("at least one lowercase 64-hex source artifact sha256 required")
    p = product if product is not None else selpn.load(model_id, data_dir)
    errs = selpn.validate_catalog(p)
    if errs:
        raise ValueError(f"refusing to review an invalid catalog record: {errs[0]['code']} {errs[0]['path']}")
    b = _bindings(model_id, p, data_dir)
    path = _review_file(model_id, data_dir)
    rec = _load_json(path) or {"model_id": model_id, "tracks": {}}
    rec["tracks"][track] = {"reviewer": reviewer, "review_date": review_date, "source_sha256s": sorted(set(source_sha256s)),
                            "note": note, "product_sha256": b["product_sha256"], "validator_version": b["validator_version"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2, sort_keys=True))
    return rec["tracks"][track]


def _case_problems(c, product, data_dir):
    P = []
    for k in ("case_id", "string", "reviewer", "review_date"):
        if not c.get(k):
            P.append(f"missing {k}")
    if not isinstance(c.get("expected_selections"), dict) or not c.get("expected_selections"):
        P.append("expected_selections must be a non-empty object taken from the source")
    a = c.get("source_artifact") or {}
    if not a.get("doc_id") or not a.get("revision") or not a.get("locator"):
        P.append("source_artifact needs doc_id, revision, locator")
    if not HEX64.match(str(a.get("sha256", ""))):
        P.append("source_artifact.sha256 must be 64 lowercase hex")
    if a.get("path"):
        pth = pathlib.Path(a["path"])
        if not pth.exists():
            P.append(f"source_artifact.path not found: {pth}")
        elif canon.sha256_file(pth) != a.get("sha256"):
            P.append("source_artifact.path hash does not match sha256")
    try:
        datetime.date.fromisoformat(str(c.get("review_date")))
    except ValueError:
        P.append("review_date must be ISO date")
    if not P:
        try:
            parsed = selpn.parse(product["model_id"], c["string"], data_dir=data_dir)
        except ValueError as e:
            return [f"does not decode: {e}"]
        if parsed != c["expected_selections"]:
            diff = {k: (parsed.get(k), c["expected_selections"].get(k)) for k in set(parsed) | set(c["expected_selections"])
                    if parsed.get(k) != c["expected_selections"].get(k)}
            P.append(f"decoded selections differ from source-stated meanings: {diff}")
    return P


def verify_layout(model_id, data_dir=None):
    """Compute and (only on success) record the code_layout track. Never edits product JSON."""
    p = selpn.load(model_id, data_dir)
    errs = selpn.validate_catalog(p)
    if errs:
        return {"state": "rejected", "reasons": [f"catalog invalid: {e['code']} {e['path']}" for e in errs]}
    g = _load_json(_golden_file(model_id, data_dir))
    if not g or g.get("model_id") != model_id:
        return {"state": "not_started", "reasons": ["no golden file for this exact model_id"]}
    mf = [c for c in g.get("cases", []) if c.get("origin") == "manufacturer"]
    syn = [c for c in g.get("cases", []) if c.get("origin") == "synthetic"]
    other = [c for c in g.get("cases", []) if c.get("origin") not in ("manufacturer", "synthetic")]
    if other:
        return {"state": "rejected", "reasons": [f"unknown origin on {c.get('case_id')}" for c in other]}
    if not mf:
        return {"state": "not_started", "ignored_synthetic": len(syn),
                "reasons": ["no manufacturer-origin cases; synthetic cases never authorise verification"]}
    bad = {c.get("case_id", "?"): pr for c in mf if (pr := _case_problems(c, p, data_dir))}
    if bad:
        return {"state": "rejected", "reasons": bad}
    covered = {}
    for c in mf:
        for fid, code in selpn.parse(model_id, c["string"], data_dir=data_dir).items():
            covered.setdefault(fid, set()).add(code)
    scope = {"fields": {k: sorted(v) for k, v in covered.items()},
             "n_manufacturer_cases": len(mf), "n_synthetic_ignored": len(syn),
             "coverage": {f["id"]: f"{len(covered.get(f['id'], ()))}/{len(f['options'])} options"
                          for f in p["fields"]},
             "limitations": ["Layout only: field order/width/token positions for the listed field/option values.",
                             "Does not cover other options, cross-field interactions, hardware compatibility or procurement.",
                             "Case count/coverage is a metric, not a proof threshold."]}
    b = _bindings(model_id, p, data_dir)
    path = _review_file(model_id, data_dir)
    rec = _load_json(path) or {"model_id": model_id, "tracks": {}}
    rec["tracks"]["code_layout"] = {
        "reviewer": sorted({c["reviewer"] for c in mf}), "review_date": max(c["review_date"] for c in mf),
        "source_sha256s": sorted({c["source_artifact"]["sha256"] for c in mf}), "scope": scope, **b}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2, sort_keys=True))
    return {"state": "layout_verified_within_scope", "scope": scope}


def layout_scope(model_id, sel, product=None, data_dir=None):
    t = track_states(model_id, product=product, data_dir=data_dir)["code_layout"]
    out = {"state": t["state"], "stale_because": t.get("stale_because", []), "scope": t.get("scope"), "selection_within_scope": False}
    if t["state"] == "layout_verified_within_scope":
        sc = t["scope"]["fields"]
        out["selection_within_scope"] = bool(sel) and set(sel) == set(sc) and all(sel[k] in sc[k] for k in sel)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "status":
        print(json.dumps(track_states(a[1]), indent=2))
    elif len(a) >= 2 and a[0] == "layout":
        r = verify_layout(a[1]); print(json.dumps(r, indent=2)); sys.exit(0 if r["state"] != "rejected" else 1)
    elif len(a) >= 6 and a[0] == "review":
        print(json.dumps(record_review(a[1], a[2], a[3], a[4], a[5].split(","), a[6] if len(a) > 6 else ""), indent=2))
    else:
        print(__doc__)
