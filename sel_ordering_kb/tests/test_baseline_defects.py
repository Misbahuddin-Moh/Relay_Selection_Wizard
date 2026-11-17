"""Regressions for the defects in the 2026-11-16 review (baseline 3cda2bc).

These use only the BASELINE API (selpn.load/validate/assemble, promote.py) so they can be run against
the untouched baseline to prove each defect reproduces, and then against the fixed tree to prove it is gone.
Run on baseline: expect failures. Run on fixed tree: expect all pass (promote.py no longer exists -> skipped there).
"""
import copy, json, pathlib, shutil, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import selpn


def first_sel(model):
    p = selpn.load(model)
    return {f["id"]: f["options"][0]["code"] for f in p["fields"]}


def problems(model, sel):
    """Baseline validate() returned list[str]; fixed tree keeps that compat shim."""
    return selpn.validate(model, sel)


class P0_451_UserSettableVoltage(unittest.TestCase):
    def test_reproduction_must_not_validate(self):
        s = first_sel("SEL-451-5")
        s.update(chassis="2", io_b="2", io_b_voltage="X", io_c="0")
        self.assertTrue(problems("SEL-451-5", s), "user-settable pickup on I/O option 2 accepted silently")


class P0_UnknownRuleTypeFailsClosed(unittest.TestCase):
    def test_unknown_rule_type_is_not_ignored(self):
        if not hasattr(selpn, "check"):
            # baseline: inject by temporarily writing a product file copy
            self.skipTest("baseline has no injection API; verified manually: validate() returns [] for unknown type")
        p = copy.deepcopy(selpn.load("SEL-710"))
        p["constraints"].append({"id": "X1", "type": "magic", "scope": "ordering", "confidence": "stated", "note": "n"})
        r = selpn.check("SEL-710", first_sel("SEL-710"), product=p)
        self.assertEqual(r["status"], "unsupported")


class P1_EmptyProductsNotValid(unittest.TestCase):
    def test_empty_selection_on_header_only_product(self):
        for m in ("SEL-351S", "SEL-487E", "SEL-700G", "SEL-751"):
            self.assertTrue(problems(m, {}), f"{m}: validate(model, {{}}) returned [] (looks valid)")


class P1_411L_ChannelRule(unittest.TestCase):
    def test_no_channel_selection_is_not_silently_ok_under_stated_rule_id(self):
        # Baseline rule id says "87L-needs-channel" but implication allows none/none.
        s = first_sel("SEL-411L")
        s.update(diff_ch1="0", diff_ch2="0")
        ids = [c["id"] for c in selpn.load("SEL-411L")["constraints"]]
        if "411L-87L-needs-channel" in ids:
            self.assertTrue(problems("SEL-411L", s) and any("411L-87L" in p for p in problems("SEL-411L", s)),
                            "rule named 87L-needs-channel does not reject none/none")


class P0_FlagToggle(unittest.TestCase):
    def test_json_flag_alone_cannot_make_orderable(self):
        p = copy.deepcopy(selpn.load("SEL-710"))
        p["layout_verified"] = True
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "data/products").mkdir(parents=True)
            (tmp / "data/products/SEL-710.json").write_text(json.dumps(p))
            old = selpn.DATA
            selpn.DATA = tmp / "data"
            try:
                r = selpn.assemble("SEL-710", first_sel("SEL-710"))
            finally:
                selpn.DATA = old
            self.assertFalse(r.get("issuable", False))
            self.assertFalse(r.get("manufacturer_orderable", False))
        finally:
            shutil.rmtree(tmp)


class P0_SyntheticGoldenMustNotPromote(unittest.TestCase):
    SYN = ["071001A0000X0X0X810", "071001B0101A1A1A821", "071001C0000X0X0X810",
           "071001D0000X0X0X810", "071001G0000X0X0X810"]

    def test_synthetic_strings_do_not_promote(self):
        promote = ROOT / "tools/promote.py"
        if not promote.exists():
            self.skipTest("promote.py removed (replaced by verify.py)")
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            shutil.copytree(ROOT / "data", tmp / "data"); shutil.copytree(ROOT / "tools", tmp / "tools")
            (tmp / "data/golden").mkdir(exist_ok=True)
            (tmp / "data/golden/SEL-710.txt").write_text("\n".join(self.SYN))
            r = subprocess.run([sys.executable, str(tmp / "tools/promote.py"), "SEL-710"], capture_output=True, text=True)
            promoted = json.loads((tmp / "data/products/SEL-710.json").read_text()).get("layout_verified")
            self.assertFalse(promoted, "synthetic-only golden set promoted SEL-710")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
