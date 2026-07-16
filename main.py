import os
import re
import logging
from pathlib import Path
from typing import List, Literal
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
logger = logging.getLogger(__name__)

# En Vercel las variables se configuran en el panel; .env se usa solo en local.
load_dotenv(BASE_DIR / ".env")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

app = FastAPI(
    title="Analizador LLM de Mensajes Sospechosos",
    description="Backend en FastAPI para verificar mensajes, correos y enlaces mediante Gemini."
)

# Esquema para la solicitud
class VerificationRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=24)
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

# Limpiar número de teléfono para WhatsApp
def clean_phone_number(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if not 8 <= len(digits) <= 15:
        raise ValueError("El número debe incluir código de país y tener entre 8 y 15 dígitos.")
    return f"+{digits}"

# Función para enviar WhatsApp con Twilio
def send_whatsapp(to_phone: str, message_body: str) -> tuple[bool, str]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    sender_number = os.getenv("TWILIO_SENDER_NUMBER", "whatsapp:+14155238886")

    if not account_sid or not auth_token or account_sid.strip() == "" or auth_token.strip() == "":
        return False, "Twilio no configurado. Utiliza el enlace manual."

    try:
        clean_to = clean_phone_number(to_phone)
        client = TwilioClient(account_sid, auth_token)
        message = client.messages.create(
            from_=sender_number,
            body=message_body,
            to=f"whatsapp:{clean_to}"
        )
        return True, "Mensaje enviado automáticamente a WhatsApp."
    except Exception:
        logger.exception("No se pudo enviar el reporte mediante Twilio")
        return False, "No fue posible completar el envío automático."

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
    try:
        clean_phone_number(request.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VerificationResult,
                    system_instruction="Eres un analista experto en ciberseguridad. Tu objetivo es clasificar contenido sospechoso y dar recomendaciones claras y concisas al usuario en español."
                ),
            )

            # El SDK analiza el JSON directamente y lo carga en el objeto Pydantic
            result = response.parsed

        except Exception as e:
            logger.exception("Error al solicitar el análisis a Gemini")
            # Fallback a simulación si la API falla por saldo, red, etc.
            result = get_mock_analysis(request.query)
            result.summary = "[MODO DEMO - El servicio de IA no está disponible] " + result.summary
            is_demo = True

    # Intentar enviar mensaje a WhatsApp automáticamente si Twilio está configurado
    whatsapp_sent = False
    whatsapp_status = "No configurado (uso de enlace manual)"

    if request.phone_number.strip():
        success, status_msg = send_whatsapp(request.phone_number, result.whatsapp_message)
        whatsapp_sent = success
        whatsapp_status = status_msg

    return {
        "status": result.status, # seguro, sospechoso, malicioso
        "score": result.score,
        "threat_type": result.threat_type,
        "summary": result.summary,
        "reasons": result.reasons,
        "recommendations": result.recommendations,
        "whatsapp_message": result.whatsapp_message,
        "whatsapp_sent": whatsapp_sent,
        "whatsapp_status": whatsapp_status,
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
