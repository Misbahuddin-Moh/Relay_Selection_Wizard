"""Catalog tests (schema v2). Passing tests are NOT manufacturer approval or engineering acceptance."""
import copy, json, math, pathlib, shutil, sqlite3, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import canon, index, manifest, selpn, verify

MODELS = selpn.list_models()
FULL = [m for m in MODELS if selpn.load(m)["fields"]]
SYN_710 = ["071001A0000X0X0X810", "071001B0101A1A1A821", "071001C0000X0X0X810",
           "071001D0000X0X0X810", "071001G0000X0X0X810"]   # from the review: SYNTHETIC negative fixtures


def first(model, **upd):
    s = {f["id"]: f["options"][0]["code"] for f in selpn.load(model)["fields"]}
    s.update(upd)
    return s


def codes(r):
    return {x.get("rule", x["code"]) for x in r["problems"]}


class TmpData(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "data", self.tmp / "data")
        self.d = self.tmp / "data"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_product(self, model, p):
        (self.d / "products" / f"{model}.json").write_text(json.dumps(p))


# ===================================================== integrity of the shipped data
class Integrity(unittest.TestCase):
    def test_every_record_passes_schema_gate(self):
        for m in MODELS:
            self.assertEqual(selpn.validate_catalog(selpn.load(m)), [], m)

    def test_no_verification_asserted_in_data(self):
        for m in MODELS:
            blob = json.dumps(selpn.load(m))
            for k in selpn.FORBIDDEN_KEYS:
                self.assertNotIn(f'"{k}"', blob, f"{m} contains {k}")

    def test_nothing_is_verified_or_reviewed(self):
        for m in MODELS:
            t = verify.track_states(m)
            self.assertEqual(t["code_layout"]["state"], "not_started", m)
            self.assertEqual(t["data_extraction_review"]["state"], "not_started", m)
            self.assertEqual(t["compatibility_rules_review"]["state"], "not_started", m)

    def test_provenance_is_structured_not_free_text(self):
        for m in MODELS:
            p = selpn.load(m)
            self.assertIn(p["source"]["kind"], selpn.SOURCE_KINDS)
            if p["fields"]:
                self.assertNotEqual(p["source"]["kind"], "none", m)
                self.assertEqual(p["source"]["retrieval"], "llm_summary", m)   # honest: not raw-PDF reconstruction
            self.assertIsNone(p["source"]["sha256"], f"{m}: no raw artifact hashed yet")

    def test_exact_variant_matching_only(self):
        for bad in ("SEL-487E-4", "sel-451-5", "SEL-311L-1", "SEL-451", "SEL-751A "):
            with self.assertRaises(KeyError, msg=bad):
                selpn.load(bad)
        self.assertEqual(selpn.load("SEL-311L")["identity"]["variants"], ["SEL-311L-0", "SEL-311L-6"])
        self.assertFalse(selpn.load("SEL-487E")["identity"]["variant_resolved"])

    def test_known_provenance_facts_from_review(self):
        s = selpn.load("SEL-451-5")["source"]
        self.assertEqual((s["revision"], s["doc_date"]), ("WI-8789", "2019-07-11"))
        self.assertIn("reviewer_reported", s["date_basis"])         # not claimed as raw-PDF verified

    def test_author_labels_and_placeholders_never_exportable(self):
        for m in FULL:
            self.assertTrue(all(v == [] for v in selpn.export_tokens(m).values()), m)
        eth = next(f for f in selpn.load("SEL-451-5")["fields"] if f["id"] == "eth_ports")
        self.assertEqual({o["token_status"] for o in eth["options"] if o["code"] != "X"}, {"author_label"})
        sv = next(f for f in selpn.load("SEL-451-5")["fields"] if f["id"] == "sec_voltage")
        self.assertIn("placeholder", {o["token_status"] for o in sv["options"]})

    def test_cross_family_codes_not_shared(self):
        def ps(m): return {o["code"]: o["desc"] for f in selpn.load(m)["fields"] if f["id"] == "power_supply" for o in f["options"]}
        self.assertNotEqual(ps("SEL-451-5")["4"], ps("SEL-311L")["4"])

    def test_unresolved_items_are_structured_and_present(self):
        for m in MODELS:
            self.assertTrue(selpn.load(m)["unresolved"], f"{m} claims nothing unresolved")


