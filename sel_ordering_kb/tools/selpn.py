#!/usr/bin/env python3
"""SEL ordering-code catalog engine (schema v2).  FAIL-CLOSED.

check(model_id, selection, application=None)  -> structured result; status is one of
    unsupported | invalid | unresolved | validated_within_scope
  An empty problem list NEVER means "valid": only status == validated_within_scope does, and even
  that means "consistent with the reviewed catalog within its stated scope" -- not manufacturer-orderable.
assemble(...) -> adds an inert, clearly-labelled preview; `manufacturer_orderable` is always False.
  Procurement/manufacturer release lives OUTSIDE this engine.
validate(...) -> compat shim returning list[str] of everything that is not a clean validated_within_scope.

Verification is never read from catalog JSON. Catalog JSON asserting verification is rejected.
Evidence/layout state comes only from content-bound review records (see verify.py).
"""
import json, pathlib, sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
VALIDATOR_VERSION = "2.0.0"
SCHEMA_VERSION = 2

RULE_TYPES = {"requires", "requires_any", "max_per_chassis"}
SCOPES = {"ordering", "application"}
FIELD_CONF = {"high", "medium", "low"}
RULE_CONF = {"stated", "inferred"}
TOKEN_STATUS = {"literal_verified", "extracted", "author_label", "placeholder"}
SOURCE_KINDS = {"mot_pdf", "datasheet", "none"}
BLOCKS = {"layout", "hardware", "application"}
FORBIDDEN_KEYS = {"layout_verified", "verified", "review_state", "issuable", "orderable"}


# ------------------------------------------------------------------ loading
def list_models(data_dir=DATA):
    return sorted(p.stem for p in (pathlib.Path(data_dir) / "products").glob("*.json"))


def load(model_id, data_dir=None):
    data_dir = pathlib.Path(data_dir or DATA)
    p = data_dir / "products" / f"{model_id}.json"
    if not p.exists():  # exact match only: no family aliases, no case folding
        raise KeyError(f"unknown model_id {model_id!r}; exact ids: {list_models(data_dir)}")
    return json.loads(p.read_text())


# ------------------------------------------------------------------ catalog schema gate
def _err(code, path, msg):
    return {"code": code, "path": path, "msg": msg}


def _pred_errors(pred, fields, path):
    errs = []
    if not isinstance(pred, dict):
        return [_err("RULE_SHAPE", path, "predicate must be an object")]
    extra = set(pred) - {"field", "in", "not_in"}
    if extra:
        errs.append(_err("RULE_SHAPE", path, f"unknown predicate keys {sorted(extra)}"))
    if pred.get("field") not in fields:
        return errs + [_err("RULE_REF", path, f"unknown field {pred.get('field')!r}")]
    ops = [k for k in ("in", "not_in") if k in pred]
    if len(ops) != 1:
        return errs + [_err("RULE_SHAPE", path, "predicate needs exactly one of in / not_in")]
    vals = pred[ops[0]]
    if not isinstance(vals, list) or not vals or not all(isinstance(v, str) for v in vals):
        return errs + [_err("RULE_SHAPE", path, f"{ops[0]} must be a non-empty list of strings")]
    for v in vals:
        if v not in fields[pred["field"]]:
            errs.append(_err("RULE_REF", path, f"option {v!r} not in field {pred['field']!r}"))
    return errs


