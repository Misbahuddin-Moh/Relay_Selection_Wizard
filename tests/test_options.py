import io
import json
from unittest import TestCase
from unittest.mock import patch

from backend.main import reference_study
from backend.options import OptionsError, generate_options, request_options


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

        study["ct_inventory"]["transformer_lv_phase"] = 0
        options[2]["transformer_main_b_hv"] = "unresolved"
        reply["content"][0]["text"] = json.dumps({"options": options})
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), patch(
            "backend.options.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())
        ):
            changed, unresolved = generate_options(study)["options"][1:]
        self.assertEqual(unresolved["main_coverage"]["transformer_b"]["status"], "Missing measurement")
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