# ===================================================== rules: every executable rule has pass AND fail cases
# rule_id: (model, fail_updates, pass_updates, application)
RULE_CASES = {
    "451-eth61850-needs-eth": ("SEL-451-5", dict(eth_protocols="C", eth_ports="X"), dict(eth_protocols="C", eth_ports="A1"), None),
    "451-chassis-io": ("SEL-451-5", dict(chassis="1", io_b="2", io_b_voltage="4"), dict(chassis="1", io_b="0"), None),
    "451-io-c-5u": ("SEL-451-5", dict(io_c="1", chassis="2"), dict(io_c="1", chassis="6"), None),
    "451-ioB-fixed-voltage-boards": ("SEL-451-5", dict(chassis="2", io_b="2", io_b_voltage="X"), dict(chassis="2", io_b="2", io_b_voltage="4"), None),
    "451-ioC-fixed-voltage-boards": ("SEL-451-5", dict(chassis="6", io_c="2", io_c_voltage="X"), dict(chassis="6", io_c="2", io_c_voltage="4"), None),
    "411L-io-c-needs-5u": ("SEL-411L", dict(io_c="2", chassis="4"), dict(io_c="2", chassis="5"), None),
    "411L-io-d-needs-6u": ("SEL-411L", dict(io_d="2", chassis="5"), dict(io_d="2", chassis="6"), None),
    "411L-app-87L-needs-channel": ("SEL-411L", dict(diff_ch1="0", diff_ch2="0"), dict(diff_ch1="0", diff_ch2="A"), {"requires_87l": True}),
    "751A-61850-needs-eth": ("SEL-751A", dict(slot_b_proto="1", slot_b_eth="0"), dict(slot_b_proto="1", slot_b_eth="2"), None),
    "751A-max-one-3di4do1ao": ("SEL-751A", dict(slot_c="BA", slot_d="BA"), dict(slot_c="BA", slot_d="0X"), None),
    "751A-max-one-4ai4ao": ("SEL-751A", dict(slot_c="6X", slot_d="6X"), dict(slot_c="6X", slot_d="0X"), None),
    "710-max-one-3di4do1ao": ("SEL-710", dict(slot_c="BA", slot_d="BA"), dict(slot_c="BA", slot_d="0X"), None),
    "710-max-one-4ai4ao": ("SEL-710", dict(slot_c="6X", slot_d="6X"), dict(slot_c="6X", slot_d="0X"), None),
    "311L-io-needs-4u": ("SEL-311L", dict(io_board="2", mounting="H"), dict(io_board="2", mounting="J"), None),
}


class RuleCoverage(unittest.TestCase):
    def test_every_rule_in_kb_has_cases_and_vice_versa(self):
        ids = {c["id"] for m in FULL for c in selpn.load(m)["constraints"]}
        self.assertEqual(ids, set(RULE_CASES))

    def test_each_rule_fails_and_passes_independently(self):
        for rid, (m, bad, good, app) in RULE_CASES.items():
            self.assertIn(rid, codes(selpn.check(m, first(m, **bad), app)), f"{rid}: violation not detected")
            self.assertNotIn(rid, codes(selpn.check(m, first(m, **good), app)), f"{rid}: false positive")

    def test_voltage_rule_per_board_allowed_and_forbidden(self):
        """Do not infer a universal rule from one board: test every I/O board option at both B and C."""
        user_settable = {"1", "5", "6"}
        for pos, vf, base in (("io_b", "io_b_voltage", dict(chassis="2")), ("io_c", "io_c_voltage", dict(chassis="6"))):
            f = next(x for x in selpn.load("SEL-451-5")["fields"] if x["id"] == pos)
            for code in (o["code"] for o in f["options"] if o["code"] != "0"):
                r = selpn.check("SEL-451-5", first("SEL-451-5", **{**base, pos: code, vf: "X"}))
                rule = "451-ioB-fixed-voltage-boards" if pos == "io_b" else "451-ioC-fixed-voltage-boards"
                if pos == "io_c" and code in {"3A", "3B", "7A", "7B"}:
                    continue
                self.assertEqual(rule in codes(r), code not in user_settable, f"{pos}={code}")

    def test_application_rule_only_when_input_supplied(self):
        s = first("SEL-411L", diff_ch1="0", diff_ch2="0")
        r = selpn.check("SEL-411L", s)
        self.assertNotIn("411L-app-87L-needs-channel", codes(r))
        self.assertIn("411L-app-87L-needs-channel", r["not_evaluated"]["application_rules"])
        self.assertNotIn("invalid", r["status"])    # no-channel relay is orderable as far as ordering rules go

    def test_411L_channel2_only_not_rejected(self):
        r = selpn.check("SEL-411L", first("SEL-411L", diff_ch1="0", diff_ch2="C"), {"requires_87l": True})
        self.assertNotIn("411L-app-87L-needs-channel", codes(r))


