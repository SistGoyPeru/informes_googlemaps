from urllib.parse import urlencode

from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import analytics, briefs, charts, insights, reports, services
from .forms import ClientUrlForm
from .models import Client, Review


def _report_url(pk, vista="total", year=None, month=None, week=None, day=None):
    params = {"vista": vista}
    if year:
        params["year"] = year
    if month:
        params["month"] = month
    if week:
        params["week"] = week
    if day:
        params["day"] = day
    return f"{reverse('client_report', args=[pk])}?{urlencode(params)}"


def _review_rows(source, limit=6):
    if source.empty:
        return []
    ordered = source.sort_values("date", ascending=False).head(limit)
    return [
        {
            "date": row["date"].strftime("%d/%m/%Y"),
            "author": row["author"] or "Cliente",
            "rating": int(row["rating"]),
            "text": str(row["text"])[:300],
            "response": str(row["owner_response"])[:300],
        }
        for _, row in ordered.iterrows()
    ]


def _complete_frame(client):
    return analytics.complete_months(analytics.enrich(analytics.to_frame(client.reviews.all())))


def _validate_period(frame, month=None, year=None):
    if month and (frame.empty or month not in frame["mes"].tolist()):
        raise Http404("Mes sin datos completos.")
    if year and (frame.empty or int(year) not in frame["anio"].tolist()):
        raise Http404("Año sin datos.")


def _portfolio_context():
    rows = []
    for item in Client.objects.all():
        frame = analytics.report_frame(item.reviews.all())
        kpis = analytics.reputation_kpis(frame)
        score = insights.scorecard(kpis)
        rhythm = insights.review_rhythm(frame)
        monthly = analytics.monthly_table(frame)
        best = monthly.sort_values("Rating", ascending=False).iloc[0] if not monthly.empty else None
        rows.append({
            "pk": item.pk,
            "name": item.name,
            "url": _report_url(item.pk),
            "place_id": item.place_id,
            "average": kpis["average"],
            "score": score["score"],
            "label": score["label"],
            "color": score["color"],
            "total": kpis["total"],
            "positive_rate": kpis["positive_rate"],
            "five_rate": kpis["five_rate"],
            "negative": kpis["negative"],
            "negative_rate": kpis["negative_rate"],
            "response_rate": kpis["response_rate"],
            "negative_response_rate": kpis["negative_response_rate"],
            "rhythm": rhythm["recent_per_day"],
            "best_month": f"{analytics.month_label(best['Mes'])} · {best['Rating']:.2f}★" if best is not None else "Sin datos",
        })
    rows.sort(key=lambda item: (-item["score"], -item["average"], -item["total"]))
    for position, row in enumerate(rows, 1):
        row["rank"] = position
    frame = analytics.report_frame(Review.objects.all())
    kpis = analytics.reputation_kpis(frame)
    score = insights.scorecard(kpis)
    guide = [
        {"name": "Rating medio", "why": "La nota general que ve cualquiera en Google. Se mide sobre 5 estrellas."},
        {"name": "Satisfacción", "why": "Es el rating convertido a porcentaje. 4,5★ equivale al 90% de satisfacción."},
        {"name": "Excelencia 5★", "why": "Mide cuántos clientes quedan encantados, no solo conformes."},
        {"name": "Saldo neto", "why": "Positivas menos incidencias. Si baja, el negocio pierde confianza aunque tenga muchas reseñas."},
        {"name": "Respuesta a 1-2★", "why": "Muestra si el cliente enfadado recibe una solución. Es la palanca más rápida."},
        {"name": "Ritmo de reseñas", "why": "Reseñas nuevas por día en los últimos 30 días. Sin ritmo, la ficha se enfría."},
    ]
    return {
        "rows": rows,
        "portfolio_kpis": kpis,
        "portfolio_score": score,
        "ranking_chart": charts.client_ranking(rows),
        "guide": guide,
        "total_clients": len(rows),
        "new_client_url": reverse("new_client"),
    }


def home(request):
    return render(request, "core/dashboard.html", _portfolio_context())


def new_client(request):
    form = ClientUrlForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            client = services.sync_client(form.cleaned_data["url"], form.cleaned_data["limit"])
            messages.success(request, f"Datos de {client.name} importados y guardados correctamente.")
            return redirect(_report_url(client.pk))
        except Exception as error:
            messages.error(request, f"No se pudo importar: {error}")
    return render(request, "core/new_client.html", {"form": form})


