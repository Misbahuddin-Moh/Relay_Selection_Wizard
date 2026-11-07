import io
import json
from unittest import TestCase
from unittest.mock import patch

from backend.main import reference_study
from backend.engine import analyze
from backend.options import OptionsError, device_requirements, generate_options, request_options


class OptionsTests(TestCase):
    def test_compact_cached_request_and_local_boundary_checks(self):
        self.addCleanup(request_options.cache_clear)
        study = reference_study()["study"]
        study.update(title="private drawing title", include_poi_line=True, ct_inventory={
            "hv_breaker_135": 0, "hv_breaker_246": 2,
            "transformer_hv_phase": 3, "transformer_lv_phase": 3,
            "transformer_hv_neutral": 2, "transformer_lv_neutral": 2,
            "lv_breaker_135": 2, "lv_breaker_246": 2,
        })
        options = [
            dict(scheme="combined", hv_boundary=boundary, rationale="Compare the station span. " * 12,
                 transformer_main_b_hv="bushing", backup="Review graded overcurrent.",
                 open_item="Confirm remote clearing.", evidence=["TB_COMBINED", "L_87L"])
            for boundary in ("poi", "breaker_transformer", "bushing")
        ]
        options[2]["transformer_main_b_hv"] = "unresolved"
        reply = dict(stop_reason="end_turn", content=[{"type": "text", "text": json.dumps({"options": options})}],
                     usage={"input_tokens": 600, "output_tokens": 300})
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), patch(
            "backend.options.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())
        ) as call:
            result = generate_options(study)
            again = generate_options({**study, "title": "Renamed study"})
        self.assertEqual(result, again)
        self.assertEqual(call.call_count, 1)
        sent = call.call_args.args[0].data.decode()
        self.assertNotIn(study["title"], sent)
        self.assertNotIn(study["bays"][0]["id"], sent)
        self.assertEqual(json.loads(sent)["max_tokens"], 4096)
        self.assertIn("300–600 output tokens", json.loads(sent)["system"])
        first, second, third = result["options"]
        self.assertEqual(first["check"]["status"], "Missing measurement")
        self.assertEqual(second["boundary"]["state"], "present")
        self.assertIn("coverage gap", third["poi_line"]["coverage"])
        self.assertEqual(second["main_coverage"]["transformer_a"]["function"], "87TB")
        self.assertEqual(second["main_coverage"]["bus"]["function"], "87TB (shared with transformer Main A)")
        self.assertEqual(second["main_coverage"]["transformer_b"]["status"], "Boundaries present")
        self.assertIn("excludes the HV breaker", second["main_coverage"]["transformer_b"]["coverage"])
        self.assertEqual(third["main_coverage"]["transformer_b"]["alternatives"], ["breaker_transformer", "bushing"])

        study["ct_inventory"]["transformer_lv_phase"] = 0
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), patch(
            "backend.options.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())
        ):
            changed, unresolved = generate_options(study)["options"][1:]
        self.assertEqual(unresolved["main_coverage"]["transformer_b"]["status"], "Missing measurement")
        self.assertEqual(unresolved["main_coverage"]["transformer_b"]["alternatives"], [])
        self.assertEqual(unresolved["main_coverage"]["transformer_b"]["boundaries"][0]["state"], "absent")
        self.assertEqual(changed["main_coverage"]["transformer_b"]["status"], "Missing measurement")
        self.assertNotEqual(changed["main_coverage"]["bus"]["status"], "Missing measurement")


    def test_truncation_is_reported_before_parsing_partial_json(self):
        self.addCleanup(request_options.cache_clear)
        response = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": '{"options": ['}]}
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), patch(
            "backend.options.urlopen", return_value=io.BytesIO(json.dumps(response).encode())
        ) as call:
            with self.assertRaisesRegex(OptionsError, "ran out of response space"):
                generate_options(reference_study()["study"])
        self.assertEqual(call.call_count, 1)


    def test_shared_ied_budget_and_independent_feeder_paths(self):
        study = reference_study()["study"]
        study.update(auxiliary="included", include_poi_line=True)
        analysis = analyze(study)
        shared = device_requirements(study, "shared", analysis)
        combined = device_requirements(study, "combined", analysis)
        self.assertEqual((shared[0]["phase_banks"], shared[0]["alternate_phase_banks"]), (6, 7))
        self.assertEqual(shared[0]["functions"], "87T + 87B simultaneously")
        self.assertEqual(combined[0]["phase_banks"], 5)
        self.assertEqual(combined[1]["phase_banks"], 2)
        self.assertEqual(sum(row["functions"].startswith("51P") for row in shared), 3)
        self.assertTrue(any(row["role"].startswith("Revenue") for row in shared))


    def test_catalog_separates_function_evidence_from_input_capacity(self):
        study = reference_study()["study"]
        study["auxiliary"] = "included"
        shared = device_requirements(study, "shared", analyze(study))
        ge, sel = shared[0]["candidates"]
        self.assertEqual(ge["status"], "Unverified application")
        self.assertEqual(sel["status"], "Conditional configuration")
        self.assertEqual(sel["capacity"], "See dual-card terminal allocation")
        self.assertEqual(
            [(row["phase_banks"], row["neutral_inputs"], row["vt_banks"]) for row in sel["allocations"]],
            [(5, 3, 2), (6, 3, 1), (6, 0, 2), (7, 0, 1)],
        )
        self.assertEqual(sel["allocations"][0]["fit"], "Insufficient phase banks")
        self.assertEqual(sel["allocations"][1]["fit"], "Lower phase demand only")
        self.assertEqual(sel["allocations"][3]["fit"], "All listed phase cases")

        study["bays"].append({**study["bays"][0], "id": "CB-04"})
        sel = device_requirements(study, "shared", analyze(study))[0]["candidates"][1]
        self.assertEqual(
            [row["fit"] for row in sel["allocations"]],
            ["Insufficient phase banks"] * 3 + ["Lower phase demand only"],
        )
