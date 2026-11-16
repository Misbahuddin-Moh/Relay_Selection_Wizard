import json, pathlib, subprocess, sys, tempfile, shutil, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import selpn

PRODUCTS = sorted(p.stem for p in (ROOT / "data/products").glob("*.json"))
FULL = [m for m in PRODUCTS if selpn.load(m)["fields"]]


class Integrity(unittest.TestCase):
    def test_no_duplicate_codes_per_field(self):
        for m in FULL:
            for f in selpn.load(m)["fields"]:
                codes = [o["code"] for o in f["options"]]
                self.assertEqual(len(codes), len(set(codes)), f"{m}.{f['id']} duplicate codes")

    def test_declared_width_matches_codes(self):
        for m in FULL:
            for f in selpn.load(m)["fields"]:
                if f["width"] is None:
                    continue
                for o in f["options"]:
                    if o["code"] == "UNRESOLVED":
                        continue
                    self.assertEqual(len(o["code"]), f["width"], f"{m}.{f['id']} code {o['code']}")

    def test_constraints_reference_real_fields(self):
        for m in FULL:
            p = selpn.load(m); ids = {f["id"] for f in p["fields"]}
            for c in p["constraints"]:
                refs = [c["if"]["field"], c["then"]["field"]] if c["type"] == "requires" else c["fields"]
                for r in refs:
                    self.assertIn(r, ids, f"{m}:{c['id']} -> {r}")

    def test_every_product_has_provenance(self):
        for m in PRODUCTS:
            p = selpn.load(m)
            self.assertTrue(p["source"].get("doc_id"), m)
            self.assertIn("layout_verified", p)

    def test_nothing_is_verified_without_golden(self):
        for m in PRODUCTS:
            if not (ROOT / "data/golden" / f"{m}.txt").exists():
                self.assertFalse(selpn.load(m)["layout_verified"], f"{m} claims verified without golden PNs")


class Engine(unittest.TestCase):
    SEL710 = {"slot_a": "1A", "slot_b": "000", "slot_c": "0X", "slot_d": "0X", "slot_e": "0X", "slot_z": "85", "conformal": "0"}

    def test_roundtrip_self_consistency_only(self):
        r = selpn.assemble("SEL-710", self.SEL710)
        self.assertEqual(r["string"], "07100" "1A" "000" "0X0X0X" "85" "0")
        self.assertEqual(selpn.parse("SEL-710", r["string"]), self.SEL710)

    def test_unverified_layout_is_never_issuable(self):
        for m in FULL:
            p = selpn.load(m)
            sel = {f["id"]: f["options"][0]["code"] for f in p["fields"]}
            self.assertFalse(selpn.assemble(m, sel)["issuable"], m)

    def test_unknown_code_rejected(self):
        bad = dict(self.SEL710, slot_z="99")
        self.assertTrue(any("slot_z" in p for p in selpn.validate("SEL-710", bad)))

    def test_one_per_chassis_rule(self):
        sel = dict(self.SEL710, slot_c="BA", slot_d="BA")
        self.assertTrue(any("710-max-one-3di4do1ao" in p for p in selpn.validate("SEL-710", sel)))

    def test_cross_family_power_supply_codes_differ(self):
        ps451 = {o["code"]: o["desc"] for f in selpn.load("SEL-451-5")["fields"] if f["id"] == "power_supply" for o in f["options"]}
        ps311 = {o["code"]: o["desc"] for f in selpn.load("SEL-311L")["fields"] if f["id"] == "power_supply" for o in f["options"]}
        self.assertNotEqual(ps451["4"], ps311["4"])

    def test_unresolved_width_blocks_string(self):
        sel = {f["id"]: f["options"][0]["code"] for f in selpn.load("SEL-451-5")["fields"]}
        self.assertIsNone(selpn.assemble("SEL-451-5", sel)["string"])
        with self.assertRaises(ValueError):
            selpn.parse("SEL-451-5", "04515" + "X" * 15)


class PromotionGate(unittest.TestCase):
    def test_gate_rejects_garbage_and_accepts_thin_golden_only_when_ok(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "data", tmp / "data"); shutil.copytree(ROOT / "tools", tmp / "tools")
        try:
            (tmp / "data/golden").mkdir()
            (tmp / "data/golden/SEL-710.txt").write_text("07100" "1A" "000" "0X0X0X" "85" "0\nNOTAPN\n")
            r = subprocess.run([sys.executable, str(tmp / "tools/promote.py"), "SEL-710"], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(json.loads((tmp / "data/products/SEL-710.json").read_text())["layout_verified"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
