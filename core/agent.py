from . import analytics, insights


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

    if any(word in query for word in ("gratis", "sin costo", "sin coste", "precio", "pagar", "api de pago")):
        return (
            "Sí. Este agente es gratuito: analiza las reseñas guardadas y responde sin APIs de pago ni claves externas. "
            "Puedes pedirle un plan, críticas, reseñas, captación o contenido las veces que quieras."
        )

    if any(word in query for word in ("plan", "30 dias", "30 días", "estrategia", "acciones", "qué hacer", "que hacer")):
        steps = [
            f"{index}) {item['phase']}: {item['move']} KPI: {item['kpi']}."
            for index, item in enumerate(strategies, 1)
        ]
        return (
            "Plan gratuito con los datos del informe: " + " ".join(steps)
            if steps else "Primero importa el histórico completo; después el agente propondrá el plan por fases."
        )

    if any(word in query for word in ("presupuesto", "barato", "coste cero", "costo cero", "bajo costo")):
        return (
            "Empieza con tres acciones de coste cero: responder el 100% de las críticas en 24 h, "
            "pedir la reseña al entregar el servicio con un guion de 10 segundos y publicar una foto semanal. "
            f"Solo con eso apuntas a {growth[0].get('kpi', '2-3 reseñas/día') if growth else 'más reseñas y mejor media'}."
        )

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
        score = diagnosis.get("score", {})
        return (
            f"En el histórico analizado hay {kpis['total']} reseñas, media {kpis['average']:.2f}★ y "
            f"{kpis['positive_rate']:.1f}% de clientes satisfechos. Índice de reputación: {score.get('label', 'sin datos')}. "
            "La lectura mensual conviene contrastarla con el mes comparable del año anterior antes de decidir cambios fuertes."
        )

    if any(word in query for word in ("foto", "visual", "contenido", "publicar")):
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


def answer_client_question(client, question):
    context = client_context(client)
    context["fotos_clientes"] = client.customer_photos
    return _local_answer(question, context), "local"