# ===================================================== fail-closed schema
class FailClosed(unittest.TestCase):
    def mutate(self, fn, model="SEL-710"):
        p = copy.deepcopy(selpn.load(model)); fn(p)
        return p

    def expect(self, fn, code, model="SEL-710"):
        p = self.mutate(fn, model)
        r = selpn.check(model, first(model), product=p)          # must not raise
        self.assertEqual(r["status"], "unsupported", code)
        self.assertIn(code, {e["code"] for e in r["catalog_errors"]})
        with self.assertRaises(ValueError):
            selpn.parse(model, "07100", product=p)

    def rule(self, **kw):
        base = {"id": "T1", "type": "requires", "scope": "ordering", "confidence": "stated", "note": "n",
                "if": {"field": "slot_z", "in": ["81"]}, "then": {"field": "conformal", "in": ["0"]}}
        base.update(kw); return base

    def test_unknown_rule_type(self):
        self.expect(lambda p: p["constraints"].append(self.rule(type="magic")), "UNSUPPORTED_RULE_TYPE")

    def test_malformed_rules(self):
        self.expect(lambda p: p["constraints"].append({k: v for k, v in self.rule().items() if k != "then"}), "RULE_SHAPE")
        self.expect(lambda p: p["constraints"].append(self.rule(**{"if": {"field": "slot_z", "in": ["81"], "not_in": ["82"]}})), "RULE_SHAPE")
        self.expect(lambda p: p["constraints"].append(self.rule(**{"if": {"field": "slot_z", "in": []}})), "RULE_SHAPE")
        self.expect(lambda p: p["constraints"].append(self.rule(scope="nonsense")), "RULE_SHAPE")
        self.expect(lambda p: p["constraints"].append(self.rule(confidence="sure")), "RULE_SHAPE")
        self.expect(lambda p: p["constraints"].append(self.rule(**{"if": {"field": "slot_z", "in": ["81"]}, "when": {"input": "a", "equals": 1}})), "RULE_SHAPE")

    def test_dangling_references(self):
        self.expect(lambda p: p["constraints"].append(self.rule(**{"if": {"field": "nope", "in": ["81"]}})), "RULE_REF")
        self.expect(lambda p: p["constraints"].append(self.rule(**{"then": {"field": "conformal", "in": ["9"]}})), "RULE_REF")
        self.expect(lambda p: p["constraints"].append({"id": "T2", "type": "max_per_chassis", "scope": "ordering", "confidence": "stated",
                                                       "note": "n", "fields": ["slot_c"], "match_codes": ["ZZ"], "max": 1}), "RULE_REF")

    def test_duplicates(self):
        self.expect(lambda p: p["constraints"].append(copy.deepcopy(p["constraints"][0])), "DUPLICATE_ID")
        self.expect(lambda p: p["fields"][0]["options"].append(copy.deepcopy(p["fields"][0]["options"][0])), "DUPLICATE_ID")
        self.expect(lambda p: p["fields"].append(copy.deepcopy(p["fields"][0])), "DUPLICATE_ID")

    def test_versions_and_shape(self):
        self.expect(lambda p: p.__setitem__("schema_version", 99), "SCHEMA_VERSION")
        self.expect(lambda p: p["fields"][0].__setitem__("width", 0), "FIELD")
        self.expect(lambda p: p["fields"][0]["options"][0].__setitem__("token_status", "verified"), "OPTION")
        self.expect(lambda p: p["fields"][0]["options"][0].__setitem__("code", "ZZZZ"), "OPTION")
        self.expect(lambda p: p["source"].__setitem__("kind", "none"), "PROVENANCE")
        self.expect(lambda p: p["unresolved"].append({"id": "x", "text": "t", "blocks": ["everything"]}), "UNRESOLVED")

    def test_asserted_verification_rejected_everywhere(self):
        for k in sorted(selpn.FORBIDDEN_KEYS):
            self.expect(lambda p: p.__setitem__(k, True), "ASSERTED_VERIFICATION")
            self.expect(lambda p: p["fields"][0].__setitem__(k, True), "ASSERTED_VERIFICATION")
            self.expect(lambda p: p["constraints"][0].__setitem__(k, True), "ASSERTED_VERIFICATION")

    def test_missing_required_key(self):
        self.expect(lambda p: p.pop("unresolved"), "SCHEMA")

    def test_model_id_mismatch(self):
        p = self.mutate(lambda p: p.__setitem__("model_id", "SEL-710-5"))
        self.assertEqual(selpn.check("SEL-710", first("SEL-710"), product=p)["status"], "unsupported")


