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


def growth_playbook(kpis, themes, low_volume, recent_per_day):
    strength = themes["good"][0] if themes.get("good") else None
    return [
        {
            "title": "Más valoraciones positivas",
            "objective": "Aumentar el volumen de reseñas y repetir los motivos que mejor valora el cliente.",
            "tactics": [
                "Pedir la opinión en el momento de mayor satisfacción: al entregar el plato o al cerrar el servicio.",
                "QR en mesa, ticket y mostrador que abra directamente el formulario de reseñas de Google.",
                "Guion de 10 segundos del equipo: si todo salió bien, invitar a dejar una reseña sin presionar.",
                (
                    f"Repetir en las respuestas públicas el motivo mejor valorado: {strength['label'].lower()}."
                    if strength else "Repetir en las respuestas públicas los puntos fuertes detectados en el informe."
                ),
                "Responder en 24 h: las positivas refuerzan la relación y las críticas evitan pérdida de confianza.",
            ],
            "kpi": f"De {recent_per_day:.1f} a 2-3 reseñas/día y mantener 80% de 5★",
            "owner": "Atención al cliente",
            "deadline": "30 días",
        },
        {
            "title": "Captar clientes nuevos",
            "objective": "Convertir la ficha de Google Maps en un canal de adquisición medible.",
            "tactics": [
                "Publicar una foto semanal de platos destacados y una novedad por semana en la ficha.",
                "Completar categoría, horario, menú, atributos y foto de portada con términos de la zona.",
                "Usar las mejores reseñas como contenido: citar el motivo mejor valorado en publicaciones y redes.",
                "Añadir enlace de WhatsApp con mensaje predefinido y contabilizar consultas cada semana.",
                "Acuerdos locales con gimnasios, talleres, hoteles u oficinas cercanas con cupón canjeable y seguimiento.",
            ],
            "kpi": "+20% de visitas a la ficha y +15 consultas por WhatsApp en 30 días",
            "owner": "Marketing y administración",
            "deadline": "30 días",
        },
    ]


def _strategies(kpis, themes, low_volume):
    top = themes["bad"][0] if themes.get("bad") else None
    return [
        {
            "phase": "0-7 días · Contención",
            "objective": "Que ninguna opinión crítica quede sin respuesta visible para futuros clientes.",
            "move": "Responder en 24 h, llevar la solución a privado y cerrar con un mensaje breve y concreto.",
            "kpi": f"De {kpis['negative_response_rate']:.1f}% a 100% de 1-2★ contestadas",
        },
        {
            "phase": "8-30 días · Corrección",
            "objective": (
                f"Reducir la causa más repetida: {top['label'].lower()}."
                if top else "Mantener la operación estable y evitar nuevas desviaciones."
            ),
            "move": (
                f"{top['action'].capitalize()}. Revisar el efecto con una comparación semanal de menciones."
                if top else "Reforzar checklist de salida, saludo y control de tiempos en hora punta."
            ),
            "kpi": f"Reducir a la mitad las {top['count']} menciones detectadas" if top else "Sostener 4★ o más en el 90% de las opiniones",
        },
        {
            "phase": "31-90 días · Crecimiento",
            "objective": "Convertir la satisfacción en prueba social y en un flujo estable de nuevas opiniones.",
            "move": (
                "QR en mesa y entregapedidos, guion de 10 segundos del equipo y petición de foto del plato."
                if low_volume else "QR permanente, fotos destacadas y respuesta pública que refuerce los platos mejor valorados."
            ),
            "kpi": "2-3 reseñas/día y +20 fotos al mes" if low_volume else "+30 reseñas y +20 fotos en 30 días",
        },
    ]