def validate_catalog(p):
    """Return list of catalog errors. Any error => the product is unsupported (fail closed)."""
    E = []
    if not isinstance(p, dict):
        return [_err("SCHEMA", "$", "product must be an object")]
    if p.get("schema_version") != SCHEMA_VERSION:
        E.append(_err("SCHEMA_VERSION", "schema_version", f"expected {SCHEMA_VERSION}, got {p.get('schema_version')!r}"))
    for k in FORBIDDEN_KEYS & set(p):
        E.append(_err("ASSERTED_VERIFICATION", k, "verification/approval may not be asserted in catalog data"))
    for k in ("model_id", "identity", "source", "fields", "constraints", "unresolved", "accessories"):
        if k not in p:
            E.append(_err("SCHEMA", k, "missing required key"))
    if E and any(e["code"] == "SCHEMA" for e in E):
        return E
    idn = p["identity"]
    if not (isinstance(idn, dict) and isinstance(idn.get("variants"), list) and isinstance(idn.get("variant_resolved"), bool)):
        E.append(_err("IDENTITY", "identity", "needs variants:list and variant_resolved:bool"))
    src = p["source"]
    if not isinstance(src, dict) or src.get("kind") not in SOURCE_KINDS or not src.get("doc_id"):
        E.append(_err("PROVENANCE", "source", f"source.kind must be one of {sorted(SOURCE_KINDS)} and doc_id non-empty"))
    elif src["kind"] == "none" and p["fields"]:
        E.append(_err("PROVENANCE", "source", "fields present but source.kind is 'none'"))
    fields = {}
    if not isinstance(p["fields"], list):
        return E + [_err("SCHEMA", "fields", "must be a list")]
    for i, f in enumerate(p["fields"]):
        path = f"fields[{i}]"
        if f.get("id") in fields:
            E.append(_err("DUPLICATE_ID", path, f"duplicate field id {f.get('id')!r}"))
        if FORBIDDEN_KEYS & set(f):
            E.append(_err("ASSERTED_VERIFICATION", path, "verification keys not allowed on fields"))
        if f.get("confidence") not in FIELD_CONF:
            E.append(_err("FIELD", path, "confidence must be high|medium|low"))
        w = f.get("width")
        if w is not None and not (isinstance(w, int) and not isinstance(w, bool) and w >= 1):
            E.append(_err("FIELD", path, "width must be null or int >= 1"))
        opts = f.get("options")
        if not isinstance(opts, list) or not opts:
            E.append(_err("FIELD", path, "options must be a non-empty list")); opts = []
        codes = {}
        for j, o in enumerate(opts):
            op = f"{path}.options[{j}]"
            c = o.get("code")
            if not isinstance(c, str) or not c:
                E.append(_err("OPTION", op, "code must be a non-empty string")); continue
            if c in codes:
                E.append(_err("DUPLICATE_ID", op, f"duplicate option code {c!r}"))
            codes[c] = o
            if o.get("token_status") not in TOKEN_STATUS:
                E.append(_err("OPTION", op, f"token_status must be one of {sorted(TOKEN_STATUS)}"))
            if not isinstance(o.get("extra_cost"), bool):
                E.append(_err("OPTION", op, "extra_cost must be bool"))
            if isinstance(w, int) and o.get("token_status") != "placeholder" and len(c) != w:
                E.append(_err("OPTION", op, f"code {c!r} length {len(c)} != field width {w}"))
        if isinstance(f.get("id"), str):
            fields[f["id"]] = codes
    seen = set()
    for i, c in enumerate(p["constraints"]):
        path = f"constraints[{i}]"
        cid = c.get("id")
        if not isinstance(cid, str) or not cid:
            E.append(_err("RULE_SHAPE", path, "rule id required")); continue
        if cid in seen:
            E.append(_err("DUPLICATE_ID", path, f"duplicate rule id {cid!r}"))
        seen.add(cid)
        if FORBIDDEN_KEYS & set(c):
            E.append(_err("ASSERTED_VERIFICATION", path, "verification keys not allowed on rules"))
        t = c.get("type")
        if t not in RULE_TYPES:
            E.append(_err("UNSUPPORTED_RULE_TYPE", path, f"rule type {t!r} is not supported by validator {VALIDATOR_VERSION}")); continue
        if c.get("scope") not in SCOPES:
            E.append(_err("RULE_SHAPE", path, "scope must be ordering|application"))
        if c.get("confidence") not in RULE_CONF:
            E.append(_err("RULE_SHAPE", path, "confidence must be stated|inferred"))
        if not c.get("note"):
            E.append(_err("RULE_SHAPE", path, "note required"))
        if t in ("requires", "requires_any"):
            trig = [k for k in ("if", "when") if k in c]
            if len(trig) != 1:
                E.append(_err("RULE_SHAPE", path, "exactly one of if / when required")); continue
            if "if" in c:
                E += _pred_errors(c["if"], fields, path + ".if")
                if c["scope"] != "ordering":
                    E.append(_err("RULE_SHAPE", path, "'if' rules must have scope ordering"))
            else:
                w_ = c["when"]
                if not (isinstance(w_, dict) and set(w_) == {"input", "equals"} and isinstance(w_["input"], str)):
                    E.append(_err("RULE_SHAPE", path, "when must be {input, equals}"))
                if c["scope"] != "application":
                    E.append(_err("RULE_SHAPE", path, "'when' rules must have scope application"))
            if t == "requires":
                E += _pred_errors(c.get("then"), fields, path + ".then")
            else:
                anyl = c.get("any")
                if not isinstance(anyl, list) or len(anyl) < 2:
                    E.append(_err("RULE_SHAPE", path, "any must be a list of >=2 predicates"))
                else:
                    for k, pr in enumerate(anyl):
                        E += _pred_errors(pr, fields, f"{path}.any[{k}]")
        else:  # max_per_chassis
            fl, mc, mx = c.get("fields"), c.get("match_codes"), c.get("max")
            if not (isinstance(fl, list) and fl and all(x in fields for x in fl)):
                E.append(_err("RULE_REF", path, "fields must be a non-empty list of existing field ids"))
            elif not (isinstance(mc, list) and mc and all(isinstance(x, str) and any(x in fields[f] for f in fl) for x in mc)):
                E.append(_err("RULE_REF", path, "match_codes must be non-empty and exist in the referenced fields"))
            if not (isinstance(mx, int) and not isinstance(mx, bool) and mx >= 1):
                E.append(_err("RULE_SHAPE", path, "max must be int >= 1"))
            if c.get("scope") != "ordering":
                E.append(_err("RULE_SHAPE", path, "max_per_chassis must have scope ordering"))
    uids = set()
    for i, u in enumerate(p["unresolved"]):
        path = f"unresolved[{i}]"
        if not (isinstance(u, dict) and u.get("id") and u.get("text") and isinstance(u.get("blocks"), list)
                and set(u["blocks"]) <= BLOCKS):
            E.append(_err("UNRESOLVED", path, f"needs id, text, blocks subset of {sorted(BLOCKS)}"))
        elif u["id"] in uids:
            E.append(_err("DUPLICATE_ID", path, f"duplicate unresolved id {u['id']!r}"))
        else:
            uids.add(u["id"])
    return E