# ===================================================== incomplete products never look valid
class PartialProducts(unittest.TestCase):
    def test_header_only_products_unsupported_everywhere(self):
        for m in ("SEL-351S", "SEL-487E", "SEL-700G", "SEL-751"):
            for sel in ({}, {"anything": "1"}):
                r = selpn.check(m, sel)
                self.assertEqual(r["status"], "unsupported", m)
                self.assertTrue(r["unsupported"])
                self.assertTrue(selpn.validate(m, sel), f"{m}: compat validate() must not return []")

    def test_487E_generic_record_cannot_be_a_variant(self):
        r = selpn.check("SEL-487E", {})
        self.assertIn("VARIANT_UNRESOLVED", {u["code"] for u in r["unsupported"]})

    def test_current_data_never_validated_within_scope(self):
        for m in FULL:
            self.assertNotEqual(selpn.check(m, first(m))["status"], "validated_within_scope", m)

    def test_medium_confidence_and_inferred_evidence_block(self):
        r = selpn.check("SEL-710", first("SEL-710"))
        got = {u["code"] for u in r["unresolved"]}
        self.assertLessEqual({"EXTRACTION_CONFIDENCE", "CATALOG_UNRESOLVED", "REVIEW_NOT_STARTED"}, got)
        self.assertIn("INFERRED_RULES", {u["code"] for u in selpn.check("SEL-451-5", first("SEL-451-5"))["unresolved"]})

    def test_incomplete_selection_is_unresolved_not_valid(self):
        r = selpn.check("SEL-710", {"slot_a": "1A"})
        self.assertIn(r["status"], ("unresolved",))
        self.assertIn("SELECTION_INCOMPLETE", {u["code"] for u in r["unresolved"]})

    def test_unknown_field_and_code_invalid(self):
        self.assertEqual(selpn.check("SEL-710", dict(first("SEL-710"), slot_z="99"))["status"], "invalid")
        self.assertEqual(selpn.check("SEL-710", dict(first("SEL-710"), bogus="1"))["status"], "invalid")


