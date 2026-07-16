import asyncio
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

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
        self.assertEqual(GEMINI_MODEL, "gemini-3.1-flash-lite")

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

    @patch("main.send_report_email", new_callable=AsyncMock)
    @patch("main.genai.Client")
    def test_gemini_timeout_uses_fallback_and_still_sends_email(self, client_class, send_email):
        gemini_client = Mock()
        gemini_client.aio.models.generate_content = AsyncMock(side_effect=asyncio.TimeoutError)
        gemini_client.aio.aclose = AsyncMock()
        client_class.return_value = gemini_client
        send_email.return_value = (True, "Enviamos una copia del reporte a tu correo.")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=False):
            response = self.client.post(
                "/api/verify",
                json={
                    "email": "usuario@example.com",
                    "query": "Urgente: confirma tu contraseña bancaria",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_demo"])
        self.assertTrue(payload["email_sent"])
        self.assertNotIn("MODO DEMO", payload["summary"])
        send_email.assert_awaited_once()
        gemini_client.aio.aclose.assert_awaited_once()

    @patch("main.httpx.AsyncClient")
    def test_emailjs_invalid_key_returns_actionable_status(self, client_class):
        response = Mock()
        response.is_error = True
        response.status_code = 403
        response.text = "Invalid public key"
        client = AsyncMock()
        client.post.return_value = response
        client_class.return_value.__aenter__.return_value = client

        with patch.dict(
            os.environ,
            {
                "EMAILJS_SERVICE_ID": "service_test",
                "EMAILJS_TEMPLATE_ID": "template_test",
                "EMAILJS_PUBLIC_KEY": "public_test",
                "EMAILJS_PRIVATE_KEY": "private_test",
            },
            clear=False,
        ):
            from main import send_report_email
            import asyncio

            sent, status = asyncio.run(
                send_report_email("usuario@example.com", get_mock_analysis("Mensaje normal"))
            )

        self.assertFalse(sent)
        self.assertIn("credenciales", status.lower())

        request = client.post.call_args
        self.assertEqual(request.args[0], "https://api.emailjs.com/api/v1.0/email/send")
        payload = request.kwargs["json"]
        self.assertEqual(payload["template_params"]["to_email"], "usuario@example.com")
        self.assertIn("Reporte de VeridiCheck", payload["template_params"]["report_html"])
        self.assertEqual(payload["accessToken"], "private_test")


if __name__ == "__main__":
    unittest.main()
