import pandas as pd

from . import analytics


def review_rhythm(frame):
    daily_counts = frame.groupby("date").size() if "date" in frame.columns and not frame.empty else pd.Series(dtype=int)
    median_daily = float(daily_counts.median()) if not daily_counts.empty else 0.0
    last_date = frame["date"].max() if "date" in frame.columns and not frame.empty else None
    recent_per_day = 0.0
    if last_date is not None:
        recent = frame[frame["date"] >= last_date - pd.Timedelta(days=30)]
        recent_per_day = len(recent) / 30
    return {
        "median_daily": median_daily,
        "recent_per_day": recent_per_day,
        "low_volume": median_daily <= 1 or recent_per_day < 2,
    }


def scorecard(kpis):
    if not kpis.get("total"):
        return {"score": 0, "label": "Sin datos", "color": "#64748B"}
    score = (
        kpis["average"] / 5 * 58
        + kpis["positive_rate"] * 0.22
        + (100 - kpis["negative_rate"]) * 0.12
        + kpis["response_rate"] * 0.08
    )
    score = round(min(score, 100), 1)
    if score >= 90:
        label = "Excelente"
        color = "#10B981"
    elif score >= 78:
        label = "Sólido"
        color = "#2563EB"
    elif score >= 65:
        label = "En mejora"
        color = "#F59E0B"
    else:
        label = "Atención urgente"
        color = "#EF4444"
    return {"score": score, "label": label, "color": color}


def client_diagnosis(frame, client=None):
    kpis = analytics.reputation_kpis(frame)
    themes = analytics.themes(frame)
    score = scorecard(kpis)
    rhythm = review_rhythm(frame)
    median_daily = rhythm["median_daily"]
    recent_per_day = rhythm["recent_per_day"]
    low_volume = rhythm["low_volume"]
    if not kpis.get("total"):
        return {
            "score": score,
            "headline": "Todavía no hay reseñas con fecha válida.",
            "strengths": ["La ficha ya está conectada a Google Maps."],
            "risks": ["Faltan reseñas procesadas para generar conclusiones."],
            "actions": [{
                "priority": "Alta", "title": "Actualizar datos",
                "detail": "Pulsa Actualizar datos para traer el histórico completo.",
                "owner": "Administrador", "deadline": "Hoy", "impact": "Alta", "effort": "Bajo", "kpi": "Histórico disponible",
            }],
        }

    strengths = []
    if kpis["five_rate"] >= 70:
        strengths.append(f"El {kpis['five_rate']:.1f}% de las reseñas son 5★: la excelencia es la norma, no la excepción.")
    elif kpis["five_rate"] >= 50:
        strengths.append(f"El {kpis['five_rate']:.1f}% de las reseñas alcanza 5★, una base sólida sobre la que trabajar.")
    if kpis["positive_rate"] >= 85:
        strengths.append(f"El {kpis['positive_rate']:.1f}% de los clientes se va satisfecho (4-5★).")
    for item in themes["good"][:2]:
        strengths.append(f"{item['label']} aparece {item['count']} veces en los comentarios.")
    if client and client.customer_photos >= 100:
        strengths.append(f"Hay {client.customer_photos} fotos de clientes: prueba social suficiente para reforzar la conversión.")

    risks = []
    if kpis["negative_response_rate"] < 50:
        risks.append(f"Solo se responde el {kpis['negative_response_rate']:.1f}% de las reseñas de 1-2★. El cliente insatisfecho no ve una reacción.")
    if kpis["negative_rate"] > 8:
        risks.append(f"Las incidencias (1-2★) representan el {kpis['negative_rate']:.1f}% del total; por encima del objetivo del 8%.")
    if kpis["five_rate"] < 60:
        risks.append(f"La excelencia cae al {kpis['five_rate']:.1f}%; hay margen claro para subir a 4,70★.")
    if low_volume:
        risks.append(
            f"El ritmo de reseñas es bajo: mediana de {median_daily:.1f} por día activo y "
            f"{recent_per_day:.1f} diarias en los últimos 30 días. La ficha pierde frescura y señal de confianza."
        )
    for item in themes["bad"][:2]:
        risks.append(f"{item['label']} se repite {item['count']} veces y es una causa directa de pérdida de rating.")
    if not strengths:
        strengths.append("La operación está estabilizada; no aparece un patrón crítico en los comentarios.")
    if not risks:
        risks.append("No hay patrones críticos. El riesgo está en perder el nivel actual si se relaja la respuesta o la operación.")

    actions = []
    if kpis["negative_response_rate"] < 80:
        actions.append({
            "priority": "Alta",
            "title": "Responder en 24 h a 1-3★",
            "detail": "Disculpa concreta, solución privada y seguimiento. Objetivo: 100% de negativas contestadas.",
            "owner": "Atención al cliente",
            "deadline": "24 h",
            "impact": "Alta",
            "effort": "Bajo",
            "kpi": f"De {kpis['negative_response_rate']:.1f}% a 100%",
        })
    if kpis["negative_rate"] > 6:
        actions.append({
            "priority": "Alta",
            "title": "Contener incidencias",
            "detail": "Revisar esperas, errores de pedido y raciones en los días con peor rating.",
            "owner": "Cocina y sala",
            "deadline": "7 días",
            "impact": "Alta",
            "effort": "Medio",
            "kpi": f"De {kpis['negative']} a menos del 8%",
        })
    if kpis["five_rate"] < 80:
        actions.append({
            "priority": "Media",
            "title": "Subir la excelencia",
            "detail": "Checklist de salida de cocina, saludo obligatorio y revisión de tiempos en hora punta.",
            "owner": "Responsable de operaciones",
            "deadline": "30 días",
            "impact": "Media",
            "effort": "Medio",
            "kpi": f"De {kpis['five_rate']:.1f}% a 80% de 5★",
        })
    actions.append({
        "priority": "Alta" if low_volume else "Media",
        "title": "Pedir más reseñas cada día" if low_volume else "Más prueba social",
        "detail": (
            "QR en mesa y en el entregapedidos, guion de 10 segundos al cerrar el servicio y seguimiento diario del equipo. "
            "Pedir la reseña cuando el cliente acaba de recibir el plato, sin incentivos prohibidos por Google."
            if low_volume else
            "QR en mesa para pedir reseña y foto; destacar los platos más valorados en la respuesta del propietario."
        ),
        "owner": "Todo el equipo",
        "deadline": "Diario",
        "impact": "Alta",
        "effort": "Bajo",
        "kpi": f"De {recent_per_day:.1f} a 2-3 reseñas/día" if low_volume else "+20 fotos y +30 reseñas al mes",
    })

    headline = (
        f"Reputación {score['label'].lower()}: rating {kpis['average']:.2f}★, "
        f"{kpis['positive_rate']:.1f}% de clientes satisfechos y {kpis['negative']} incidencias."
    )
    if low_volume:
        headline += f" Ritmo bajo de reseñas: {recent_per_day:.1f} al día en los últimos 30 días."
    return {"score": score, "headline": headline, "strengths": strengths, "risks": risks, "actions": actions}