# ===================================================== assemble / parse / representation
class Assemble(TmpData):
    SEL710 = dict(slot_a="1A", slot_b="000", slot_c="0X", slot_d="0X", slot_e="0X", slot_z="85", conformal="0")

    def test_never_orderable_and_no_order_string(self):
        for m in FULL:
            a = selpn.assemble(m, first(m))
            self.assertFalse(a["manufacturer_orderable"]); self.assertIsNone(a["order_string"])
            self.assertNotIn("issuable", a)

    def test_roundtrip_self_consistency_only(self):
        a = selpn.assemble("SEL-710", self.SEL710)
        self.assertEqual(a["unverified_preview"], "07100" "1A" "000" "0X0X0X" "85" "0")
        self.assertEqual(selpn.parse("SEL-710", a["unverified_preview"]), self.SEL710)
        self.assertIn("NOT a part number", " ".join(a["limitations"]))

    def test_leading_zero_representations_normalise(self):
        full = "07100" "1A" "000" "0X0X0X" "85" "0"
        self.assertEqual(selpn.normalize("SEL-710", full), (full, "mot_full"))
        self.assertEqual(selpn.normalize("SEL-710", full[1:]), (full, "relay_stored_no_leading_zero"))
        self.assertEqual(selpn.parse("SEL-710", full[1:]), self.SEL710)
        with self.assertRaises(ValueError):
            selpn.normalize("SEL-710", "9" + full)

    def test_unresolved_width_blocks_preview_and_parse(self):
        self.assertIsNone(selpn.assemble("SEL-451-5", first("SEL-451-5"))["unverified_preview"])
        with self.assertRaises(ValueError):
            selpn.parse("SEL-451-5", "04515" + "X" * 15)

    def test_json_flag_toggle_cannot_change_anything(self):
        p = copy.deepcopy(selpn.load("SEL-710")); p["layout_verified"] = True
        self.write_product("SEL-710", p)
        r = selpn.check("SEL-710", first("SEL-710"), data_dir=self.d)
        self.assertEqual(r["status"], "unsupported")
        self.assertIn("ASSERTED_VERIFICATION", {e["code"] for e in r["catalog_errors"]})
        self.assertFalse(selpn.assemble("SEL-710", first("SEL-710"), data_dir=self.d)["manufacturer_orderable"])


# ===================================================== evidence-bound verification
def golden_case(case_id, string, expected, origin="manufacturer", **over):
    c = {"case_id": case_id, "origin": origin, "string": string, "expected_selections": expected,
         "source_artifact": {"doc_id": "TEST-MECHANISM-ONLY", "sha256": "a" * 64, "revision": "test", "locator": "n/a"},
         "reviewer": "test-reviewer", "review_date": "2026-11-16"}
    c.update(over); return c


