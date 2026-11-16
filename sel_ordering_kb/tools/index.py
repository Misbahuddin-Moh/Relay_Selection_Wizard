#!/usr/bin/env python3
"""Builds data/sel_kb.sqlite (with FTS5) from data/products/*.json + grammar.json.

  python3 tools/index.py                      # build
  python3 tools/index.py search "24 Vdc"      # full-text search across all options
  python3 tools/index.py status               # per-product ingestion status
"""
import json, pathlib, sqlite3, sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
DB = DATA / "sel_kb.sqlite"


def build():
    if DB.exists():
        DB.unlink()
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE products(model TEXT PRIMARY KEY, family TEXT, category TEXT, prefix TEXT, doc_status TEXT,
        layout_verified INTEGER, source_doc TEXT, source_url TEXT, doc_date TEXT, n_fields INTEGER);
    CREATE TABLE fields(model TEXT, ord INTEGER, id TEXT, name TEXT, width INTEGER, confidence TEXT, note TEXT,
        PRIMARY KEY(model,id));
    CREATE TABLE options(model TEXT, field_id TEXT, code TEXT, descr TEXT, extra_cost INTEGER, note TEXT);
    CREATE TABLE constraints(model TEXT, id TEXT, type TEXT, confidence TEXT, note TEXT, body TEXT);
    CREATE TABLE open_questions(model TEXT, q TEXT);
    CREATE TABLE accessories(model TEXT, item TEXT, pn TEXT, note TEXT);
    CREATE VIRTUAL TABLE option_fts USING fts5(model, field_name, code, descr, note);
    CREATE INDEX opt_model ON options(model, field_id);
    """)
    for p in sorted((DATA / "products").glob("*.json")):
        d = json.loads(p.read_text())
        s = d.get("source", {})
        c.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (d["model"], d.get("family"), d.get("category"), d.get("prefix"), d["doc_status"],
                   int(d["layout_verified"]), s.get("doc_id"), s.get("url"), s.get("doc_date"), len(d["fields"])))
        for f in d["fields"]:
            c.execute("INSERT INTO fields VALUES(?,?,?,?,?,?,?)",
                      (d["model"], f["order"], f["id"], f["name"], f["width"], f["confidence"], f.get("note")))
            for o in f["options"]:
                c.execute("INSERT INTO options VALUES(?,?,?,?,?,?)",
                          (d["model"], f["id"], o["code"], o["desc"], int(o["extra_cost"]), o.get("note")))
                c.execute("INSERT INTO option_fts VALUES(?,?,?,?,?)",
                          (d["model"], f["name"], o["code"], o["desc"], o.get("note") or ""))
        for k in d.get("constraints", []):
            c.execute("INSERT INTO constraints VALUES(?,?,?,?,?,?)",
                      (d["model"], k["id"], k["type"], k["confidence"], k["note"], json.dumps(k)))
        for q in d.get("open_questions", []):
            c.execute("INSERT INTO open_questions VALUES(?,?)", (d["model"], q))
        for a in d.get("accessories", []):
            c.execute("INSERT INTO accessories VALUES(?,?,?,?)", (d["model"], a["item"], a.get("pn"), a.get("note")))
    c.commit()
    n = c.execute("select count(*) from options").fetchone()[0]
    print(f"indexed {c.execute('select count(*) from products').fetchone()[0]} products, {n} options -> {DB}")
    c.close()


def search(q):
    c = sqlite3.connect(DB)
    for r in c.execute("SELECT model, field_name, code, descr FROM option_fts WHERE option_fts MATCH ? LIMIT 40", (q,)):
        print(" | ".join(r))


def status():
    c = sqlite3.connect(DB)
    for r in c.execute("SELECT model, doc_status, layout_verified, n_fields, source_doc, doc_date FROM products"):
        print(r)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: build()
    elif a[0] == "search": search(" ".join(a[1:]))
    elif a[0] == "status": status()
