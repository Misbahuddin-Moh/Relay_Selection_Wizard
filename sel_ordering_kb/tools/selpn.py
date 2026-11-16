#!/usr/bin/env python3
"""SEL part-number engine over the JSON knowledge base.

  validate(model, selection)  -> list of problems (unknown codes, violated constraints)
  assemble(model, selection)  -> {"tokens", "string", "issuable", "warnings"}
  parse(model, string)        -> best-effort decode (only when all widths are known)

POLICY: `issuable` is True only when product.layout_verified is True AND no warnings.
The BOM app should show unverified output as a *spec* (tokens + descriptions) for EOR review,
never as an orderable part number.
"""
import json, pathlib, sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def load(model):
    p = DATA / "products" / f"{model}.json"
    if not p.exists():
        raise KeyError(f"unknown model {model!r}; have: {sorted(x.stem for x in (DATA/'products').glob('*.json'))}")
    return json.loads(p.read_text())


def _opt_map(field):
    return {o["code"]: o for o in field["options"]}


def validate(model, sel):
    prod = load(model)
    probs = []
    fields = {f["id"]: f for f in prod["fields"]}
    for fid, code in sel.items():
        if fid not in fields:
            probs.append(f"unknown field {fid!r}")
        elif code not in _opt_map(fields[fid]):
            probs.append(f"{fid}: code {code!r} not in KB options {sorted(_opt_map(fields[fid]))[:12]}...")
    for fid in fields:
        if fid not in sel:
            probs.append(f"{fid}: no selection")
    for c in prod["constraints"]:
        if c["type"] == "requires":
            iff, then = c["if"], c["then"]
            v = sel.get(iff["field"])
            trig = (v in iff["in"]) if "in" in iff else (v is not None and v not in iff["not_in"])
            if trig:
                tv = sel.get(then["field"])
                ok = (tv in then["in"]) if "in" in then else (tv is not None and tv not in then["not_in"])
                if not ok:
                    probs.append(f"[{c['id']}] ({c['confidence']}) {c['note']}")
        elif c["type"] == "max_per_chassis":
            n = sum(1 for f in c["fields"] if str(sel.get(f, "")).startswith(c["match_prefix"])
                    and sel.get(f) != "0X")
            if n > c["max"]:
                probs.append(f"[{c['id']}] ({c['confidence']}) {c['note']} (found {n})")
    return probs


def assemble(model, sel):
    prod = load(model)
    warnings = list(validate(model, sel))
    tokens, parts, complete = [], [], True
    for f in prod["fields"]:
        code = sel.get(f["id"])
        desc = _opt_map(f).get(code, {}).get("desc", "?")
        tokens.append({"field": f["id"], "name": f["name"], "code": code, "desc": desc,
                       "confidence": f["confidence"], "width": f["width"]})
        if f["width"] is None or code is None:
            complete = False
        elif len(code) != f["width"]:
            warnings.append(f"{f['id']}: code {code!r} length {len(code)} != declared width {f['width']}")
        if f["confidence"] == "low":
            warnings.append(f"{f['id']}: low-confidence field")
        parts.append(code or "?")
    string = (prod.get("prefix", "") + "".join(parts)) if complete else None
    if not prod["layout_verified"]:
        warnings.append("layout NOT verified against real SEL part numbers -- spec only, not orderable")
    issuable = bool(string) and prod["layout_verified"] and not [w for w in warnings if "layout NOT" not in w]
    return {"model": model, "prefix": prod.get("prefix"), "tokens": tokens, "string": string,
            "issuable": issuable, "warnings": warnings,
            "accessories": prod.get("accessories", []), "open_questions": prod.get("open_questions", [])}


def parse(model, s):
    prod = load(model)
    pre = prod.get("prefix", "")
    if not s.startswith(pre):
        raise ValueError(f"{s!r} does not start with prefix {pre!r}")
    body, i, out = s[len(pre):], 0, {}
    for f in prod["fields"]:
        if f["width"] is None:
            raise ValueError(f"cannot parse: field {f['id']} has unresolved width (see open_questions)")
        code = body[i:i + f["width"]]
        if code not in _opt_map(f):
            raise ValueError(f"field {f['id']} at offset {i}: {code!r} not a known option")
        out[f["id"]] = code
        i += f["width"]
    if i != len(body):
        raise ValueError(f"{len(body) - i} trailing chars after last field: {body[i:]!r}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, model = sys.argv[1], sys.argv[2]
    if cmd == "parse":
        print(json.dumps(parse(model, sys.argv[3]), indent=2))
    elif cmd == "assemble":
        print(json.dumps(assemble(model, json.loads(sys.argv[3])), indent=2))