class Verification(TmpData):
    A = dict(slot_a="1A", slot_b="000", slot_c="0X", slot_d="0X", slot_e="0X", slot_z="85", conformal="0")
    B = dict(slot_a="2C", slot_b="010", slot_c="5X", slot_d="9X", slot_e="71", slot_z="81", conformal="1")

    def s(self, d): return "07100" + "".join(d[k] for k in ("slot_a", "slot_b", "slot_c", "slot_d", "slot_e", "slot_z", "conformal"))

    def put_golden(self, cases, model="SEL-710"):
        (self.d / "golden").mkdir(exist_ok=True)
        (self.d / "golden" / f"{model}.json").write_text(json.dumps({"schema_version": 1, "model_id": model, "cases": cases}))

    def test_synthetic_only_never_promotes(self):
        self.put_golden([golden_case(f"s{i}", s, selpn.parse("SEL-710", s, data_dir=self.d), origin="synthetic")
                         for i, s in enumerate(SYN_710)])
        r = verify.verify_layout("SEL-710", self.d)
        self.assertEqual(r["state"], "not_started"); self.assertEqual(r["ignored_synthetic"], 5)
        self.assertEqual(verify.track_states("SEL-710", data_dir=self.d)["code_layout"]["state"], "not_started")

    def test_manufacturer_cases_verify_only_their_scope(self):
        self.put_golden([golden_case("m1", self.s(self.A), self.A)])
        r = verify.verify_layout("SEL-710", self.d)
        self.assertEqual(r["state"], "layout_verified_within_scope")
        self.assertEqual(r["scope"]["fields"]["slot_z"], ["85"])
        self.assertIn("1/", r["scope"]["coverage"]["slot_z"])
        inside = selpn.assemble("SEL-710", self.A, data_dir=self.d)
        self.assertTrue(inside["layout_verification"]["selection_within_scope"])
        outside = selpn.assemble("SEL-710", dict(self.A, slot_z="81"), data_dir=self.d)
        self.assertFalse(outside["layout_verification"]["selection_within_scope"])
        for a in (inside, outside):                       # layout proof never = orderable
            self.assertFalse(a["manufacturer_orderable"]); self.assertIsNone(a["order_string"])

    def test_expected_meaning_must_come_from_source_not_parser(self):
        self.put_golden([golden_case("m1", self.s(self.A), dict(self.A, slot_z="86"))])
        r = verify.verify_layout("SEL-710", self.d)
        self.assertEqual(r["state"], "rejected"); self.assertIn("differ", json.dumps(r["reasons"]))
        self.assertFalse((self.d / "reviews" / "SEL-710.json").exists())

    def test_provenance_is_mandatory(self):
        for key in ("reviewer", "review_date", "case_id"):
            c = golden_case("m1", self.s(self.A), self.A); c[key] = ""
            self.put_golden([c])
            self.assertEqual(verify.verify_layout("SEL-710", self.d)["state"], "rejected", key)
        for bad in ({"doc_id": "x", "sha256": "short", "revision": "r", "locator": "l"},
                    {"doc_id": "x", "sha256": "a" * 64, "revision": "", "locator": "l"}):
            self.put_golden([golden_case("m1", self.s(self.A), self.A, source_artifact=bad)])
            self.assertEqual(verify.verify_layout("SEL-710", self.d)["state"], "rejected")

    def test_source_file_hash_is_checked_when_path_given(self):
        art = self.tmp / "artifact.pdf"; art.write_bytes(b"%PDF fake")
        good = {"doc_id": "x", "sha256": canon.sha256_file(art), "revision": "r", "locator": "p1", "path": str(art)}
        self.put_golden([golden_case("m1", self.s(self.A), self.A, source_artifact=good)])
        self.assertEqual(verify.verify_layout("SEL-710", self.d)["state"], "layout_verified_within_scope")
        art.write_bytes(b"tampered")
        self.assertEqual(verify.verify_layout("SEL-710", self.d)["state"], "rejected")

    def test_unknown_origin_and_undecodable_rejected(self):
        self.put_golden([golden_case("m1", self.s(self.A), self.A, origin="vendor-ish")])
        self.assertEqual(verify.verify_layout("SEL-710", self.d)["state"], "rejected")
        self.put_golden([golden_case("m1", "07100NOPE", self.A)])
        self.assertEqual(verify.verify_layout("SEL-710", self.d)["state"], "rejected")

    def test_stale_when_product_changes(self):
        self.put_golden([golden_case("m1", self.s(self.A), self.A)])
        verify.verify_layout("SEL-710", self.d)
        p = selpn.load("SEL-710", self.d)
        p["fields"][0]["options"][0]["desc"] += " (edited)"          # any content change
        self.write_product("SEL-710", p)
        t = verify.track_states("SEL-710", data_dir=self.d)["code_layout"]
        self.assertEqual(t["state"], "stale"); self.assertIn("product_sha256", t["stale_because"])
        self.assertFalse(selpn.assemble("SEL-710", self.A, data_dir=self.d)["layout_verification"]["selection_within_scope"])

    def test_stale_when_token_changes(self):
        self.put_golden([golden_case("m1", self.s(self.A), self.A)])
        verify.verify_layout("SEL-710", self.d)
        p = selpn.load("SEL-710", self.d)
        z = next(f for f in p["fields"] if f["id"] == "slot_z")
        z["options"][0]["code"] = "91"
        self.write_product("SEL-710", p)
        self.assertEqual(verify.track_states("SEL-710", data_dir=self.d)["code_layout"]["state"], "stale")

    def test_stale_when_golden_or_validator_changes(self):
        self.put_golden([golden_case("m1", self.s(self.A), self.A)])
        verify.verify_layout("SEL-710", self.d)
        self.put_golden([golden_case("m1", self.s(self.A), self.A, reviewer="someone-else")])
        self.assertIn("golden_sha256", verify.track_states("SEL-710", data_dir=self.d)["code_layout"]["stale_because"])
        self.put_golden([golden_case("m1", self.s(self.A), self.A)])
        self.assertEqual(verify.track_states("SEL-710", data_dir=self.d)["code_layout"]["state"], "layout_verified_within_scope")
        old = selpn.VALIDATOR_VERSION
        try:
            selpn.VALIDATOR_VERSION = "9.9.9"
            self.assertEqual(verify.track_states("SEL-710", data_dir=self.d)["code_layout"]["state"], "stale")
        finally:
            selpn.VALIDATOR_VERSION = old

    def test_layout_proof_does_not_imply_other_tracks(self):
        self.put_golden([golden_case("m1", self.s(self.A), self.A)])
        verify.verify_layout("SEL-710", self.d)
        t = verify.track_states("SEL-710", data_dir=self.d)
        self.assertEqual(t["data_extraction_review"]["state"], "not_started")
        self.assertEqual(t["compatibility_rules_review"]["state"], "not_started")
        self.assertEqual(t["configuration_evidence"]["state"], "out_of_catalog_scope")
        self.assertNotEqual(selpn.check("SEL-710", self.A, data_dir=self.d)["status"], "validated_within_scope")

    def test_human_review_validation(self):
        with self.assertRaises(ValueError): verify.record_review("SEL-710", "code_layout", "r", "2026-11-16", ["a" * 64], data_dir=self.d)
        with self.assertRaises(ValueError): verify.record_review("SEL-710", "data_extraction_review", "", "2026-11-16", ["a" * 64], data_dir=self.d)
        with self.assertRaises(ValueError): verify.record_review("SEL-710", "data_extraction_review", "r", "2026-11-16", ["zz"], data_dir=self.d)
        with self.assertRaises(ValueError): verify.record_review("SEL-710", "data_extraction_review", "r", "16/11/2026", ["a" * 64], data_dir=self.d)


