import json
import os
from urllib.request import Request, urlopen

from . import analytics, insights

SYSTEM_PROMPT = (
    "Eres un analista de reputación para negocios locales en Google Maps. "
    "Responde en español, con tono profesional y directo. Usa solo los datos del contexto. "
    "Da una lectura breve, evidencia numérica y recomendaciones concretas con responsable, plazo y KPI. "
    "No inventes datos. Si falta información, dilo y propón cómo obtenerla."
)


def _plain(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def client_context(client):
    frame = analytics.report_frame(client.reviews.all())
    kpis = analytics.reputation_kpis(frame)
    diagnosis = insights.client_diagnosis(frame, client)
    themes = analytics.themes(frame)
    return _plain({
        "negocio": client.name,
        "categoria": client.category,
        "pais": client.country or "Sin país",
        "zona": client.zone or "Sin zona",
        "kpis": kpis,
        "temas_positivos": themes["good"],
        "temas_criticos": themes["bad"],
        "diagnostico": diagnosis,
    })


def _local_answer(question, context):
    query = question.lower()
    kpis = context["kpis"]
    diagnosis = context["diagnostico"]
    growth = diagnosis.get("growth", [])
    strategies = diagnosis.get("strategies", [])
    strengths = context["temas_positivos"]
    risks = context["temas_criticos"]

    if any(word in query for word in ("captar", "cliente nuevo", "adquisicion", "adquisición", "venta")):
        play = growth[1] if len(growth) > 1 else {}
        tactics = "; ".join(play.get("tactics", [])[:3])
        return (
            f"Para captar clientes en {context['zona']}, convierte la ficha en un embudo medible. "
            f"Objetivo: {play.get('objective', 'acercar la ficha a nuevas consultas')}. "
            f"Acciones: {tactics or 'completar ficha, publicar fotos y abrir WhatsApp'}. "
            f"KPI: {play.get('kpi', '+20% de visitas y +15 consultas en 30 días')}."
        )

    if any(word in query for word in ("valoracion", "valoración", "reseña", "review", "positiv")):
        play = growth[0] if growth else {}
        tactics = "; ".join(play.get("tactics", [])[:3])
        return (
            f"Con {kpis['total']} opiniones y {kpis['five_rate']:.1f}% de 5★, la base existe. "
            f"Para subir valoraciones positivas: {tactics or 'pedir la reseña al entregar el servicio, QR en mesa y guion breve'}. "
            f"KPI: {play.get('kpi', '2-3 reseñas/día con al menos 80% de 5★')}."
        )

    if any(word in query for word in ("critic", "negativ", "queja", "problema", "riesgo", "1 estrella", "2 estrellas")):
        top = risks[0] if risks else {}
        return (
            f"Hay {kpis['negative']} opiniones críticas ({kpis['negative_rate']:.1f}%). "
            f"El patrón más repetido es {top.get('label', 'no identificado')} con {top.get('count', 0)} menciones. "
            f"Corrección: {top.get('action', 'revisar el motivo y cerrar la respuesta en 24 h')}. "
            f"Además, solo se contesta el {kpis['negative_response_rate']:.1f}% de las críticas; el objetivo es 100%."
        )

    if any(word in query for word in ("respuesta", "contestar", "respondida")):
        return (
            f"El negocio responde el {kpis['response_rate']:.1f}% de todas las opiniones, pero solo el "
            f"{kpis['negative_response_rate']:.1f}% de las críticas. Primero contesta el 100% de 1-2★ en 24 h "
            "con disculpa concreta, solución privada y cierre público. Después estandariza un guion breve para 4-5★."
        )

    if any(word in query for word in ("mes", "tendencia", "evolucion", "evolución", "periodo")):
        monthly = diagnosis.get("score", {})
        return (
            f"En el histórico analizado hay {kpis['total']} reseñas, media {kpis['average']:.2f}★ y "
            f"{kpis['positive_rate']:.1f}% de clientes satisfechos. Índice de reputación: {monthly.get('label', 'sin datos')}. "
            "La lectura mensual conviene contrastarla con el mes comparable del año anterior antes de decidir cambios fuertes."
        )

    if any(word in query for word in ("foto", "visual", "contenido")):
        return (
            f"El negocio tiene {context.get('fotos_clientes', 'varias')} fotos de clientes. "
            "Publica una foto semanal del plato o servicio mejor valorado y pide una foto al pedir la reseña. "
            "Eso refuerza el motivo que más se repite en los comentarios positivos y mejora la conversión de la ficha."
        )

    top_strength = strengths[0]["label"] if strengths else "la calidad general del servicio"
    first_strategy = strategies[0] if strategies else {}
    return (
        f"{diagnosis.get('headline', 'La ficha mantiene una base sólida.')} "
        f"El motivo mejor valorado es {top_strength.lower()}. "
        f"Prioridad inmediata: {first_strategy.get('move', 'contestar las críticas y repetir la experiencia 5★')}. "
        f"KPI: {first_strategy.get('kpi', '100% de críticas respondidas en 15 días')}."
    )


def _remote_answer(question, context):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    endpoint = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Pregunta del usuario: {question}\n\nContexto de datos:\n{json.dumps(context, ensure_ascii=False)}",
            },
        ],
        "temperature": 0.3,
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def answer_client_question(client, question):
    context = client_context(client)
    context["fotos_clientes"] = client.customer_photos
    remote = _remote_answer(question, context)
    if remote:
        return remote, "ia"
    return _local_answer(question, context), "local"
