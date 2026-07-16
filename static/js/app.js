// Recuperar correo guardado al iniciar la página
document.addEventListener("DOMContentLoaded", () => {
    const savedEmail = localStorage.getItem("veridicheck_email");
    if (savedEmail) {
        document.getElementById("email-input").value = savedEmail;
    }
});

// Mensajes de carga dinámicos para simular escaneo
const loadingSteps = [
    { title: "Iniciando análisis...", desc: "Estableciendo conexión segura con VeridiCheck..." },
    { title: "Evaluando remitente...", desc: "Buscando patrones conocidos de fraude e ingeniería social..." },
    { title: "Analizando enlaces...", desc: "Verificando reputación de dominios y redireccionamientos..." },
    { title: "Procesando heurística...", desc: "Consultando el modelo de lenguaje para el dictamen final..." }
];

// Manejador del Formulario
async function handleFormSubmit(event) {
    event.preventDefault();

    const emailInput = document.getElementById("email-input").value.trim();
    const contentInput = document.getElementById("content-input").value.trim();

    if (!emailInput || !contentInput) return;

    // Guardar correo en LocalStorage
    localStorage.setItem("veridicheck_email", emailInput);

    // Obtener referencias de secciones
    const scannerSection = document.getElementById("scanner-section");
    const loadingSection = document.getElementById("loading-section");
    const resultsSection = document.getElementById("results-section");

    // Transición visual a pantalla de Carga
    scannerSection.classList.add("hidden");
    resultsSection.classList.add("hidden");
    loadingSection.classList.remove("hidden");

    // Iniciar simulación de carga textual progresiva
    let stepIdx = 0;
    const loadingTitle = document.getElementById("loading-title");
    const loadingDesc = document.getElementById("loading-desc");

    const loadingInterval = setInterval(() => {
        if (stepIdx < loadingSteps.length - 1) {
            stepIdx++;
            loadingTitle.textContent = loadingSteps[stepIdx].title;
            loadingDesc.textContent = loadingSteps[stepIdx].desc;
        }
    }, 1200);

    try {
        // Petición al Servidor
        const response = await fetch("/api/verify", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: emailInput,
                query: contentInput
            })
        });

        clearInterval(loadingInterval);

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Error en el servidor");
        }

        const data = await response.json();

        // Renderizar Resultados
        displayResults(data);

    } catch (error) {
        clearInterval(loadingInterval);
        alert(`Ocurrió un error al analizar: ${error.message}`);
        resetScanner();
    }
}

// Renderizar Resultados
function displayResults(data) {
    const loadingSection = document.getElementById("loading-section");
    const resultsSection = document.getElementById("results-section");

    // Limpiar clases de temas anteriores
    resultsSection.classList.remove("safe-theme", "suspicious-theme", "malicious-theme");

    // Definir temas e iconos por estado
    const status = data.status.toLowerCase();
    let themeClass = "safe-theme";
    let badgeText = "Seguro";
    let badgeClass = "badge-safe";

    if (status === "malicioso") {
        themeClass = "malicious-theme";
        badgeText = "Malicioso";
        badgeClass = "badge-malicious";
    } else if (status === "sospechoso") {
        themeClass = "suspicious-theme";
        badgeText = "Sospechoso";
        badgeClass = "badge-suspicious";
    }

    // Aplicar tema de peligro al panel
    resultsSection.classList.add(themeClass);

    // Actualizar Badge de Estado
    const threatBadge = document.getElementById("threat-badge");
    const threatBadgeText = document.getElementById("threat-badge-text");
    threatBadge.className = `badge-status ${badgeClass}`;
    threatBadgeText.textContent = badgeText;

    // Actualizar Medidor de Riesgo
    const scoreVal = data.score;
    document.getElementById("threat-score").textContent = `${scoreVal}%`;
    const scoreBar = document.getElementById("threat-score-bar");
    scoreBar.style.width = "0%"; // Reiniciar para transición
    setTimeout(() => {
        scoreBar.style.width = `${scoreVal}%`;
    }, 100);

    // Actualizar Resumen y Demo Tag
    document.getElementById("result-summary").textContent = data.summary;
    const demoBadge = document.getElementById("demo-badge-container");
    if (data.is_demo) {
        demoBadge.classList.remove("hidden");
    } else {
        demoBadge.classList.add("hidden");
    }

    // Actualizar Lista de Indicadores / Razones
    const reasonsContainer = document.getElementById("result-reasons");
    reasonsContainer.innerHTML = "";
    if (data.reasons && data.reasons.length > 0) {
        data.reasons.forEach(reason => {
            const li = document.createElement("li");
            li.textContent = reason;
            reasonsContainer.appendChild(li);
        });
    } else {
        reasonsContainer.innerHTML = "<li>No se encontraron indicadores sospechosos obvios.</li>";
    }

    // Actualizar Lista de Recomendaciones
    const recommendationsContainer = document.getElementById("result-recommendations");
    recommendationsContainer.innerHTML = "";
    if (data.recommendations && data.recommendations.length > 0) {
        data.recommendations.forEach(rec => {
            const li = document.createElement("li");
            li.textContent = rec;
            recommendationsContainer.appendChild(li);
        });
    } else {
        recommendationsContainer.innerHTML = "<li>Mantente alerta ante cualquier cambio en el remitente.</li>";
    }

    // Configurar alerta de envío por correo
    const emailAlert = document.getElementById("email-status-alert");
    const emailAlertText = document.getElementById("email-status-text");
    emailAlert.className = "email-alert"; // Limpiar clases secundarias

    if (data.email_sent) {
        emailAlert.classList.add("success-alert");
        emailAlertText.textContent = "Enviamos una copia del reporte a tu correo.";
    } else {
        emailAlert.classList.add("info-alert");
        emailAlertText.textContent = data.email_status;
    }

    // Compartir el reporte con cualquier contacto elegido por el usuario.
    const encodedMessage = encodeURIComponent(data.whatsapp_message);
    const waUrl = `https://wa.me/?text=${encodedMessage}`;

    const waBtn = document.getElementById("whatsapp-manual-btn");
    waBtn.href = waUrl;

    // Transición visual para mostrar resultados
    loadingSection.classList.add("hidden");
    resultsSection.classList.remove("hidden");
}

// Reiniciar el Escáner
function resetScanner() {
    document.getElementById("scanner-section").classList.remove("hidden");
    document.getElementById("loading-section").classList.add("hidden");
    document.getElementById("results-section").classList.add("hidden");

    // Limpiar campo de mensaje, pero mantener teléfono
    document.getElementById("content-input").value = "";

    // Restaurar textos de carga iniciales
    document.getElementById("loading-title").textContent = loadingSteps[0].title;
    document.getElementById("loading-desc").textContent = loadingSteps[0].desc;
}