def clean_product():
    """Minimal fully-specified product used ONLY to exercise the positive path in tests."""
    return {"schema_version": 2, "model_id": "T-1", "identity": {"manufacturer": "T", "model": "T-1", "variants": ["T-1"], "variant_resolved": True},
            "source": {"kind": "mot_pdf", "doc_id": "TEST", "sha256": None, "retrieval": "raw_pdf"}, "prefix": "T1",
            "fields": [{"id": "a", "name": "A", "width": 1, "confidence": "high", "order": 1, "options": [
                           {"code": "1", "desc": "one", "extra_cost": False, "token_status": "extracted"},
                           {"code": "2", "desc": "two", "extra_cost": False, "token_status": "extracted"}]},
                       {"id": "b", "name": "B", "width": 1, "confidence": "high", "order": 2, "options": [
                           {"code": "X", "desc": "none", "extra_cost": False, "token_status": "extracted"},
                           {"code": "Y", "desc": "yes", "extra_cost": False, "token_status": "extracted"}]}],
            "constraints": [{"id": "r1", "type": "requires", "scope": "ordering", "confidence": "stated", "note": "2 needs Y",
                             "if": {"field": "a", "in": ["2"]}, "then": {"field": "b", "in": ["Y"]}}],
            "unresolved": [{"id": "app", "text": "station-specific", "blocks": ["application"]}], "accessories": []}


