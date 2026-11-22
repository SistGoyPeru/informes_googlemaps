from . import analytics, insights

AUTHOR = "Alex Goyzueta"
WHATSAPP = "+34 624 59 23 98"
WHATSAPP_URL = "https://wa.me/34624592398"
EMAIL = "alexgoyzueta2018@gmail.com"


def email_brief(client, frame, month=None, year=None):
    cutoff = analytics.last_complete_month()
    current_note = ""
    if month:
        subset = frame[frame["mes"] == month]
        period = analytics.month_label(month)
        if month > cutoff:
            current_note = "Este mes está en curso, por lo que aún pueden faltar días de reseñas."
    elif year:
        subset = frame[frame["anio"] == year]
        period = f"año {year}"
    else:
        subset = analytics.complete_months(frame)
        period = f"histórico hasta {analytics.month_label(cutoff)}"
        current_note = "El informe general y anual llega hasta el último mes completo."

    kpis = analytics.reputation_kpis(subset)
    score = insights.scorecard(kpis)
    diagnosis = insights.client_diagnosis(subset, client)
    rhythm = insights.review_rhythm(subset)
    strength = diagnosis["strengths"][0] if diagnosis.get("strengths") else "la operación mantiene una base estable de clientes"
    action = diagnosis["actions"][0] if diagnosis.get("actions") else {"title": "Mantener el nivel actual", "detail": "Revisar el informe del próximo mes y sostener la respuesta a los clientes."}

    if kpis["total"]:
        summary = (
            f"{client.name} tiene un rating medio de {kpis['average']:.2f}★, "
            f"un {kpis['positive_rate']:.1f}% de clientes satisfechos y {kpis['negative']} incidencias de 1-2★. "
            f"El índice de reputación es {score['score']:.0f}/100 ({score['label'].lower()})."
        )
        focus = (
            f"El punto fuerte es que {strength.lower()} "
            f"La oportunidad más rápida es {action['title'].lower()}: {action['detail']}"
        )
    else:
        summary = f"Todavía no hay reseñas válidas procesadas para {client.name} en el periodo seleccionado."
        focus = "El siguiente paso es importar el histórico completo desde la ficha de Google Maps."

    subject = f"Informe de reputación Google Maps · {client.name} · {period}"
    comment = (
        f"Adjunto el informe de reputación de {client.name} ({period}). Incluye rating real, satisfechos vs incidencias, "
        "comentarios verificables y un plan de mejora con acciones concretas. "
        f"Si te parece, lo revisamos juntos y definimos el siguiente paso. {current_note}"
    ).strip()
    body_lines = [
        f"Hola,",
        "",
        f"Te adjunto la ficha y los informes de reputación de {client.name} con datos reales de Google Maps ({period}).",
        "",
        summary,
        "",
        focus,
        "",
        f"Ritmo de reseñas: {rhythm['recent_per_day']:.1f} al día en los últimos 30 días. Respuestas: {kpis['response_rate']:.1f}% del total y {kpis['negative_response_rate']:.1f}% de las incidencias.",
        "",
        "Qué encontrarás en el archivo:",
        "- Informe general histórico.",
        "- Informe por año.",
        "- Informe mensual, incluido el mes en curso cuando tiene reseñas.",
        "- Gráficos explicados y plan de mejora en cada PDF.",
        "",
        "Si quieres, lo revisamos en 10 minutos y dejamos cerrado el plan del próximo mes.",
        "",
        f"Un saludo,",
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
        "last_complete": analytics.month_label(cutoff),
    }
