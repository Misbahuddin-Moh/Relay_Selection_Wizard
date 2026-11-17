#!/usr/bin/env python3
"""Builds the DERIVED research index data/sel_kb.sqlite (FTS5) from canonical JSON. Never edit the DB.

  python3 tools/index.py                      # rebuild
  python3 tools/index.py search "24 Vdc"
  python3 tools/index.py status               # per-product catalog status (not verification)
  python3 tools/index.py digest               # content digest of all rows (parity check)

Parity: rows_digest(db) is a hash of every table's rows in a deterministic order; tests assert that a fresh build
from JSON equals the checked-in DB. The DB is a convenience for search, not an authority.
"""
import hashlib, json, pathlib, sqlite3, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import selpn

DATA = selpn.DATA
DB = DATA / "sel_kb.sqlite"
TABLES = ["products", "fields", "options", "constraints", "unresolved", "accessories"]
SCHEMA = """
CREATE TABLE products(model_id TEXT PRIMARY KEY, family TEXT, category TEXT, prefix TEXT, doc_status TEXT,
    variant_resolved INTEGER, source_kind TEXT, source_doc TEXT, source_url TEXT, revision TEXT, doc_date TEXT, n_fields INTEGER);
CREATE TABLE fields(model_id TEXT, ord INTEGER, id TEXT, name TEXT, width INTEGER, confidence TEXT, note TEXT, PRIMARY KEY(model_id,id));
CREATE TABLE options(model_id TEXT, field_id TEXT, code TEXT, descr TEXT, extra_cost INTEGER, token_status TEXT, note TEXT);
CREATE TABLE constraints(model_id TEXT, id TEXT, type TEXT, scope TEXT, confidence TEXT, note TEXT, body TEXT);
CREATE TABLE unresolved(model_id TEXT, id TEXT, text TEXT, blocks TEXT);
CREATE TABLE accessories(model_id TEXT, item TEXT, pn TEXT, note TEXT);
CREATE VIRTUAL TABLE option_fts USING fts5(model_id, field_name, code, descr, note);
"""


def build(db_path=DB, data_dir=DATA):
    db_path = pathlib.Path(db_path)
    if db_path.exists():
        db_path.unlink()
    c = sqlite3.connect(db_path)
    c.executescript(SCHEMA)
    for m in selpn.list_models(data_dir):
        d = selpn.load(m, data_dir)
        errs = selpn.validate_catalog(d)
        if errs:
            raise SystemExit(f"refusing to index invalid catalog {m}: {errs[0]}")
        s = d["source"]
        c.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (m, d.get("family"), d.get("category"), d.get("prefix"), d["doc_status"], int(d["identity"]["variant_resolved"]),
                   s["kind"], s["doc_id"], s.get("url"), s.get("revision"), s.get("doc_date"), len(d["fields"])))
        for f in d["fields"]:
            c.execute("INSERT INTO fields VALUES(?,?,?,?,?,?,?)", (m, f["order"], f["id"], f["name"], f["width"], f["confidence"], f.get("note")))
            for o in f["options"]:
                c.execute("INSERT INTO options VALUES(?,?,?,?,?,?,?)",
                          (m, f["id"], o["code"], o["desc"], int(o["extra_cost"]), o["token_status"], o.get("note")))
                c.execute("INSERT INTO option_fts VALUES(?,?,?,?,?)", (m, f["name"], o["code"], o["desc"], o.get("note") or ""))
        for k in d["constraints"]:
            c.execute("INSERT INTO constraints VALUES(?,?,?,?,?,?,?)",
                      (m, k["id"], k["type"], k["scope"], k["confidence"], k["note"], json.dumps(k, sort_keys=True)))
        for u in d["unresolved"]:
            c.execute("INSERT INTO unresolved VALUES(?,?,?,?)", (m, u["id"], u["text"], ",".join(u["blocks"])))
        for a in d["accessories"]:
            c.execute("INSERT INTO accessories VALUES(?,?,?,?)", (m, a["item"], a.get("pn"), a.get("note")))
    c.commit(); c.close()
    return rows_digest(db_path)


def rows_digest(db_path=DB):
    c = sqlite3.connect(db_path)
    h = hashlib.sha256()
    for t in TABLES + ["option_fts"]:
        rows = sorted(map(repr, c.execute(f"SELECT * FROM {t}").fetchall()))
        h.update(t.encode()); h.update("\n".join(rows).encode())
    c.close()
    return h.hexdigest()


def search(q):
    c = sqlite3.connect(DB)
    for r in c.execute("SELECT model_id, field_name, code, descr FROM option_fts WHERE option_fts MATCH ? LIMIT 40", (q,)):
        print(" | ".join(map(str, r)))


def status():
    c = sqlite3.connect(DB)
    for r in c.execute("SELECT model_id, doc_status, variant_resolved, n_fields, source_kind, source_doc FROM products"):
        print(r)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print("rows digest", build())
    elif a[0] == "search": search(" ".join(a[1:]))
    elif a[0] == "status": status()
    elif a[0] == "digest": print(rows_digest())
