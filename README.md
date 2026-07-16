# VeridiCheck - Analizador de Mensajes y Enlaces Sospechosos

Este proyecto es una aplicación web interactiva que te permite verificar si un mensaje, correo electrónico o enlace (URL) es legítimo o si tiene intenciones maliciosas (como phishing o estafas). Utiliza la Inteligencia Artificial de Google Gemini para realizar una auditoría de seguridad instantánea y te ofrece los resultados en una interfaz premium y listos para enviar a tu WhatsApp.

---

## Características Principales

- **Análisis Inteligente**: Clasifica la amenaza en una de tres categorías: *Seguro*, *Sospechoso* o *Malicioso*.
- **Métricas de Seguridad**: Te otorga una puntuación de riesgo detallada (0-100%), tipo de amenaza y razones específicas del porqué de su clasificación.
- **Doble Distribución en WhatsApp**:
  - **Automático (API)**: Envío automático a tu teléfono mediante Twilio si configuras tus credenciales en el archivo `.env`.
  - **Manual (Click-to-Chat)**: Genera un botón instantáneo que abre WhatsApp Web o WhatsApp Móvil con el texto del reporte precargado, ideal para compartirlo con amigos, familiares o guardarlo para ti mismo.
- **Diseño Premium**: Interfaz moderna, oscura e inspirada en dashboards de ciberseguridad, utilizando efectos translúcidos (glassmorphism) y animaciones de radar radar.
- **Modo Demo Resiliente**: Si no tienes una clave de API de Gemini a la mano, la aplicación entrará automáticamente en un **modo de simulación interactiva**. Podrás probar el funcionamiento pegando mensajes comunes de estafas bancarias o sorteos falsos.

---

## Requisitos Previos

- Python 3.10 o superior (Verificado con Python 3.14.5).
- Conexión a Internet.
- Una clave de API de Google Gemini (opcional para el modo demo, recomendada para uso real. Consíguela gratis en [Google AI Studio](https://aistudio.google.com/)).

---

## Instalación y Configuración

Sigue estos sencillos pasos en tu terminal (PowerShell en Windows, Bash en Linux/macOS) para poner en marcha el proyecto:

### 1. Clonar o Ubicar la Carpeta
Asegúrate de que estás situado en la carpeta raíz del proyecto (`Proyecto Customer`).

### 2. Crear y Activar un Entorno Virtual
Crea un entorno virtual para aislar las librerías del proyecto:

```bash
# Crear entorno virtual (.venv)
python -m venv .venv

# Activar en Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Activar en Windows (Símbolo del Sistema / CMD)
.venv\Scripts\activate.bat

# Activar en macOS / Linux
source .venv/bin/activate
```

### 3. Instalar Dependencias
Instala los paquetes necesarios utilizando `pip`:

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Copia el archivo de plantilla `.env.example` y renómbralo a `.env`:

```bash
# En Windows (PowerShell)
Copy-Item .env.example .env

# En Linux/macOS o Git Bash
cp .env.example .env
```

Abre el archivo `.env` recién creado en tu editor de código favorito y configura las siguientes claves:

```env
# Introduce tu clave de Gemini obtenida en Google AI Studio
GEMINI_API_KEY=tu_clave_de_gemini_aqui

# (Opcional) Si quieres envío automatizado por WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=tu_twilio_sid
TWILIO_AUTH_TOKEN=tu_twilio_token
TWILIO_SENDER_NUMBER=whatsapp:+14155238886
```
> [!TIP]
> Si deseas usar el envío automático de Twilio en modo de prueba, debes registrar tu número personal en el "Twilio WhatsApp Sandbox" siguiendo las instrucciones de la consola de administración de tu cuenta Twilio (enviar un mensaje de WhatsApp como `join <palabra-clave>` al número remitente).

---

## Cómo Ejecutar la Aplicación

Para iniciar el servidor web de desarrollo de FastAPI, ejecuta el siguiente comando:

```bash
python main.py
```

Verás una salida en consola indicando que el servidor está corriendo. Abre tu navegador web e ingresa a:

👉 **[http://localhost:8000](http://localhost:8000)**

---

## Despliegue en Vercel

El proyecto incluye `app.py`, `.python-version` y `vercel.json`, por lo que Vercel detecta FastAPI automáticamente.

1. Publica el repositorio en GitHub e impórtalo desde el panel de Vercel.
2. En **Settings > Environment Variables**, agrega `GEMINI_API_KEY` y, si usarás envío automático, las tres variables `TWILIO_*` descritas arriba.
3. Despliega sin configurar Build Command ni Output Directory.
4. Verifica `/`, `/docs` y una solicitud real desde la interfaz.

No subas `.env`: está excluido por `.gitignore`. El modo demo es útil para desarrollo, pero no sustituye el análisis real. El veredicto es orientativo; evita presentar el sistema como una garantía absoluta de seguridad.

---

## Casos de Prueba Recomendados para Probar el Escáner

Si ejecutas la aplicación en **Modo Simulación** (sin configurar la API Key de Gemini), puedes pegar los siguientes textos de ejemplo en la interfaz para probar cómo reacciona VeridiCheck:

### Caso 1: Phishing Bancario (Clasificación esperada: *MALICIOSO*)
> "Estimado cliente de BANCO SEGURO, hemos detectado accesos inusuales en su banca móvil. Por seguridad, su tarjeta ha sido bloqueada temporalmente. Ingrese con urgencia a https://banco-seguro-verificar.net/login para restaurar sus credenciales inmediatamente y evitar la cancelación definitiva."

### Caso 2: Estafa de Sorteo / Dinero Gratis (Clasificación esperada: *SOSPECHOSO*)
> "¡FELICIDADES! Tu número de teléfono ha sido seleccionado como el ganador de nuestro gran premio anual de $10,000 USD y un iPhone 15 Pro Max. Reclama tu premio ahora mismo haciendo clic en este enlace acortado: https://bit.ly/sorteo-gratis-hoy. Tienes 24 horas antes de que expire."

### Caso 3: Mensaje Normal / Seguro (Clasificación esperada: *SEGURO*)
> "Hola Juan, recuerda que mañana tenemos la reunión mensual de planificación a las 10:00 AM. Trae los reportes del trimestre por favor. ¡Saludos!"
