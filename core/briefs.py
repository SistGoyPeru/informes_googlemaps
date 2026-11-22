from . import analytics, insights

AUTHOR = "Alex Goyzueta"
WHATSAPP = "+34 624 59 23 98"
WHATSAPP_URL = "https://wa.me/34624592398"
EMAIL = "alexgoyzueta2018@gmail.com"


def email_brief(client, frame, month=None, year=None):
    cutoff = analytics.last_complete_month()
    if month:
        subset = frame[frame["mes"] == month]
        period = analytics.month_label(month)
    elif year:
        subset = frame[frame["anio"] == year]
        period = f"año {year}"
    else:
        subset = analytics.complete_months(frame)
        period = f"histórico hasta {analytics.month_label(cutoff)}"

    kpis = analytics.reputation_kpis(subset)
    score = insights.scorecard(kpis)
    diagnosis = insights.client_diagnosis(subset, client)
    rhythm = insights.review_rhythm(subset)
    strength = diagnosis["strengths"][0] if diagnosis.get("strengths") else "la operación mantiene una base estable de clientes"
    action = diagnosis["actions"][0] if diagnosis.get("actions") else {"title": "Mantener el nivel actual", "detail": "Revisar el informe del próximo mes y sostener la respuesta a los clientes."}

    if kpis["total"]:
        summary = (
            f"La ficha de {client.name} muestra un rating medio de {kpis['average']:.2f}★ y un "
            f"{kpis['positive_rate']:.1f}% de clientes satisfechos. El índice de reputación es "
            f"{score['score']:.0f}/100 ({score['label'].lower()}); hay {kpis['negative']} opiniones críticas "
            "que conviene convertir en mejoras visibles."
        )
        focus = (
            f"El activo más fuerte es que {strength.lower()} "
            f"La palanca más rápida es {action['title'].lower()}: {action['detail']} "
            "Conviene medir el resultado durante los próximos 30 días."
        )
    else:
        summary = f"Todavía no hay reseñas válidas procesadas para {client.name} en el periodo seleccionado."
        focus = "El siguiente paso es importar el histórico completo desde la ficha de Google Maps."

    subject = f"Análisis de reputación Google Maps · {client.name} · {period}"
    comment = (
        f"Adjunto el análisis de reputación de {client.name} ({period}). Incluye rating real, composición de opiniones, "
        "comentarios verificables y un plan de acción con responsables y métricas. "
        "Si te parece, lo revisamos juntos y cerramos el plan del próximo mes."
    ).strip()
    strategy_lines = [
        f"- {item['phase']}: {item['objective']} KPI: {item['kpi']}."
        for item in diagnosis.get("strategies", [])
    ]
    growth_lines = [
        f"- {item['title']}: {'; '.join(item['tactics'][:2])} KPI: {item['kpi']}."
        for item in diagnosis.get("growth", [])
    ]
    body_lines = [
        "Hola,",
        "",
        f"Te adjunto el análisis de reputación de {client.name} con datos reales de Google Maps ({period}).",
        "",
        summary,
        "",
        focus,
        "",
        f"Ritmo de opiniones: {rhythm['recent_per_day']:.1f} al día en los últimos 30 días. Respuestas: {kpis['response_rate']:.1f}% del total y {kpis['negative_response_rate']:.1f}% de las críticas.",
        "",
        "Estrategia recomendada:",
    ] + strategy_lines + [
        "",
        "Motor de crecimiento:",
    ] + growth_lines + [
        "",
        "Qué encontrarás en el archivo:",
        "- Informe general histórico.",
        "- Informe por año.",
        "- Informe mensual de cada mes.",
        "- Gráficos explicados, estrategia de 90 días, motor de crecimiento y plan de acción en cada PDF.",
        "",
        "Si quieres, lo revisamos en 10 minutos y dejamos cerrado el plan del próximo mes.",
        "",
        "Un saludo,",
        AUTHOR,
        f"WhatsApp: {WHATSAPP} · {WHATSAPP_URL}",
        f"Email: {EMAIL}",
    ]
    return {
        "client": client.name,
        "period": period,
        "subject": subject,
        "comment": comment,
        "body": "\n".join(body_lines),
        "summary": summary,
        "focus": focus,
        "action_title": action["title"],
        "action_detail": action["detail"],
        "strategies": diagnosis.get("strategies", []),
        "growth": diagnosis.get("growth", []),
    }
