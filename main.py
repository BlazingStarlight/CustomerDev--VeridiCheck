import os
import logging
import html
import asyncio
from pathlib import Path
from typing import List, Literal
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
logger = logging.getLogger(__name__)

# En Vercel las variables se configuran en el panel; .env se usa solo en local.
load_dotenv(BASE_DIR / ".env")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_TIMEOUT_SECONDS = 25

app = FastAPI(
    title="Analizador LLM de Mensajes Sospechosos",
    description="Backend en FastAPI para verificar mensajes, correos y enlaces mediante Gemini."
)

# Esquema para la solicitud
class VerificationRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    query: str = Field(min_length=3, max_length=12_000)

# Esquema Pydantic para estructurar la respuesta de Gemini
class VerificationResult(BaseModel):
    status: Literal["seguro", "sospechoso", "malicioso"] = Field(description="Safety status of the content.")
    score: int = Field(ge=0, le=100, description="Risk score from 0 (safe) to 100 (malicious).")
    threat_type: str = Field(description="The primary type of threat identified, such as 'Phishing', 'Estafa/Scam', 'Malware', 'Suplantación de identidad', 'Ninguno' (None), or 'Otro' (Other).")
    summary: str = Field(description="A concise summary of the analysis in Spanish (1-2 sentences).")
    reasons: List[str] = Field(description="A bulleted list of 2 to 4 key reasons for this risk classification, explaining indicators like suspicious domains, urgent language, requests for sensitive details, etc. Written in Spanish.")
    recommendations: List[str] = Field(description="A bulleted list of 2 to 3 actionable security recommendations/next steps for the user in Spanish.")
    whatsapp_message: str = Field(description="A beautifully formatted summary of the analysis in Spanish, optimized for reading on WhatsApp. Include bold text (using asterisks *), clear bullet points, relevant emojis, and a professional warning/safe tone.")

def build_email_html(result: "VerificationResult") -> str:
    reasons = "".join(f"<li>{html.escape(item)}</li>" for item in result.reasons)
    recommendations = "".join(
        f"<li>{html.escape(item)}</li>" for item in result.recommendations
    )
    return f"""
    <!doctype html>
    <html lang="es">
      <body style="font-family:Arial,sans-serif;color:#172033;line-height:1.6">
        <h1>Reporte de VeridiCheck</h1>
        <p><strong>Clasificación:</strong> {html.escape(result.status.title())}</p>
        <p><strong>Nivel de riesgo:</strong> {result.score}/100</p>
        <p><strong>Tipo de amenaza:</strong> {html.escape(result.threat_type)}</p>
        <h2>Resumen</h2>
        <p>{html.escape(result.summary)}</p>
        <h2>Indicadores detectados</h2>
        <ul>{reasons}</ul>
        <h2>Recomendaciones</h2>
        <ul>{recommendations}</ul>
        <p style="color:#64748b">Este análisis es orientativo. Ante cualquier duda, verifica mediante canales oficiales.</p>
      </body>
    </html>
    """


async def send_report_email(to_email: str, result: "VerificationResult") -> tuple[bool, str]:
    service_id = os.getenv("EMAILJS_SERVICE_ID", "").strip()
    template_id = os.getenv("EMAILJS_TEMPLATE_ID", "").strip()
    public_key = os.getenv("EMAILJS_PUBLIC_KEY", "").strip()
    private_key = os.getenv("EMAILJS_PRIVATE_KEY", "").strip()
    if not service_id or not template_id or not public_key or not private_key:
        return False, "El envío por correo aún no está configurado."

    try:
        payload = {
            "service_id": service_id,
            "template_id": template_id,
            "user_id": public_key,
            "accessToken": private_key,
            "template_params": {
                "to_email": to_email,
                "subject": f"Reporte VeridiCheck: {result.status.title()} ({result.score}/100)",
                "report_html": build_email_html(result),
            },
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.emailjs.com/api/v1.0/email/send",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "VeridiCheck/1.0",
                },
                json=payload,
            )
            if response.is_error:
                error_message = response.text[:500]
                logger.error(
                    "EmailJS rechazó el envío: status=%s message=%s",
                    response.status_code,
                    error_message,
                )
                if response.status_code in (401, 403):
                    return False, "EmailJS rechazó las credenciales. Revisa las claves pública y privada."
                if response.status_code == 429:
                    return False, "EmailJS alcanzó temporalmente su límite de envíos. Intenta nuevamente en unos segundos."
                return False, "EmailJS rechazó el envío. Revisa el servicio, la plantilla y sus variables."
        return True, "Enviamos una copia del reporte a tu correo."
    except Exception:
        logger.exception("No se pudo enviar el reporte mediante EmailJS")
        return False, "No fue posible enviar la copia por correo."

