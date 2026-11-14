import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app
from backend.provider_policy import PROVIDER_PATHS


class ProviderSecurityTests(unittest.TestCase):
    def test_paid_routes_deny_before_validation_with_accidental_keys(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key", "OPENAI_API_KEY": "fake-test-key"}), \
             patch("backend.drawing.urlopen", side_effect=AssertionError("Unexpected provider call")), \
             patch("backend.options.urlopen", side_effect=AssertionError("Unexpected provider call")), \
             patch("backend.project_requirements.urlopen", side_effect=AssertionError("Unexpected provider call")), \
             TestClient(app) as client:
            for path in PROVIDER_PATHS:
                for suffix in ("", "/"):
                    with self.subTest(path=path + suffix):
                        response = client.post(path + suffix, content=b"invalid confidential sentinel", follow_redirects=False)
                        self.assertEqual(response.status_code, 403)
                        self.assertNotIn("sentinel", response.text)
            for path in ("/api/drawing/status", "/api/requirements/status"):
                self.assertFalse(client.get(path).json()["configured"])
            self.assertEqual(client.get("/api/health").json()["provider_operations"], "disabled")

    def test_manual_analysis_remains_available(self):
        with TestClient(app) as client:
            study = client.get("/api/study").json()["study"]
            self.assertEqual(client.post("/api/analyze", json=study).status_code, 200)