# ------------------------------------------------------------------ rule evaluation
def _pv(pred, sel):
    v = sel.get(pred["field"])
    return (v in pred["in"]) if "in" in pred else (v is not None and v not in pred["not_in"])


def _fields_of(rule):
    if rule["type"] == "max_per_chassis":
        return list(rule["fields"])
    out = [rule["if"]["field"]] if "if" in rule else []
    out += [rule["then"]["field"]] if "then" in rule else [a["field"] for a in rule.get("any", [])]
    return out


def _opt_map(field):
    return {o["code"]: o for o in field["options"]}


def _load_reviews(model_id, product, data_dir):
    import verify
    return verify.track_states(model_id, product=product, data_dir=data_dir)


def check(model_id, sel, application=None, product=None, data_dir=None, tracks=None):
    data_dir = pathlib.Path(data_dir or DATA)
    p = product if product is not None else load(model_id, data_dir)
    base = {"model_id": model_id, "validator_version": VALIDATOR_VERSION, "problems": [], "unresolved": [],
            "catalog_errors": [], "unsupported": [], "not_evaluated": {"rules": [], "application_rules": []},
            "scope_statement": "Catalog consistency only. Not manufacturer-orderable; not engineering or procurement approval."}
    errs = validate_catalog(p)
    if errs:
        return dict(base, status="unsupported", catalog_errors=errs)
    if p["model_id"] != model_id:
        return dict(base, status="unsupported", unsupported=[{"code": "MODEL_ID_MISMATCH", "msg": f"record is {p['model_id']!r}"}])
    if not p["identity"]["variant_resolved"]:
        base["unsupported"].append({"code": "VARIANT_UNRESOLVED", "msg": "generic family record; exact variant required (no inference)"})
    if not p["fields"]:
        base["unsupported"].append({"code": "NO_FIELD_DATA", "msg": "no ordering fields ingested for this product"})
    if p["source"]["kind"] == "none":
        base["unsupported"].append({"code": "NO_SOURCE", "msg": "no manufacturer source artifact identified"})
    if base["unsupported"]:
        return dict(base, status="unsupported")

    fields = {f["id"]: f for f in p["fields"]}
    app = application or {}
    for fid, code in sel.items():
        if fid not in fields:
            base["problems"].append({"code": "UNKNOWN_FIELD", "msg": f"unknown field {fid!r}"})
        elif code not in _opt_map(fields[fid]):
            base["problems"].append({"code": "UNKNOWN_CODE", "msg": f"{fid}: {code!r} is not a known option"})
    missing = [fid for fid in fields if fid not in sel]
    for r in p["constraints"]:
        if r["scope"] == "application" and r["when"]["input"] not in app:
            base["not_evaluated"]["application_rules"].append(r["id"]); continue
        if any(fid not in sel for fid in _fields_of(r)):
            base["not_evaluated"]["rules"].append(r["id"]); continue
        if r["type"] == "max_per_chassis":
            n = sum(1 for fid in r["fields"] if sel[fid] in r["match_codes"])
            bad = n > r["max"]
        else:
            trig = _pv(r["if"], sel) if "if" in r else (app[r["when"]["input"]] == r["when"]["equals"])
            if not trig:
                continue
            ok = _pv(r["then"], sel) if r["type"] == "requires" else any(_pv(a, sel) for a in r["any"])
            bad = not ok
        if bad:
            base["problems"].append({"code": "RULE_VIOLATION", "rule": r["id"], "scope": r["scope"],
                                     "evidence": r["confidence"], "msg": r["note"]})
    if base["problems"]:
        return dict(base, status="invalid")

    # ---- anything that prevents a clean positive result
    U = base["unresolved"]
    if missing:
        U.append({"code": "SELECTION_INCOMPLETE", "msg": f"no selection for: {missing}"})
    for u in p["unresolved"]:
        if set(u["blocks"]) & {"layout", "hardware"}:
            U.append({"code": "CATALOG_UNRESOLVED", "id": u["id"], "msg": u["text"], "blocks": u["blocks"]})
    nw = [f["id"] for f in p["fields"] if f["width"] is None]
    if nw:
        U.append({"code": "WIDTH_UNKNOWN", "msg": f"field widths unknown: {nw}"})
    weak = [f["id"] for f in p["fields"] if f["confidence"] != "high"]
    if weak:
        U.append({"code": "EXTRACTION_CONFIDENCE", "msg": f"non-high extraction confidence: {weak}"})
    inf = [r["id"] for r in p["constraints"] if r["confidence"] != "stated"]
    if inf:
        U.append({"code": "INFERRED_RULES", "msg": f"rules inferred, not stated by manufacturer: {inf}"})
    tr = tracks if tracks is not None else _load_reviews(model_id, p, data_dir)
    for t in ("data_extraction_review", "compatibility_rules_review"):
        if tr[t]["state"] != "reviewed":
            U.append({"code": "REVIEW_" + tr[t]["state"].upper(), "msg": f"{t}: {tr[t]['state']}"})
    if base["not_evaluated"]["rules"]:
        U.append({"code": "RULES_NOT_EVALUATED", "msg": f"rules not evaluable on this selection: {base['not_evaluated']['rules']}"})
    return dict(base, status="unresolved" if U else "validated_within_scope", tracks=tr)