# Simulación de respuesta de IA cuando no hay API Key de Gemini
def get_mock_analysis(query: str) -> VerificationResult:
    query_lower = query.lower()

    # Simular una detección básica por palabras clave
    if any(word in query_lower for word in ["banco", "bloquead", "banca", "cuenta", "contraseña", "verific", "tarjeta", "urgente", "iniciar sesión"]):
        return VerificationResult(
            status="malicioso",
            score=88,
            threat_type="Phishing / Suplantación",
            summary="[MODO DEMO - Sin API Key de Gemini] Este mensaje parece ser un ataque de Phishing diseñado para robar tus credenciales bancarias o datos personales.",
            reasons=[
                "Solicitud urgente de verificación de datos personales o bancarios.",
                "Uso de lenguaje de presión o miedo ('cuenta bloqueada', 'acción inmediata').",
                "Falta de identificación formal del remitente."
            ],
            recommendations=[
                "No hagas clic en ningún enlace adjunto al mensaje.",
                "No respondas al remitente ni proporciones información confidencial.",
                "Comunícate directamente con tu banco a través de sus canales oficiales oficiales."
            ],
            whatsapp_message=(
                "🚨 *ALERTA DE SEGURIDAD* 🚨\n\n"
                "El mensaje analizado ha sido clasificado como *MALICIOSO*.\n\n"
                "📊 *Detalles del Análisis:*\n"
                "• *Tipo:* Phishing / Suplantación\n"
                "• *Riesgo:* 88/100 (Muy Alto)\n\n"
                "📝 *Resumen:*\n"
                "Detectamos intentos de suplantar una entidad bancaria solicitando verificación de cuenta urgente.\n\n"
                "⚠️ *Recomendaciones:*\n"
                "1. No abras ningún enlace.\n"
                "2. Bloquea al remitente.\n"
                "3. Contacta a los canales oficiales.\n\n"
                "_Analizado con VeridiCheck_"
            )
        )
    elif any(word in query_lower for word in ["ganaste", "premio", "felicidades", "dinero", "regalo", "sorteo", "gratis"]):
        return VerificationResult(
            status="sospechoso",
            score=65,
            threat_type="Estafa / Scam",
            summary="[MODO DEMO - Sin API Key de Gemini] Este mensaje tiene indicios de ser una estafa o sorteo falso diseñado para obtener tu información.",
            reasons=[
                "Promesas de premios de sorteos en los que probablemente no has participado.",
                "Fomento de la codicia o urgencia por reclamar un premio.",
                "Uso de enlaces acortados o dominios no reconocidos."
            ],
            recommendations=[
                "No accedas a enlaces para reclamar premios sospechosos.",
                "Evita compartir este mensaje con tus contactos, ya que suele ser viral.",
                "Verifica la autenticidad de la promoción en las redes sociales verificadas de la marca."
            ],
            whatsapp_message=(
                "⚠️ *ADVERTENCIA DE SEGURIDAD* ⚠️\n\n"
                "El mensaje analizado ha sido clasificado como *SOSPECHOSO*.\n\n"
                "📊 *Detalles del Análisis:*\n"
                "• *Tipo:* Estafa / Sorteo Falso\n"
                "• *Riesgo:* 65/100 (Medio)\n\n"
                "📝 *Resumen:*\n"
                "El contenido promete premios o dinero gratis, técnica común para recopilar datos (scam).\n\n"
                "⚠️ *Recomendaciones:*\n"
                "1. No compartas información personal ni financiera.\n"
                "2. Desconfía de sorteos aleatorios.\n\n"
                "_Analizado con VeridiCheck_"
            )
        )
    else:
        return VerificationResult(
            status="seguro",
            score=12,
            threat_type="Ninguno",
            summary="[MODO DEMO - Sin API Key de Gemini] El contenido analizado parece no contener amenazas evidentes ni patrones de comportamiento malicioso.",
            reasons=[
                "No solicita información confidencial bajo presión.",
                "El lenguaje es normal y no intenta manipular al usuario.",
                "No contiene palabras clave típicas de estafas conocidas."
            ],
            recommendations=[
                "Aunque parece seguro, mantén siempre la precaución al abrir enlaces de desconocidos.",
                "No introduzcas contraseñas en páginas web que no conozcas."
            ],
            whatsapp_message=(
                "✅ *REPORTE DE SEGURIDAD* ✅\n\n"
                "El mensaje analizado ha sido clasificado como *SEGURO*.\n\n"
                "📊 *Detalles del Análisis:*\n"
                "• *Tipo:* Ninguno\n"
                "• *Riesgo:* 12/100 (Bajo)\n\n"
                "📝 *Resumen:*\n"
                "No se encontraron indicadores obvios de fraude, spam o malware.\n\n"
                "🛡️ *Consejo:* Mantén siempre la prudencia digital activa.\n\n"
                "_Analizado con VeridiCheck_"
            )
        )

