import base64
import csv
import io
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import analytics, charts
from .models import Review

BASE_DIR = Path(__file__).resolve().parents[1]
LOGO = BASE_DIR / "static" / "assets" / "logo.jpg"


def _client_folder(client):
    folder = Path(settings.MEDIA_ROOT) / "exports" / slugify(client.place_id or client.name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_csv(client, kind, frame=None):
    folder = _client_folder(client)
    filename = f"{kind}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path = folder / filename
    if kind == "resumen":
        rows = [
            {"campo": "Local", "valor": client.name},
            {"campo": "URL", "valor": client.source_url},
            {"campo": "Place ID", "valor": client.place_id},
            {"campo": "Rating Google", "valor": client.rating},
            {"campo": "Reseñas totales", "valor": client.review_total},
            {"campo": "Fotos totales", "valor": client.photo_total},
            {"campo": "Fotos del propietario", "valor": client.owner_photos},
            {"campo": "Fotos de clientes", "valor": client.customer_photos},
            {"campo": "Dirección", "valor": client.address},
            {"campo": "Teléfono", "valor": client.phone},
            {"campo": "Horario", "valor": client.hours},
            {"campo": "Última actualización", "valor": client.last_scraped},
        ]
    elif kind == "resenas":
        values = client.reviews.values("review_id", "author", "rating", "date", "text", "owner_response")
        rows = [
            {
                "review_id": row["review_id"],
                "autor": row["author"],
                "fecha": row["date"].strftime("%Y-%m-%d") if row["date"] else "",
                "rating": row["rating"],
                "reseña": row["text"],
                "respuesta_propietario": row["owner_response"],
                "url": client.source_url,
            }
            for row in values
        ]
    else:
        table_map = {
            "mensual": analytics.monthly_table(frame),
            "anual": analytics.yearly_table(frame),
            "semanal": analytics.weekly_table(frame),
            "diario": analytics.daily_table(frame),
        }
        rows = analytics.records(table_map[kind])
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = list(rows[0].keys()) if rows else ["campo", "valor"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleEs", parent=base["Title"], fontSize=20, leading=24, textColor=colors.HexColor("#240C48")),
        "h2": ParagraphStyle("H2Es", parent=base["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#395B84"), spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("BodyEs", parent=base["BodyText"], fontSize=9, leading=13),
        "small": ParagraphStyle("SmallEs", parent=base["BodyText"], fontSize=7.4, leading=9.4),
        "center": ParagraphStyle("CenterEs", parent=base["BodyText"], alignment=TA_CENTER, fontSize=9, leading=12),
        "bad": ParagraphStyle("BadEs", parent=base["BodyText"], fontSize=9, leading=13, textColor=colors.HexColor("#B91C1C")),
    }


def _table(records, styles, max_rows=None):
    if not records:
        return Paragraph("Sin datos para este periodo.", styles["body"])
    rows = records[:max_rows] if max_rows else records
    header = [Paragraph(f"<b>{key}</b>", styles["small"]) for key in rows[0].keys()]
    body = [[Paragraph(str(value), styles["small"]) for value in row.values()] for row in rows]
    table = Table([header] + body, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#240C48")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7DEEA")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _image(value):
    if not value:
        return None
    return Image(io.BytesIO(base64.b64decode(value)), width=455)


def export_pdf(client, frame, month=None):
    folder = _client_folder(client)
    suffix = month or "general"
    path = folder / f"informe_{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    styles = _styles()
    story = []
    if LOGO.exists():
        story.append(Image(str(LOGO), width=48, height=48))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"{client.name} · Informe de reputación", styles["title"]))
    period = analytics.month_label(month) if month else "Histórico completo"
    story.append(Paragraph(f"Periodo: {period} · Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["center"]))
    story.append(Paragraph("WhatsApp +34 624 59 23 98 · alexgoyzueta2018@gmail.com", styles["center"]))
    story.append(Spacer(1, 10))

    subset = frame[frame["mes"] == month] if month else frame
    kpis = analytics.reputation_kpis(subset)
    kpi_rows = [
        ["Rating medio", f"{kpis['average']:.2f}★", "Satisfacción", f"{kpis['satisfaction']:.1f}%"],
        ["Reseñas", kpis["total"], "Excelencia 5★", f"{kpis['five_rate']:.1f}%"],
        ["Positivas 4-5★", f"{kpis['positive_rate']:.1f}%", "Incidencias 1-2★", kpis["negative"]],
        ["Saldo reputacional", f"+{kpis['balance']:.1f}", "Respuestas", f"{kpis['response_rate']:.1f}%"],
    ]
    kpi_table = Table(kpi_rows, colWidths=[42 * mm, 35 * mm, 42 * mm, 35 * mm])
    kpi_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DEEA")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F8")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EEF2F8")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(kpi_table)

    info = analytics.themes(subset)
    story.append(Paragraph("1. Lectura ejecutiva", styles["h2"]))
    story.append(Paragraph(f"<b>Lo que destacaron:</b> {info['good_text']}", styles["body"]))
    story.append(Paragraph(f"<b>Lo que gusta:</b> {info['strength']}", styles["body"]))
    story.append(Paragraph(f"<b>Lo que hay que corregir:</b> {info['bad_text']}", styles["bad"]))
    story.append(Paragraph(info["correction"], styles["bad"]))
    story.append(Paragraph(f"<b>Oportunidad comercial:</b> solo se responde el {kpis['negative_response_rate']:.1f}% de las reseñas de 1-2★. Contestarlas es la acción de mayor retorno reputacional.", styles["body"]))

    story.append(Paragraph("2. Evolución visual", styles["h2"]))
    image = _image(charts.monthly(frame))
    if image:
        story.append(image)
    image = _image(charts.distribution(subset))
    if image:
        story.append(image)
    image = _image(charts.response_by_rating(frame))
    if image:
        story.append(image)

    story.append(PageBreak())
    story.append(Paragraph("3. Análisis temporal", styles["h2"]))
    story.append(Paragraph("Resumen mensual", styles["h2"]))
    story.append(_table(analytics.records(analytics.monthly_table(frame)), styles, max_rows=20))
    if month:
        image = _image(charts.weekly(subset))
        if image:
            story.append(image)
        story.append(Paragraph("Resumen semanal", styles["h2"]))
        story.append(_table(analytics.records(analytics.weekly_table(subset)), styles))
        image = _image(charts.daily(subset))
        if image:
            story.append(image)
        story.append(Paragraph("Resumen diario", styles["h2"]))
        story.append(_table(analytics.records(analytics.daily_table(subset)), styles, max_rows=25))
    else:
        story.append(Paragraph("Resumen anual", styles["h2"]))
        story.append(_table(analytics.records(analytics.yearly_table(frame)), styles))
        image = _image(charts.weekday(frame))
        if image:
            story.append(image)

    story.append(Paragraph("4. Comentarios verificables", styles["h2"]))
    for item in analytics.verbatims(subset, True):
        story.append(Paragraph(f"<b>{item['date']} · {item['author']} · {item['rating']}★</b><br/>{item['text']}", styles["body"]))
    story.append(Paragraph("Incidencias", styles["h2"]))
    for item in analytics.verbatims(subset, False):
        story.append(Paragraph(f"<b>{item['date']} · {item['author']} · {item['rating']}★</b><br/>{item['text']}", styles["bad"]))

    story.append(Paragraph("5. Plan de acción 30 días", styles["h2"]))
    actions = [
        "Responder en menos de 24 h todas las reseñas de 1-3★ con disculpa concreta y compensación privada.",
        "Revisar esperas y errores de pedido en los días con peor rating.",
        "Revisar raciones percibidas y añadir al menos dos opciones veganas/vegetarianas.",
        "Campaña de fotos de clientes con QR en mesa y objetivo de 4,70★.",
    ]
    for index, action in enumerate(actions, 1):
        story.append(Paragraph(f"{index}. {action}", styles["body"]))

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Informe {client.name} {period}",
        author="Informes Google Maps",
    )
    doc.build(story)
    return path