def validate(model_id, sel, application=None, **kw):
    """Compat shim: list[str]. Non-empty for anything other than validated_within_scope."""
    r = check(model_id, sel, application, **kw)
    out = [e["msg"] for e in r["catalog_errors"]] + [e["msg"] for e in r["unsupported"]]
    out += [f"[{x.get('rule', x['code'])}] {x['msg']}" for x in r["problems"]]
    out += [f"(unresolved) {x['msg']}" for x in r["unresolved"]]
    return out


# ------------------------------------------------------------------ representation + assemble/parse
def normalize(model_id, s, data_dir=None):
    """Return (canonical_string_with_prefix, representation). Accepts the relay-stored form that omits a
    leading zero of the prefix. The representation used in a BOM is a project decision, not guessed here."""
    pre = load(model_id, data_dir)["prefix"]
    if s.startswith(pre):
        return s, "mot_full"
    if pre.startswith("0") and s.startswith(pre[1:]):
        return "0" + s, "relay_stored_no_leading_zero"
    raise ValueError(f"{s!r} does not start with prefix {pre!r} (or {pre[1:]!r})")


def parse(model_id, s, data_dir=None, product=None):
    p = product if product is not None else load(model_id, data_dir)
    errs = validate_catalog(p)
    if errs:
        raise ValueError(f"catalog invalid: {errs[0]['code']} at {errs[0]['path']}")
    s, _ = normalize(model_id, s, data_dir) if product is None else (s, "mot_full")
    body, i, out = s[len(p["prefix"]):], 0, {}
    for f in p["fields"]:
        if f["width"] is None:
            raise ValueError(f"cannot parse: field {f['id']} has unresolved width")
        code = body[i:i + f["width"]]
        if code not in _opt_map(f):
            raise ValueError(f"field {f['id']} at offset {i}: {code!r} not a known option")
        out[f["id"]] = code
        i += f["width"]
    if i != len(body):
        raise ValueError(f"{len(body) - i} trailing chars: {body[i:]!r}")
    return out