# Endpoint principal para verificar el contenido
@app.post("/api/verify")
async def verify_content(request: VerificationRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="El contenido a analizar no puede estar vacío.")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # Verificar si la clave API está configurada o si es la por defecto
    if not gemini_key or gemini_key.strip() == "" or "tu_gemini_api_key_aqui" in gemini_key:
        print("GEMINI_API_KEY no configurada. Utilizando modo simulación...")
        result = get_mock_analysis(request.query)
        is_demo = True
    else:
        is_demo = False
        try:
            # Inicializar cliente de Gemini con la API key
            client = genai.Client(api_key=gemini_key)

            prompt = f"""
            Analiza el siguiente contenido sospechoso proporcionado por un usuario (puede ser un mensaje de texto, correo electrónico o enlace/URL) y determina si es malicioso, sospechoso o seguro.

            Contenido a analizar:
            ---
            {request.query}
            ---

            Realiza una evaluación experta de seguridad informática/ciberseguridad. Analiza si tiene patrones de phishing, ingeniería social, suplantación de identidad (spoofing), malware, enlaces engañosos, urgencia artificial, o si por el contrario parece legítimo y seguro.
            """

            # Generar contenido estructurado
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=VerificationResult,
                            system_instruction="Eres un analista experto en ciberseguridad. Tu objetivo es clasificar contenido sospechoso y dar recomendaciones claras y concisas al usuario en español."
                        ),
                    ),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
            finally:
                await client.aio.aclose()

            # El SDK analiza el JSON directamente y lo carga en el objeto Pydantic
            result = response.parsed

        except TimeoutError:
            logger.warning(
                "Gemini no respondió en %s segundos; se utilizará el análisis de respaldo",
                GEMINI_TIMEOUT_SECONDS,
            )
            result = get_mock_analysis(request.query)
            result.summary = "[MODO DEMO - Gemini excedió el tiempo de respuesta] " + result.summary
            is_demo = True
        except Exception:
            logger.exception("Error al solicitar el análisis a Gemini")
            # Fallback a simulación si la API falla por saldo, red, etc.
            result = get_mock_analysis(request.query)
            result.summary = "[MODO DEMO - El servicio de IA no está disponible] " + result.summary
            is_demo = True

    email_sent, email_status = await send_report_email(request.email, result)

    return {
        "status": result.status, # seguro, sospechoso, malicioso
        "score": result.score,
        "threat_type": result.threat_type,
        "summary": result.summary,
        "reasons": result.reasons,
        "recommendations": result.recommendations,
        "whatsapp_message": result.whatsapp_message,
        "email_sent": email_sent,
        "email_status": email_status,
        "is_demo": is_demo
    }

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Ruta para la página principal
@app.get("/")
async def read_root():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    # Lanzar el servidor localmente en el puerto 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