def _range_note(table, label_column):
    if table.empty:
        return "Sin suficientes datos para comparar periodos."
    best = table.sort_values("Rating", ascending=False).iloc[0]
    worst = table.sort_values("Rating").iloc[0]
    return (
        f"Mejor {label_column}: {best[label_column]} con {best['Rating']:.2f}★. "
        f"Más débil: {worst[label_column]} con {worst['Rating']:.2f}★."
    )


def chart_notes(level, frame, subset, kpis):
    notes = {
        "monthly": "Sin datos mensuales todavía.",
        "distribution": "Sin distribución disponible.",
        "response": "Sin respuestas registradas.",
        "weekly": "Sin desglose semanal en este periodo.",
        "daily": "Sin desglose diario en este periodo.",
        "weekday": "Sin patrón semanal suficiente.",
        "sentiment": "Sin suficientes reseñas para clasificar sentimiento.",
    }
    if not kpis.get("total"):
        return notes
    monthly = analytics.monthly_table(frame)
    notes["monthly"] = _range_note(monthly, "Mes") + f" El volumen total es de {kpis['total']} reseñas."
    notes["distribution"] = (
        f"{kpis['five']} reseñas de 5★ marcan la excelencia; {kpis['negative']} reseñas de 1-2★ concentran el riesgo. "
        f"Las 3★ y 4★ explican la zona de mejora."
    )
    notes["response"] = (
        f"Se contesta el {kpis['response_rate']:.1f}% de todas las reseñas, pero solo el "
        f"{kpis['negative_response_rate']:.1f}% de las negativas. Responder más a 1-2★ es la palanca de mayor impacto."
    )
    if not subset.empty:
        weekly = analytics.weekly_table(subset)
        if not weekly.empty:
            notes["weekly"] = _range_note(weekly, "Semana")
        daily = analytics.daily_table(subset)
        if not daily.empty:
            peak = daily.sort_values("Reseñas", ascending=False).iloc[0]
            notes["daily"] = f"Día con más actividad: {peak['Fecha']} con {peak['Reseñas']} reseñas y {peak['Rating']:.2f}★."
    weekday = analytics.daily_table(frame)
    if not weekday.empty:
        grouped = frame.groupby("dia_semana")["rating"].agg(["mean", "size"]).sort_values("mean", ascending=False)
        if not grouped.empty:
            notes["weekday"] = (
                f"Mejor día por rating: {grouped.index[0]} ({grouped.iloc[0]['mean']:.2f}★). "
                f"Día con más reseñas: {grouped['size'].idxmax()} ({int(grouped['size'].max())})."
            )
    neutral = kpis["total"] - kpis["positive"] - kpis["negative"]
    notes["sentiment"] = (
        f"De {kpis['total']} reseñas, {kpis['positive']} son clientes satisfechos (4-5★, {kpis['positive_rate']:.1f}%), "
        f"{neutral} son neutros (3★) y {kpis['negative']} son incidencias (1-2★). "
        "Es la forma más rápida de ver si el negocio suma confianza o pierde clientes."
    )
    return notes