def update_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        try:
            updated = services.refresh_client(client)
            messages.success(request, f"{updated.name} actualizado sin volver a buscar la URL.")
        except Exception as error:
            messages.error(request, f"No se pudo actualizar: {error}")
    return redirect(_report_url(pk))


def client_report(request, pk):
    client = get_object_or_404(Client, pk=pk)
    frame = _complete_frame(client)
    requested_month = request.GET.get("month") or ""

    years = sorted(frame["anio"].unique().tolist(), reverse=True) if not frame.empty else []
    try:
        year = int(request.GET.get("year") or (years[0] if years else 0))
    except (TypeError, ValueError):
        year = years[0] if years else 0
    frame_year = frame[frame["anio"] == year] if year else frame
    frame_complete_year = frame_year

    months = sorted(frame_year["mes"].unique().tolist()) if not frame_year.empty else []
    month = requested_month or (months[-1] if months else "")
    if month not in months:
        month = months[-1] if months else ""
    frame_month = frame_year[frame_year["mes"] == month] if month else frame_year

    weeks = analytics.week_options(frame_month, month) if month else []
    try:
        week = int(request.GET.get("week") or (weeks[-1]["number"] if weeks else 0))
    except (TypeError, ValueError):
        week = weeks[-1]["number"] if weeks else 0
    if week and week not in [item["number"] for item in weeks]:
        week = weeks[-1]["number"] if weeks else 0
    frame_week = frame_month[frame_month["semana_num"] == week] if week else frame_month

    days = analytics.day_options(frame_month, month, week) if month else []
    day = request.GET.get("day") or (days[-1]["value"] if days else "")
    if day and day not in [item["value"] for item in days]:
        day = days[-1]["value"] if days else ""
    frame_day = frame_week[frame_week["date"].dt.strftime("%Y-%m-%d") == day] if day else frame_week

    vista = request.GET.get("vista", "total")
    views_map = {
        "total": frame,
        "anio": frame_complete_year,
        "mes": frame_month,
        "semana": frame_week,
        "dia": frame_day,
    }
    if vista not in views_map:
        vista = "total"
    subset = views_map[vista]

    chart_source = frame_complete_year if vista == "anio" else (frame_year if vista in ("mes", "semana", "dia") else frame)
    period_labels = {
        "total": f"Histórico completo · {frame['mes'].min() if not frame.empty else 'sin datos'} a {frame['mes'].max() if not frame.empty else 'sin datos'}",
        "anio": f"Año {year}" if year else "Año sin datos",
        "mes": analytics.month_label(month) if month else "Mes sin datos",
        "semana": f"{analytics.month_label(month)} · Semana {week}" if week else analytics.month_label(month),
        "dia": f"{day.strftime('%d/%m/%Y') if hasattr(day, 'strftime') else day}" if day else "Día sin datos",
    }
    kpis = analytics.reputation_kpis(subset)
    diagnosis = insights.client_diagnosis(subset, client)
    notes = insights.chart_notes(vista, chart_source, subset, kpis)
    clients = [
        {
            "pk": item.pk,
            "name": item.name,
            "rating": item.rating,
            "total": item.reviews.count(),
            "url": _report_url(item.pk),
        }
        for item in Client.objects.all()
    ]
    pdf_base = reverse("export_pdf", args=[pk])
    brief_period = f"?mes={month}" if vista in ("mes", "semana", "dia") and month else (f"?anio={year}" if vista == "anio" and year else "")
    brief_pdf_url = reverse("export_brief", args=[pk]) + brief_period
    brief_txt_url = reverse("export_brief_txt", args=[pk]) + brief_period
    brief = briefs.email_brief(
        client,
        frame,
        month if vista in ("mes", "semana", "dia") else None,
        year if vista == "anio" else None,
    )
    pdf_years = [
        {"year": int(value), "url": f"{pdf_base}?anio={int(value)}", "active": int(value) == year}
        for value in (frame["anio"].unique().tolist() if not frame.empty else [])
    ]
    pdf_months = [
        {
            "month": value,
            "label": analytics.month_label(value),
            "url": f"{pdf_base}?mes={value}",
            "active": value == month,
        }
        for value in sorted(frame["mes"].unique().tolist()) if not frame.empty
    ]
    context = {
        "client": client,
        "clients": clients,
        "vista": vista,
        "vista_label": period_labels[vista],
        "year": year,
        "years": years,
        "month": month,
        "months": months,
        "week": week,
        "weeks": weeks,
        "day": day,
        "days": days,
        "tabs": [
            {"label": "Total", "url": _report_url(pk, "total", year, month, week, day), "active": vista == "total"},
            {"label": "Año", "url": _report_url(pk, "anio", year, month, week, day), "active": vista == "anio"},
            {"label": "Mes", "url": _report_url(pk, "mes", year, month, week, day), "active": vista == "mes"},
            {"label": "Semana", "url": _report_url(pk, "semana", year, month, week, day), "active": vista == "semana"},
            {"label": "Día", "url": _report_url(pk, "dia", year, month, week, day), "active": vista == "dia"},
        ],
        "kpis": kpis,
        "client_kpis": analytics.reputation_kpis(frame),
        "score": diagnosis["score"],
        "diagnosis": diagnosis,
        "themes": analytics.themes(subset),
        "notes": notes,
        "charts": {
            "monthly": charts.monthly(chart_source),
            "distribution": charts.distribution(subset),
            "response": charts.response_by_rating(chart_source),
            "weekly": charts.weekly(frame_month),
            "daily": charts.daily(frame_week),
            "weekday": charts.weekday(chart_source),
            "sentiment": charts.sentiment(subset),
        },
        "monthly_table": analytics.records(analytics.monthly_table(chart_source)),
        "yearly_table": analytics.records(analytics.yearly_table(frame)),
        "weekly_table": analytics.records(analytics.weekly_table(frame_month)),
        "daily_table": analytics.records(analytics.daily_table(frame_week)),
        "reviews": _review_rows(subset if vista == "dia" else frame, 6),
        "positive_quotes": analytics.verbatims(subset, True),
        "negative_quotes": analytics.verbatims(subset, False),
        "pdf_url": pdf_base + (f"?mes={month}" if month else (f"?anio={year}" if vista == "anio" else "")),
        "pdf_general_url": pdf_base,
        "pdf_year_url": pdf_base + (f"?anio={year}" if year else ""),
        "pdf_month_url": pdf_base + (f"?mes={month}" if month else ""),
        "pdf_package_url": reverse("export_pdf_package", args=[pk]),
        "brief": brief,
        "brief_pdf_url": brief_pdf_url,
        "brief_txt_url": brief_txt_url,
        "pdf_years": pdf_years,
        "pdf_months": pdf_months,
        "csv_resumen": reverse("export_csv", args=[pk]) + "?tipo=resumen",
        "csv_resenas": reverse("export_csv", args=[pk]) + "?tipo=resenas",
    }
    return render(request, "core/report.html", context)


