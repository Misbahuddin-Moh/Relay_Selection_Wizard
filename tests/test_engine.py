import copy
import json
from pathlib import Path
import unittest

from backend.engine import analyze


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "backend" / "fixture.json"


class StudyBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.study = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_breaker_bays_and_outgoing_branches_are_counted_separately(self):
        result = analyze(self.study)
        counts = result["counts"]
        self.assertEqual(counts["breakers"], 3)
        self.assertEqual(counts["branches"], 5)
        self.assertEqual(counts["modeled_bay_cts"], 0)
        self.assertEqual(counts["combined_required_banks"], 4)
        self.assertEqual(counts["combined_phase_channels"], 12)
        combined = self._candidate(result, "combined")
        self.assertEqual(set(combined["trip_targets"]), {"HV breaker", "CB-01", "CB-02", "CB-03"})

    def test_separate_zones_distinguish_unknown_missing_and_present_lv_measurement(self):
        self.study["auxiliary"] = "excluded"
        for bay in self.study["bays"]:
            bay["ct"] = "present"

        expected = {
            "unknown": "Conditional",
            "absent": "Missing measurement",
            "present": "Baseline candidate",
        }
        for ct_state, expected_status in expected.items():
            with self.subTest(ct_state=ct_state):
                self.study["lv_ct"] = ct_state
                result = analyze(self.study)
                self.assertEqual(self._candidate(result, "dedicated")["status"], expected_status)
                if ct_state != "present":
                    self.assertEqual(self._candidate(result, "shared")["status"], expected_status)
                self.assertEqual(self._candidate(result, "combined")["status"], "Further study")

    def test_added_independent_bays_change_the_boundary_budget_and_preserve_baseline(self):
        baseline = copy.deepcopy(self.study)
        original_result = analyze(self.study)
        alternative = copy.deepcopy(self.study)
        alternative["lv_ct"] = "absent"
        alternative["bays"].extend(
            {"id": f"CB-{index:02}", "branches": [f"F-{index:02}A"], "ct": "present"}
            for index in range(4, 8)
        )

        alternative_counts = analyze(alternative)["counts"]
        self.assertEqual(alternative_counts["breakers"], 7)
        self.assertEqual(alternative_counts["branches"], 9)
        self.assertEqual(alternative_counts["modeled_bay_cts"], 4)
        self.assertEqual(alternative_counts["combined_required_banks"], 8)
        self.assertEqual(alternative_counts["combined_phase_channels"], 24)
        self.assertEqual(self.study, baseline)
        self.assertEqual(analyze(self.study), original_result)

    def test_auxiliary_boundary_adds_one_three_phase_bank(self):
        self.study["auxiliary"] = "excluded"
        excluded = analyze(self.study)["counts"]
        self.study["auxiliary"] = "included"
        included = analyze(self.study)["counts"]
        self.assertEqual(included["combined_required_banks"], excluded["combined_required_banks"] + 1)
        self.assertEqual(included["combined_phase_channels"], excluded["combined_phase_channels"] + 3)
        self.assertEqual(included["breakers"], excluded["breakers"])
        self.assertEqual(included["branches"], excluded["branches"])

    def test_boundary_status_uses_only_the_modeled_side_counts(self):
        self.study["auxiliary"] = "excluded"
        self.study["ct_inventory"] = {
            "lv_breaker_135": 2,
            "lv_breaker_246": 0,
            "hv_breaker_135": 0,
            "hv_breaker_246": 2,
            "transformer_hv_phase": 3,
            "transformer_lv_phase": 3,
            "transformer_hv_neutral": 2,
            "transformer_lv_neutral": 0,
        }
        inventory = self.study["ct_inventory"]
        result = analyze(self.study)
        self.assertEqual(result["counts"]["modeled_bay_cts"], 0)
        combined = self._candidate(result, "combined")
        self.assertEqual(combined["status"], "Missing measurement")
        self.assertIn("HV breaker POI-side", combined["reason"])
        self.assertIn("CB-01", combined["reason"])

        inventory["hv_breaker_135"] = 1
        inventory["lv_breaker_246"] = 1
        inventory["lv_breaker_135"] = 0
        result = analyze(self.study)
        self.assertEqual(result["counts"]["modeled_bay_cts"], 3)
        self.assertEqual(self._candidate(result, "dedicated")["status"], "Baseline candidate")

        inventory["lv_breaker_246"] = None
        result = analyze(self.study)
        self.assertEqual(self._candidate(result, "dedicated")["status"], "Conditional")
        self.assertEqual(result["counts"]["combined_phase_channels"], 12)
        self.assertIn("ct_inventory.neutral", {question["field"] for question in result["questions"]})

    def test_zone_review_identifies_missing_boundaries_and_auxiliary_scope(self):
        self.study["auxiliary"] = "included"
        for bay in self.study["bays"]:
            bay["ct"] = "present"
        self.study["lv_ct"] = "absent"

        result = analyze(self.study)
        zones = {zone["id"]: zone for zone in result["zones"]}
        self.assertEqual(zones["transformer"]["status"], "Missing measurement")
        self.assertEqual(zones["bus"]["status"], "Missing measurement")
        self.assertEqual(zones["combined"]["status"], "Boundaries present")
        auxiliary = {"label": "Auxiliary tap phase CT bank", "state": "present"}
        self.assertNotIn(auxiliary, zones["transformer"]["boundaries"])
        self.assertIn(auxiliary, zones["bus"]["boundaries"])
        self.assertIn(auxiliary, zones["combined"]["boundaries"])
        self.assertEqual(zones["combined"]["trip_targets"], ["HV breaker", "CB-01", "CB-02", "CB-03"])

        self.study["hv_ct"] = "absent"
        combined = next(zone for zone in analyze(self.study)["zones"] if zone["id"] == "combined")
        self.assertEqual(combined["status"], "Missing measurement")
        self.assertIn({"label": "HV breaker POI-side phase CT bank", "state": "absent"}, combined["boundaries"])

    def test_selecting_alternate_hv_ct_preserves_location_specific_coverage(self):
        self.study["ct_inventory"] = {
            "hv_breaker_135": 0,
            "hv_breaker_246": 2,
            "transformer_hv_phase": 3,
            "transformer_lv_phase": 3,
            "lv_breaker_135": 2,
            "lv_breaker_246": 2,
        }
        self.study["include_poi_line"] = True
        self.study["auxiliary"] = "excluded"
        original = analyze(self.study)
        self.assertEqual(self._candidate(original, "combined")["status"], "Missing measurement")
        self.assertEqual([option["state"] for option in original["hv_boundaries"]], ["absent", "present", "present"])
        self.assertEqual(len(original["feeder_areas"]), 3)
        self.assertEqual(sum(len(area["circuits"]) for area in original["feeder_areas"]), 5)

        self.study["hv_boundary"] = "breaker_transformer"
        alternate = analyze(self.study)
        self.assertEqual(self._candidate(alternate, "combined")["status"], "Further study")
        self.assertEqual(alternate["zones"][0]["boundaries"][0]["state"], "present")
        self.assertIn("meet", alternate["poi_line"]["coverage"])

        self.study["hv_boundary"] = "bushing"
        self.assertIn("coverage gap", analyze(self.study)["poi_line"]["coverage"])

    @staticmethod
    def _candidate(result, candidate_id):
        return next(candidate for candidate in result["candidates"] if candidate["id"] == candidate_id)


if __name__ == "__main__":
    unittest.main()
