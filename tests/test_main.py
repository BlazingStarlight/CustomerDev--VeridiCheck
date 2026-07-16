import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import GEMINI_MODEL, app, build_email_html, get_mock_analysis


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_home_is_available(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VeridiCheck", response.text)

    def test_uses_current_stable_gemini_model(self):
        self.assertEqual(GEMINI_MODEL, "gemini-3.5-flash")

    def test_invalid_email_is_rejected(self):
        response = self.client.post(
            "/api/verify",
            json={"email": "correo-invalido", "query": "Mensaje de prueba"},
        )
        self.assertEqual(response.status_code, 422)

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    def test_demo_analysis_returns_structured_result(self):
        response = self.client.post(
            "/api/verify",
            json={
                "email": "usuario@example.com",
                "query": "Urgente: verifica tu cuenta bancaria en este enlace",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "malicioso")
        self.assertTrue(payload["is_demo"])
        self.assertGreaterEqual(payload["score"], 0)
        self.assertLessEqual(payload["score"], 100)

    def test_email_report_escapes_generated_content(self):
        result = get_mock_analysis("Mensaje normal")
        result.summary = "<script>alert('x')</script>"
        report = build_email_html(result)
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;", report)


if __name__ == "__main__":
    unittest.main()
