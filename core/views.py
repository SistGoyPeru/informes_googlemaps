from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render, get_object_or_404

from . import analytics, charts, reports, services
from .forms import ClientUrlForm
from .models import Client


def home(request):
    form = ClientUrlForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            client = services.sync_client(form.cleaned_data["url"], form.cleaned_data["limit"])
            messages.success(request, f"Datos de {client.name} importados y guardados correctamente.")
            return redirect("client_report", pk=client.pk)
        except Exception as error:
            messages.error(request, f"No se pudo importar: {error}")
    clients = []
    for client in Client.objects.all():
        frame = analytics.enrich(analytics.to_frame(client.reviews.all()))
        clients.append({"client": client, "kpis": analytics.reputation_kpis(frame)})
    return render(request, "core/home.html", {"form": form, "clients": clients})


def update_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        try:
            updated = services.refresh_client(client)
            messages.success(request, f"{updated.name} actualizado sin volver a buscar la URL.")
        except Exception as error:
            messages.error(request, f"No se pudo actualizar: {error}")
    return redirect("client_report", pk=pk)


def client_report(request, pk):
    client = get_object_or_404(Client, pk=pk)
    frame = analytics.enrich(analytics.to_frame(client.reviews.all()))
    years = sorted(frame["anio"].unique().tolist(), reverse=True) if not frame.empty else []
    try:
        year = int(request.GET.get("year") or (years[0] if years else 0))
    except (TypeError, ValueError):
        year = years[0] if years else 0
    frame_year = frame[frame["anio"] == year] if year else frame
    months = sorted(frame_year["mes"].unique().tolist()) if not frame_year.empty else []
    month = request.GET.get("month") or (months[-1] if months else "")
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
    subset = frame_month[frame_month["semana_num"] == week] if week else frame_month

    context = {
        "client": client,
        "years": years,
        "year": year,
        "months": months,
        "month": month,
        "month_label": analytics.month_label(month) if month else "Histórico",
        "weeks": weeks,
        "week": week,
        "kpis": analytics.reputation_kpis(subset),
        "client_kpis": analytics.reputation_kpis(frame),
        "charts": {
            "monthly": charts.monthly(frame_year),
            "distribution": charts.distribution(subset),
            "response": charts.response_by_rating(frame),
            "weekly": charts.weekly(frame_month),
            "daily": charts.daily(subset),
            "weekday": charts.weekday(frame_year),
            "cumulative": charts.cumulative(frame_year),
        },
        "monthly": analytics.records(analytics.monthly_table(frame_year)),
        "yearly": analytics.records(analytics.yearly_table(frame)),
        "weekly_table": analytics.records(analytics.weekly_table(frame_month)),
        "daily_table": analytics.records(analytics.daily_table(subset)),
        "themes": analytics.themes(subset),
        "positive_quotes": analytics.verbatims(subset, True),
        "negative_quotes": analytics.verbatims(subset, False),
    }
    return render(request, "core/report.html", context)


def export_csv(request, pk):
    client = get_object_or_404(Client, pk=pk)
    kind = request.GET.get("tipo", "resenas")
    allowed = {"resumen", "resenas", "mensual", "anual", "semanal", "diario"}
    if kind not in allowed:
        raise Http404("Tipo de CSV no válido")
    frame = analytics.enrich(analytics.to_frame(client.reviews.all()))
    path = reports.export_csv(client, kind, frame)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type="text/csv; charset=utf-8")


def export_pdf(request, pk):
    client = get_object_or_404(Client, pk=pk)
    frame = analytics.enrich(analytics.to_frame(client.reviews.all()))
    month = request.GET.get("mes") or None
    path = reports.export_pdf(client, frame, month)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
