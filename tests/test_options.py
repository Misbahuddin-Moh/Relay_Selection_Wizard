import io
import json
from unittest import TestCase
from unittest.mock import patch

from backend.main import reference_study
from backend.options import generate_options, request_options


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
            dict(scheme="combined", hv_boundary=boundary, rationale="Compare the station span.",
                 redundancy="Verify independent CT and trip circuits.", backup="Review graded overcurrent.",
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
        self.assertEqual(json.loads(sent)["max_tokens"], 1400)
        first, second, third = result["options"]
        self.assertEqual(first["check"]["status"], "Missing measurement")
        self.assertEqual(second["boundary"]["state"], "present")
        self.assertIn("coverage gap", third["poi_line"]["coverage"])
