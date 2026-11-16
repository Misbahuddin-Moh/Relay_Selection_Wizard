#!/usr/bin/env python3
"""Promotion gate: a product's layout becomes `layout_verified` only if REAL SEL part numbers decode.

Golden file format (data/golden/<model>.txt), one per line:
    <real part number as issued by SEL (quote, nameplate, or SEL Configure & Order)>   # optional comment

    python3 tools/promote.py SEL-710 --min 5

Rules: every golden PN must parse with no unknown codes and no trailing chars, and pass validate().
Requires >= --min distinct golden PNs (default 5) that between them exercise >= 2 different options in
every field that has more than one option. Only then is layout_verified flipped to true.
Never edit layout_verified by hand.
"""
import argparse, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import selpn

DATA = selpn.DATA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--min", type=int, default=5)
    a = ap.parse_args()
    g = DATA / "golden" / f"{a.model}.txt"
    if not g.exists():
        sys.exit(f"no golden file {g}")
    pns = [l.split("#")[0].strip().replace(" ", "") for l in g.read_text().splitlines() if l.split("#")[0].strip()]
    pns = sorted(set(pns))
    prod = selpn.load(a.model)
    seen = {f["id"]: set() for f in prod["fields"]}
    bad = []
    for pn in pns:
        try:
            sel = selpn.parse(a.model, pn)
        except ValueError as e:
            bad.append((pn, str(e))); continue
        probs = [p for p in selpn.validate(a.model, sel)]
        if probs:
            bad.append((pn, "; ".join(probs))); continue
        for k, v in sel.items():
            seen[k].add(v)
    if bad:
        for pn, why in bad: print("FAIL", pn, "->", why)
        sys.exit(1)
    if len(pns) < a.min:
        sys.exit(f"only {len(pns)} golden PNs; need {a.min}")
    thin = [k for k, v in seen.items() if len(v) < 2 and len(next(f for f in prod["fields"] if f["id"] == k)["options"]) > 1]
    if thin:
        sys.exit(f"golden set does not exercise >=2 options in: {thin}")
    prod["layout_verified"] = True
    prod["doc_status"] = "verified_against_golden"
    (DATA / "products" / f"{a.model}.json").write_text(json.dumps(prod, indent=2))
    print(f"{a.model}: promoted to layout_verified using {len(pns)} golden part numbers")


if __name__ == "__main__":
    main()