def export_tokens(model_id, data_dir=None):
    """Only literal manufacturer-verified symbols may be exported. Nothing qualifies until a source review upgrades it."""
    p = load(model_id, data_dir)
    return {f["id"]: [o["code"] for o in f["options"] if o["token_status"] == "literal_verified"] for f in p["fields"]}


def assemble(model_id, sel, application=None, data_dir=None, product=None):
    import verify
    p = product if product is not None else load(model_id, data_dir)
    r = check(model_id, sel, application, product=product, data_dir=data_dir)
    lay = verify.layout_scope(model_id, sel, product=p, data_dir=data_dir) if r["status"] != "unsupported" else {"state": "unverified"}
    tokens, parts, all_known = [], [], r["status"] != "unsupported"
    if r["status"] != "unsupported":
        for f in p["fields"]:
            code = sel.get(f["id"]); o = _opt_map(f).get(code, {})
            tokens.append({"field": f["id"], "code": code, "desc": o.get("desc"), "token_status": o.get("token_status"),
                           "extraction_confidence": f["confidence"], "width": f["width"]})
            if f["width"] is None or code is None or code not in _opt_map(f):
                all_known = False
            parts.append(code or "?")
    literal = all_known and all(t["token_status"] == "literal_verified" for t in tokens)
    preview = (p["prefix"] + "".join(parts)) if all_known else None
    return {"model_id": model_id, "check": r, "tokens": tokens,
            "order_string": preview if (literal and lay["state"] == "layout_verified_within_scope" and lay.get("selection_within_scope")) else None,
            "unverified_preview": preview if not literal or lay["state"] != "layout_verified_within_scope" else None,
            "layout_verification": lay,
            "manufacturer_orderable": False,
            "limitations": ["Catalog engine never grants manufacturer or procurement release.",
                            "unverified_preview is a parser/debug aid, NOT a part number."],
            "accessories": p["accessories"]}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, model = sys.argv[1], sys.argv[2]
    if cmd == "parse":
        print(json.dumps(parse(model, sys.argv[3]), indent=2))
    elif cmd == "check":
        print(json.dumps(check(model, json.loads(sys.argv[3]), json.loads(sys.argv[4]) if len(sys.argv) > 4 else None), indent=2))
    elif cmd == "assemble":
        print(json.dumps(assemble(model, json.loads(sys.argv[3])), indent=2))