def client_diagnosis(frame, client=None):
    kpis = analytics.reputation_kpis(frame)
    themes = analytics.themes(frame)
    score = scorecard(kpis)
    rhythm = review_rhythm(frame)
    median_daily = rhythm["median_daily"]
    recent_per_day = rhythm["recent_per_day"]
    low_volume = rhythm["low_volume"]
    name = client.name if client else "la ficha"

    if not kpis.get("total"):
        return {
            "score": score,
            "headline": "Todavía no hay reseñas con fecha válida para analizar.",
            "strengths": ["La ficha ya está conectada a Google Maps; la base del análisis está lista."],
            "risks": ["Sin reseñas procesadas no hay evidencia suficiente para dar conclusiones."],
            "actions": [{
                "priority": "Alta",
                "title": "Importar el histórico completo",
                "detail": "Pulsa Actualizar datos para traer todas las reseñas con fecha y valoración válidas.",
                "owner": "Administrador",
                "deadline": "Hoy",
                "impact": "Alta",
                "effort": "Bajo",
                "kpi": "Histórico disponible y analizable",
            }],
            "strategies": [{
                "phase": "0-7 días · Arranque",
                "objective": "Disponer de datos completos antes de dar recomendaciones.",
                "move": "Importar el histórico, revisar fechas y confirmar que las reseñas con texto estén cargadas.",
                "kpi": "Historial importado y listo para analizar",
            }],
            "growth": [{
                "title": "Más valoraciones positivas",
                "objective": "Preparar la captación de reseñas apenas haya datos suficientes.",
                "tactics": ["QR en mesa y mostrador.", "Guion de petición de reseña.", "Respuesta pública a cada opinión."],
                "kpi": "Sistema listo para usar",
                "owner": "Atención al cliente",
                "deadline": "7 días",
            }, {
                "title": "Captar clientes nuevos",
                "objective": "Tener la ficha lista para convertir visitas en consultas.",
                "tactics": ["Fotos de portada y platos destacados.", "WhatsApp con mensaje predefinido.", "Alianzas locales cercanas."],
                "kpi": "Ficha optimizada y enlace activo",
                "owner": "Marketing y administración",
                "deadline": "7 días",
            }],
        }

    strengths = []
    if kpis["five_rate"] >= 70:
        strengths.append(f"La excelencia es constante: el {kpis['five_rate']:.1f}% de las opiniones son 5★ y sostienen la nota pública.")
    elif kpis["five_rate"] >= 50:
        strengths.append(f"Hay una base sólida de clientes satisfechos: el {kpis['five_rate']:.1f}% otorga 5★.")
    if kpis["positive_rate"] >= 85:
        strengths.append(f"La mayoría de quienes opinan se va conforme: {kpis['positive_rate']:.1f}% concede 4-5★.")
    for item in themes["good"][:2]:
        strengths.append(f"{item['label']} aparece {item['count']} veces; es un argumento que conviene repetir en respuestas y fotos.")
    if client and client.customer_photos >= 100:
        strengths.append(f"Las {client.customer_photos} fotos de clientes actúan como prueba social y refuerzan la conversión.")

    risks = []
    if kpis["negative_response_rate"] < 80:
        risks.append(
            f"La respuesta a opiniones críticas es el principal hueco: solo se contesta el "
            f"{kpis['negative_response_rate']:.1f}% de las reseñas de 1-2★. Cada respuesta pendiente es una objeción visible."
        )
    if kpis["negative_rate"] > 6:
        risks.append(
            f"Las opiniones críticas representan el {kpis['negative_rate']:.1f}% del total; el objetivo es mantenerlas por debajo del 6%."
        )
    if kpis["five_rate"] < 60:
        risks.append(f"La excelencia cae al {kpis['five_rate']:.1f}%. El reto no es solo subir la media, sino repetir 5★ con más frecuencia.")
    if low_volume:
        risks.append(
            f"El ritmo es bajo: {recent_per_day:.1f} opiniones al día en los últimos 30 días y mediana de "
            f"{median_daily:.1f} por día activo. Una ficha sin entradas nuevas transmite menos confianza."
        )
    for item in themes["bad"][:2]:
        risks.append(f"Se repite {item['label'].lower()} ({item['count']} menciones). Es una causa concreta de pérdida de rating y tiene solución operativa.")
    if not strengths:
        strengths.append("La operación mantiene una base estable; no aparece un patrón crítico en los comentarios.")
    if not risks:
        risks.append("No aparece una alerta clara. El riesgo está en perder el nivel actual por falta de constancia.")

    actions = []
    if kpis["negative_response_rate"] < 80:
        actions.append({
            "priority": "Alta",
            "title": "Responder y cerrar reseñas críticas",
            "detail": "Contesta en menos de 24 h con disculpa concreta, solución por privado y mensaje final cuando esté resuelto. Evita respuestas genéricas.",
            "owner": "Atención al cliente",
            "deadline": "24 h",
            "impact": "Alta",
            "effort": "Bajo",
            "kpi": f"De {kpis['negative_response_rate']:.1f}% a 100% en 15 días",
        })
    if themes["bad"]:
        top = themes["bad"][0]
        actions.append({
            "priority": "Alta" if kpis["negative_rate"] > 6 else "Media",
            "title": f"Corregir {top['label'].lower()}",
            "detail": f"{top['action'].capitalize()}. Revisar el resultado en 7 días y comparar el número de menciones.",
            "owner": "Cocina y sala",
            "deadline": "7 días",
            "impact": "Alta",
            "effort": "Medio",
            "kpi": f"Reducir {top['count']} menciones a la mitad",
        })
    if kpis["five_rate"] < 80:
        actions.append({
            "priority": "Media",
            "title": "Repetir la experiencia 5 estrellas",
            "detail": "Checklist de salida, saludo inicial y control de tiempos en hora punta. Registrar cada desviación en el parte diario.",
            "owner": "Responsable de operaciones",
            "deadline": "30 días",
            "impact": "Media",
            "effort": "Medio",
            "kpi": f"De {kpis['five_rate']:.1f}% a 80% de 5★",
        })
    actions.append({
        "priority": "Alta" if low_volume else "Media",
        "title": "Generar reseñas y fotos de forma constante" if low_volume else "Ampliar la prueba social",
        "detail": (
            "QR en mesa y en el entregapedidos, guion de 10 segundos al cerrar el servicio y petición de foto del plato. "
            "Pedir la opinión justo después del servicio, sin incentivos que infrinjan las normas de Google."
            if low_volume else
            "QR en mesa para pedir reseña y foto; destacar los platos mejor valorados en la respuesta del propietario."
        ),
        "owner": "Todo el equipo",
        "deadline": "Diario",
        "impact": "Alta",
        "effort": "Bajo",
        "kpi": f"De {recent_per_day:.1f} a 2-3 reseñas/día" if low_volume else "+30 reseñas y +20 fotos en 30 días",
    })
    actions.append({
        "priority": "Media",
        "title": "Activar captación local medible",
        "detail": "Ficha completa con foto de portada y publicación semanal, WhatsApp con mensaje predefinido y cupón canjeable con negocios cercanos.",
        "owner": "Marketing y administración",
        "deadline": "30 días",
        "impact": "Alta",
        "effort": "Medio",
        "kpi": "+20% de visitas a la ficha y +15 consultas por WhatsApp",
    })

    headline = (
        f"La reputación de {name} se mantiene en nivel {score['label'].lower()}: "
        f"{kpis['average']:.2f}★ de media y {kpis['positive_rate']:.1f}% de clientes satisfechos. "
        f"Hay {kpis['negative']} opiniones críticas que conviene convertir en mejoras visibles."
    )
    if low_volume:
        headline += f" El ritmo de opiniones es bajo ({recent_per_day:.1f}/día en 30 días), así que falta frescura en la ficha."
    strategies = _strategies(kpis, themes, low_volume)
    return {
        "score": score,
        "headline": headline,
        "strengths": strengths,
        "risks": risks,
        "actions": actions,
        "strategies": strategies,
        "growth": growth_playbook(kpis, themes, low_volume, recent_per_day),
    }


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
        "monthly": "Aún no hay datos mensuales suficientes para mostrar tendencia.",
        "distribution": "Aún no hay distribución de estrellas disponible.",
        "response": "Aún no hay respuestas del propietario registradas.",
        "weekly": "Aún no hay desglose semanal en este periodo.",
        "daily": "Aún no hay actividad diaria suficiente en este periodo.",
        "weekday": "Aún no hay patrón semanal suficiente.",
        "sentiment": "Aún no hay reseñas suficientes para clasificar el sentimiento.",
    }
    if not kpis.get("total"):
        return notes
    monthly = analytics.monthly_table(frame)
    notes["monthly"] = _range_note(monthly, "Mes") + f" Se analizan {kpis['total']} reseñas; la lectura clave es la tendencia, no solo el volumen."
    notes["distribution"] = (
        f"Las {kpis['five']} reseñas de 5★ sostienen la reputación; las {kpis['negative']} opiniones de 1-2★ concentran el riesgo. "
        "Las valoraciones de 3★ y 4★ marcan el margen de mejora más accesible."
    )
    notes["response"] = (
        f"La respuesta global alcanza el {kpis['response_rate']:.1f}%, pero solo el "
        f"{kpis['negative_response_rate']:.1f}% de las opiniones críticas recibe contestación. "
        "Cerrar ese hueco es la palanca más rápida para recuperar confianza."
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
        f"{neutral} se sitúan en 3★ y {kpis['negative']} son opiniones críticas (1-2★). "
        "Esta mezcla indica si la ficha suma confianza o está dejando escapar clientes."
    )
    return notes