class PositivePath(TmpData):
    def setUp(self):
        super().setUp()
        self.p = clean_product()
        (self.d / "products" / "T-1.json").write_text(json.dumps(self.p))

    def attest(self):
        for t in ("data_extraction_review", "compatibility_rules_review"):
            verify.record_review("T-1", t, "rev", "2026-11-16", ["b" * 64], data_dir=self.d)

    def test_validated_only_with_both_reviews_and_stays_scoped(self):
        sel = {"a": "2", "b": "Y"}
        self.assertEqual(selpn.check("T-1", sel, data_dir=self.d)["status"], "unresolved")
        self.attest()
        r = selpn.check("T-1", sel, data_dir=self.d)
        self.assertEqual(r["status"], "validated_within_scope")
        self.assertIn("Not manufacturer-orderable", r["scope_statement"])
        self.assertEqual(selpn.check("T-1", {"a": "2", "b": "X"}, data_dir=self.d)["status"], "invalid")

    def test_application_only_unresolved_does_not_block_catalog_status(self):
        self.attest()
        self.assertEqual(selpn.check("T-1", {"a": "1", "b": "X"}, data_dir=self.d)["status"], "validated_within_scope")

    def test_blocking_unresolved_item_prevents_validation(self):
        self.attest()
        self.p["unresolved"].append({"id": "hw", "text": "board limits unknown", "blocks": ["hardware"]})
        (self.d / "products" / "T-1.json").write_text(json.dumps(self.p))
        r = selpn.check("T-1", {"a": "1", "b": "X"}, data_dir=self.d)
        self.assertEqual(r["status"], "unresolved")          # and the review is now stale too

    def test_review_invalidated_by_any_change(self):
        self.attest()
        self.p["fields"][0]["options"][0]["desc"] = "changed"
        (self.d / "products" / "T-1.json").write_text(json.dumps(self.p))
        r = selpn.check("T-1", {"a": "1", "b": "X"}, data_dir=self.d)
        self.assertEqual(r["status"], "unresolved")
        self.assertIn("REVIEW_STALE", {u["code"] for u in r["unresolved"]})

    def test_even_validated_and_layout_verified_is_not_orderable(self):
        self.attest()
        a = selpn.assemble("T-1", {"a": "1", "b": "X"}, data_dir=self.d)
        self.assertFalse(a["manufacturer_orderable"]); self.assertIsNone(a["order_string"])   # tokens not literal_verified


# ===================================================== hashing, manifest, derived index
class Reproducibility(TmpData):
    def test_canonical_hash_is_repeatable_and_sensitive(self):
        p = selpn.load("SEL-451-5")
        self.assertEqual(canon.sha256_obj(p), canon.sha256_obj(json.loads(json.dumps(p))))
        q = copy.deepcopy(p); q["fields"][1]["options"][0]["code"] = "9"
        self.assertNotEqual(canon.sha256_obj(p), canon.sha256_obj(q))
        self.assertEqual(canon.canonical_json({"b": "é", "a": 1}), '{"a":1,"b":"\\u00e9"}')

    def test_nonfinite_numbers_rejected(self):
        for v in (math.nan, math.inf):
            with self.assertRaises(ValueError): canon.sha256_obj({"x": v})

    def test_manifest_matches_canonical_data(self):
        self.assertEqual(json.loads((ROOT / "data/manifest.json").read_text()), manifest.build())

    def test_manifest_detects_drift(self):
        p = selpn.load("SEL-451-5", self.d); p["fields"][0]["options"][0]["desc"] = "x"
        self.write_product("SEL-451-5", p)
        self.assertNotEqual(manifest.build(self.d)["products"]["SEL-451-5"]["sha256"],
                            json.loads((ROOT / "data/manifest.json").read_text())["products"]["SEL-451-5"]["sha256"])

    def test_sqlite_is_derived_and_in_parity(self):
        before = {p.name: canon.sha256_file(p) for p in (ROOT / "data/products").glob("*.json")}
        digest = index.build(self.tmp / "fresh.sqlite", ROOT / "data")
        after = {p.name: canon.sha256_file(p) for p in (ROOT / "data/products").glob("*.json")}
        self.assertEqual(before, after, "rebuilding the index changed canonical data")
        self.assertEqual(digest, index.rows_digest(ROOT / "data/sel_kb.sqlite"))
        c = sqlite3.connect(self.tmp / "fresh.sqlite")
        self.assertEqual(c.execute("select count(*) from options").fetchone()[0],
                         sum(len(f["options"]) for m in MODELS for f in selpn.load(m)["fields"]))

    def test_generator_does_not_overwrite_canonical_json(self):
        import build_kb
        p = selpn.load("SEL-710", self.d); p["category"] = "HAND EDIT"; self.write_product("SEL-710", p)
        old = build_kb.OUT; build_kb.OUT = self.d
        try: build_kb.main(force=False)
        finally: build_kb.OUT = old
        self.assertEqual(selpn.load("SEL-710", self.d)["category"], "HAND EDIT")


if __name__ == "__main__":
    unittest.main(verbosity=1)