def export_csv(request, pk):
    client = get_object_or_404(Client, pk=pk)
    kind = request.GET.get("tipo", "resenas")
    allowed = {"resumen", "resenas", "mensual", "anual", "semanal", "diario"}
    if kind not in allowed:
        raise Http404("Tipo de CSV no válido")
    frame = analytics.report_frame(client.reviews.all())
    path = reports.export_csv(client, kind, frame)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="text/csv; charset=utf-8")


def export_brief(request, pk):
    client = get_object_or_404(Client, pk=pk)
    month = request.GET.get("mes") or None
    year = request.GET.get("anio") or None
    frame = _complete_frame(client)
    _validate_period(frame, month, year)
    path = reports.export_brief(client, frame, month, year)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="application/pdf")


def export_brief_txt(request, pk):
    client = get_object_or_404(Client, pk=pk)
    month = request.GET.get("mes") or None
    year = request.GET.get("anio") or None
    frame = _complete_frame(client)
    _validate_period(frame, month, year)
    data = briefs.email_brief(client, frame, month, year)
    content = (
        f"ASUNTO:\n{data['subject']}\n\n"
        f"COMENTARIO SUGERIDO PARA EL ARCHIVO:\n{data['comment']}\n\n"
        f"CUERPO COMPLETO PARA COPIAR:\n{data['body']}\n"
    )
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="ficha_correo_cliente_{pk}.txt"'
    return response


def export_pdf(request, pk):
    client = get_object_or_404(Client, pk=pk)
    month = request.GET.get("mes") or None
    year = request.GET.get("anio") or None
    frame = _complete_frame(client)
    _validate_period(frame, month, year)
    path = reports.export_pdf(client, frame, month, year)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="application/pdf")


def export_pdf_package(request, pk):
    client = get_object_or_404(Client, pk=pk)
    frame = _complete_frame(client)
    path, _ = reports.export_pdf_package(client, frame)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="application/zip")
