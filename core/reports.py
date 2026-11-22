import base64
import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils.text import slugify
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import analytics, charts, briefs, insights
from .models import Client, Review

BASE_DIR = Path(__file__).resolve().parents[1]
LOGO = BASE_DIR / "static" / "assets" / "logo.jpg"
BRAND = "INFORMES GOOGLE MAPS"
AUTHOR = "Alex Goyzueta"
WHATSAPP = "+34 624 59 23 98"
WHATSAPP_URL = "https://wa.me/34624592398"
EMAIL = "alexgoyzueta2018@gmail.com"
NAVY = colors.HexColor("#240C48")
BLUE = colors.HexColor("#395B84")
LIGHT_BLUE = colors.HexColor("#EEF2F8")
GRID = colors.HexColor("#D7DEEA")
GOOD = colors.HexColor("#10B981")
BAD = colors.HexColor("#EF4444")
WARN = colors.HexColor("#F59E0B")


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
        "title": ParagraphStyle("TitleEs", parent=base["Title"], fontSize=22, leading=26, textColor=NAVY, spaceAfter=2),
        "subtitle": ParagraphStyle("SubEs", parent=base["Normal"], fontSize=10, leading=14, textColor=BLUE, spaceAfter=8),
        "h2": ParagraphStyle("H2Es", parent=base["Heading2"], fontSize=13, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=5),
        "h3": ParagraphStyle("H3Es", parent=base["Heading3"], fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=4, spaceAfter=5),
        "body": ParagraphStyle("BodyEs", parent=base["BodyText"], fontSize=9, leading=13),
        "small": ParagraphStyle("SmallEs", parent=base["BodyText"], fontSize=7.4, leading=9.4),
        "table_header": ParagraphStyle("TableHeaderEs", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.4, leading=9.4, textColor=colors.white),
        "note": ParagraphStyle("NoteEs", parent=base["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#475569"), backColor=colors.HexColor("#F5F8FC"), borderPadding=5, spaceBefore=3),
        "center": ParagraphStyle("CenterEs", parent=base["BodyText"], alignment=TA_CENTER, fontSize=9, leading=12, textColor=BLUE),
        "good": ParagraphStyle("GoodEs", parent=base["BodyText"], fontSize=9, leading=13, textColor=colors.HexColor("#065F46")),
        "bad": ParagraphStyle("BadEs", parent=base["BodyText"], fontSize=9, leading=13, textColor=colors.HexColor("#991B1B")),
        "white": ParagraphStyle("WhiteEs", parent=base["BodyText"], fontSize=9, leading=12, textColor=colors.white),
    }


def _para(text, style):
    return Paragraph(escape(str(text)), style)


def _decorate(canvas, doc, client, period):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 22 * mm, width, 22 * mm, fill=1, stroke=0)
    if LOGO.exists():
        canvas.drawImage(str(LOGO), 14 * mm, height - 18 * mm, 14 * mm, 14 * mm, preserveAspectRatio=True)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9.5)
    canvas.drawString(32 * mm, height - 10 * mm, BRAND)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(32 * mm, height - 15 * mm, f"{client.name[:62]} · {period[:62]}")
    canvas.setStrokeColor(GRID)
    canvas.line(16 * mm, 15 * mm, width - 16 * mm, 15 * mm)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(16 * mm, 10 * mm, f"WhatsApp {WHATSAPP} · {EMAIL}")
    canvas.drawRightString(width - 16 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _table(records, styles, col_widths=None, max_rows=None):
    if not records:
        return _para("Sin datos para este periodo.", styles["body"])
    rows = records[:max_rows] if max_rows else records
    header = [_para(key, styles["table_header"]) for key in rows[0].keys()]
    body = [[_para(value, styles["small"]) for value in row.values()] for row in rows]
    table = Table([header] + body, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    table.setStyle(TableStyle(style))
    return table


def _profile_table(client):
    rows = [
        ["Local", client.name],
        ["Categoría", client.category or "Google Business Profile"],
        ["Dirección", client.address or "No disponible"],
        ["Teléfono", client.phone or "No disponible"],
        ["Google", f"{client.rating or 0:.2f}★ · {client.review_total} reseñas · {client.photo_total} fotos · {client.customer_photos} de clientes"],
        ["Ficha", client.source_url],
        ["Actualizado", client.last_scraped.strftime("%d/%m/%Y %H:%M") if client.last_scraped else "Sin fecha"],
    ]
    table = Table([[_para(key, get_styles()["small"]), _para(value, get_styles()["small"])] for key, value in rows], colWidths=[30 * mm, 146 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def get_styles():
    return _styles()


def _kpi_table(kpis, score):
    rows = [
        ["Rating medio", f"{kpis['average']:.2f}★", "Índice reputación", f"{score['score']:.0f} · {score['label']}"],
        ["Rating ajustado", f"{score.get('weighted_rating', kpis['average']):.2f}★", "Confianza por volumen", f"{score.get('confidence', 0):.0f}%"],
        ["Satisfacción", f"{kpis['satisfaction']:.1f}%", "Reseñas analizadas", kpis["total"]],
        ["Excelencia 5★", f"{kpis['five_rate']:.1f}%", "Positivas 4-5★", f"{kpis['positive_rate']:.1f}%"],
        ["Incidencias 1-2★", kpis["negative"], "Respuesta a 1-2★", f"{kpis['negative_response_rate']:.1f}%"],
        ["Saldo neto", f"+{kpis['balance']:.1f}", "Respuestas", f"{kpis['response_rate']:.1f}%"],
    ]
    styles = _styles()
    data = [[_para(left, styles["small"]), _para(right, styles["small"]), _para(left2, styles["small"]), _para(right2, styles["small"])] for left, right, left2, right2 in rows]
    table = Table(data, colWidths=[35 * mm, 40 * mm, 42 * mm, 59 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _status_badge(score, styles):
    color = colors.HexColor(score.get("color", "#64748B"))
    table = Table([[
        _para("ESTADO GENERAL", styles["white"]),
        _para(f"{score['score']:.0f}/100 · {score['label']}", styles["white"]),
    ]], colWidths=[45 * mm, 131 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _benchmark_table(client):
    peers = Client.objects.exclude(pk=client.pk)
    if client.category:
        by_category = peers.filter(category=client.category)
        if by_category.exists():
            peers = by_category
            label = f"Compañeros de {client.category}"
        else:
            label = "Cartera guardada"
    else:
        label = "Cartera guardada"
    result = analytics.benchmark(client, peers)
    if result["label"] != "Sin comparables":
        result["label"] = label
    return result


def _methodology_table(client, frame, period):
    styles = _styles()
    rows = [
        {"Tema": "Fuente", "Detalle": "Google Maps · ficha pública del local"},
        {"Tema": "URL analizada", "Detalle": client.source_url},
        {"Tema": "Periodo", "Detalle": period},
        {"Tema": "Muestra", "Detalle": f"{len(frame)} reseñas con fecha y valoración válidas"},
        {"Tema": "Última extracción", "Detalle": client.last_scraped.strftime("%d/%m/%Y %H:%M") if client.last_scraped else "Sin fecha"},
        {"Tema": "Regla de cierre", "Detalle": f"Mes incompleto excluido · último mes cerrado {analytics.month_label(analytics.last_complete_month())}"},
        {"Tema": "Temas", "Detalle": "Clasificación por palabras clave sobre el texto literal de las reseñas"},
        {"Tema": "Benchmark", "Detalle": "Promedio de la cartera guardada en este programa, no de todo Google Maps"},
        {"Tema": "Limitación", "Detalle": "Reseñas sin fecha válida no entran en series temporales; el texto se resume sin alterar su sentido"},
    ]
    return _table(rows, styles, col_widths=[32 * mm, 144 * mm])


def _recommendation_table(actions, styles):
    rows = [
        [_para(action.get("priority", ""), styles["small"]),
         _para(action.get("title", ""), styles["small"]),
         _para(action.get("detail", ""), styles["small"]),
         _para(action.get("owner", "Responsable"), styles["small"]),
         _para(action.get("deadline", "Por definir"), styles["small"]),
         _para(f"{action.get('impact', 'Media')} / {action.get('effort', 'Medio')}", styles["small"]),
         _para(action.get("kpi", ""), styles["small"])]
        for action in actions
    ]
    data = [[
        _para("Prioridad", styles["table_header"]),
        _para("Acción", styles["table_header"]),
        _para("Cómo hacerlo", styles["table_header"]),
        _para("Responsable", styles["table_header"]),
        _para("Plazo", styles["table_header"]),
        _para("Impacto / esfuerzo", styles["table_header"]),
        _para("KPI objetivo", styles["table_header"]),
    ]] + rows
    table = Table(data, colWidths=[14 * mm, 27 * mm, 52 * mm, 20 * mm, 16 * mm, 23 * mm, 24 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _strategy_table(strategies, styles):
    rows = [
        [_para(item.get("phase", ""), styles["small"]),
         _para(item.get("objective", ""), styles["small"]),
         _para(item.get("move", ""), styles["small"]),
         _para(item.get("kpi", ""), styles["small"])]
        for item in strategies
    ]
    data = [[
        _para("Fase", styles["table_header"]),
        _para("Objetivo", styles["table_header"]),
        _para("Movimiento recomendado", styles["table_header"]),
        _para("Métrica", styles["table_header"]),
    ]] + rows
    table = Table(data, colWidths=[28 * mm, 48 * mm, 66 * mm, 34 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _growth_table(growth, styles):
    rows = []
    for item in growth:
        tactics = "\n".join(f"• {escape(tactic)}" for tactic in item.get("tactics", []))
        rows.append([
            _para(escape(item.get("title", "")), styles["small"]),
            _para(escape(item.get("objective", "")), styles["small"]),
            _para(tactics, styles["small"]),
            _para(escape(item.get("kpi", "")), styles["small"]),
            _para(f"{escape(item.get('owner', ''))}<br/>{escape(item.get('deadline', ''))}", styles["small"]),
        ])
    data = [[
        _para("Palanca", styles["table_header"]),
        _para("Objetivo", styles["table_header"]),
        _para("Tácticas", styles["table_header"]),
        _para("Métrica", styles["table_header"]),
        _para("Responsable", styles["table_header"]),
    ]] + rows
    table = Table(data, colWidths=[26 * mm, 36 * mm, 68 * mm, 30 * mm, 26 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _glossary_table(styles):
    rows = [
        {"KPI": "Rating medio", "Qué significa": "Nota de 1 a 5 estrellas que ve el cliente en Google", "Por qué importa": "Es la primera impresión del negocio"},
        {"KPI": "Satisfacción", "Qué significa": "El rating convertido a porcentaje; 4,5★ son 90%", "Por qué importa": "Permite comparar meses aunque cambie el volumen"},
        {"KPI": "Excelencia 5★", "Qué significa": "Porcentaje de clientes que dan la máxima nota", "Por qué importa": "Mide clientes encantados, no solo conformes"},
        {"KPI": "Saldo neto", "Qué significa": "Positivas (4-5★) menos incidencias (1-2★)", "Por qué importa": "Resume si la reputación suma o pierde confianza"},
        {"KPI": "Respuesta a 1-2★", "Qué significa": "Porcentaje de opiniones críticas contestadas", "Por qué importa": "Es la acción más rápida para recuperar confianza"},
        {"KPI": "Ritmo de reseñas", "Qué significa": "Reseñas nuevas por día en los últimos 30 días", "Por qué importa": "Sin entradas nuevas, la ficha pierde frescura"},
    ]
    return _table(rows, styles, col_widths=[34 * mm, 80 * mm, 62 * mm])


def _talk_script(diagnosis, kpis, styles):
    actions = diagnosis.get("actions", [])
    strategies = diagnosis.get("strategies", [])
    strengths = diagnosis.get("strengths", [])
    risks = diagnosis.get("risks", [])
    return [
        _para("Paso 1 · Lectura del periodo", styles["h3"]),
        _para(diagnosis["headline"], styles["body"]),
        _para("Paso 2 · Evidencia", styles["h3"]),
        _para(strengths[0] if strengths else "Aún no hay evidencia suficiente en los comentarios.", styles["body"]),
        _para(risks[0] if risks else f"La respuesta a opiniones críticas es del {kpis['negative_response_rate']:.1f}%.", styles["body"]),
        _para("Paso 3 · Decisión", styles["h3"]),
        _para(strategies[0]["move"] if strategies else (actions[0]["detail"] if actions else "Mantener el nivel actual y revisar el informe del próximo mes."), styles["body"]),
        _para("Paso 4 · Cómo lo medimos", styles["h3"]),
        _para(strategies[0]["kpi"] if strategies else "Revisar el informe del próximo mes.", styles["body"]),
    ]


def _image(value, width=440):
    if not value:
        return None
    data = base64.b64decode(value)
    reader = ImageReader(io.BytesIO(data))
    pixel_width, pixel_height = reader.getSize()
    height = width * pixel_height / pixel_width
    return Image(io.BytesIO(data), width=width, height=height)


def _chart_block(title, value, note, styles):
    items = [_para(title, styles["h3"])]
    image = _image(value)
    if image:
        items.append(image)
    items.append(_para(note, styles["note"]))
    return KeepTogether(items)


def _scope(frame, month=None, year=None):
    cutoff = analytics.last_complete_month()
    note = f" · Datos hasta {analytics.month_label(cutoff)}"
    if month:
        subset = frame[frame["mes"] == month]
        return subset, subset, "mensual", analytics.month_label(month), f"Informe mensual · {analytics.month_label(month)}"
    if year:
        subset = frame[frame["anio"] == year]
        return subset, subset, "anual", f"Año {year}{note}", f"Informe anual · {year}"
    return frame, frame, "general", "Histórico completo" + note, "Informe general de reputación"


def export_brief(client, frame, month=None, year=None, filename=None):
    data = briefs.email_brief(client, frame, month, year)
    styles = _styles()
    folder = _client_folder(client) / "fichas"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (filename or f"ficha_envio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

    story = [
        Spacer(1, 4),
        _para("Ficha para enviar por correo", styles["title"]),
        _para(f"{client.name} · {data['period']} · Preparada por {briefs.AUTHOR}", styles["subtitle"]),
        _profile_table(client),
        Spacer(1, 8),
        _para("Asunto sugerido", styles["h2"]),
        _para(data["subject"], styles["note"]),
        Spacer(1, 6),
        _para("Comentario para el archivo adjunto", styles["h2"]),
        _para(data["comment"], styles["note"]),
        Spacer(1, 6),
        _para("Texto listo para copiar en el correo", styles["h2"]),
    ]
    for line in data["body"].split("\n"):
        if line:
            story.append(_para(line, styles["body"]))
        else:
            story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))
    story.append(_para("Archivos que acompañan esta ficha", styles["h2"]))
    story.append(_table([
        {"Archivo": "00_FICHA_DE_ENVIO.pdf", "Contenido": "Este resumen con el texto sugerido"},
        {"Archivo": "01_informe_general.pdf", "Contenido": "Historial completo hasta el último mes cerrado"},
        {"Archivo": "02_anio_*.pdf", "Contenido": "Informe por cada año"},
        {"Archivo": "03_mes_*.pdf", "Contenido": "Informe mensual de cada mes"},
    ], styles, col_widths=[55 * mm, 121 * mm]))
    story.append(Spacer(1, 10))
    cta = Table([[
        _para("Siguiente paso", styles["white"]),
        _para(f"Revisar el informe con el cliente y confirmar el plan de mejora. {briefs.WHATSAPP_URL} · {briefs.EMAIL}", styles["white"]),
    ]], colWidths=[35 * mm, 141 * mm])
    cta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cta)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=28 * mm,
        bottomMargin=20 * mm,
        title=f"Ficha de envío · {client.name}",
        author=f"{briefs.AUTHOR} · {BRAND}",
    )
    doc.build(story, onFirstPage=lambda canvas, document: _decorate(canvas, document, client, data["period"]), onLaterPages=lambda canvas, document: _decorate(canvas, document, client, data["period"]))
    return path


def export_pdf(client, frame, month=None, year=None, filename=None):
    subset, chart_source, kind, period, title = _scope(frame, month, year)
    styles = _styles()
    kpis = analytics.reputation_kpis(subset)
    score = insights.scorecard(kpis)
    diagnosis = insights.client_diagnosis(subset, client)
    notes = insights.chart_notes(kind, chart_source, subset, kpis)
    themes = analytics.themes(subset)
    comparison = analytics.period_comparison(frame, month, year)
    photos = analytics.photo_audit(client)
    benchmark = _benchmark_table(client)

    root = _client_folder(client)
    subdir = {"mensual": "pdf_mensuales", "anual": "pdf_anuales", "general": "general"}[kind]
    folder = root / subdir
    folder.mkdir(parents=True, exist_ok=True)
    if not filename:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"informe_{kind}_{stamp}.pdf"
    path = folder / filename

    story = [
        Spacer(1, 8),
        _para(BRAND, styles["subtitle"]),
        _para(title, styles["title"]),
        _para(f"{client.name} · {period}", styles["subtitle"]),
        _status_badge(score, styles),
        Spacer(1, 8),
        _profile_table(client),
        Spacer(1, 8),
        _para("Lectura rápida", styles["h2"]),
        _para(diagnosis["headline"], styles["body"]),
        Spacer(1, 4),
        _kpi_table(kpis, score),
        Spacer(1, 8),
        _para(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} · Fuente: Google Maps · Preparado por {AUTHOR}", styles["small"]),
        PageBreak(),
        _para("1. Resumen ejecutivo", styles["h2"]),
        _para("Qué pasó", styles["h3"]),
    ]
    for item in _talk_script(diagnosis, kpis, styles):
        story.append(item)
    story.append(Spacer(1, 6))
    story.append(_para(f"Comparativa · {comparison['label']}", styles["h3"]))
    story.append(_table(comparison["rows"], styles, col_widths=[42 * mm, 38 * mm, 42 * mm, 54 * mm]))
    if not comparison["has_previous"]:
        story.append(_para("No hay periodo anterior con datos; la comparativa se activará al acumular otro mes o año cerrado.", styles["note"]))

    story.append(Spacer(1, 8))
    story.append(_para("2. Fortalezas y prioridades de mejora", styles["h2"]))
    story.append(_para("Lo que ya está funcionando", styles["h3"]))
    for item in diagnosis["strengths"][:4]:
        story.append(_para(item, styles["good"]))
    story.append(_para("Prioridades de mejora", styles["h3"]))
    for item in diagnosis["risks"][:4]:
        story.append(_para(item, styles["bad"]))
    story.append(Spacer(1, 4))
    story.append(_para("Temas que aparecen en las reseñas", styles["h3"]))
    theme_rows = []
    for item in themes["good"]:
        theme_rows.append({"Tipo": "Fortaleza", "Tema": item["label"], "Veces": str(item["count"]), "Acción sugerida": "Reforzar en respuestas y contenido visual."})
    for item in themes["bad"]:
        theme_rows.append({"Tipo": "Incidencia", "Tema": item["label"], "Veces": str(item["count"]), "Acción sugerida": item["action"].capitalize() + "."})
    story.append(_table(theme_rows, styles, col_widths=[24 * mm, 52 * mm, 16 * mm, 84 * mm]))
    story.append(_para(f"Fortalezas: {themes['good_text']}", styles["good"]))
    story.append(_para(f"Incidencias: {themes['bad_text']}", styles["bad"]))

    story.append(Spacer(1, 8))
    story.append(_para("3. Fotos y benchmark", styles["h2"]))
    story.append(_para("Prueba social en la ficha", styles["h3"]))
    story.append(_table(photos["rows"], styles, col_widths=[40 * mm, 24 * mm, 112 * mm]))
    story.append(Spacer(1, 5))
    story.append(_para(f"Comparativa · {benchmark['label']}", styles["h3"]))
    story.append(_table(benchmark["rows"], styles, col_widths=[50 * mm, 36 * mm, 46 * mm, 44 * mm]))
    if not benchmark["rows"]:
        story.append(_para("Aún no hay otros clientes guardados para comparar. Al importar más locales aparecerá el promedio de la cartera.", styles["note"]))
    else:
        story.append(_para("El benchmark usa solo la cartera de este programa; no representa a todos los competidores de Google Maps.", styles["note"]))

    story.append(Spacer(1, 8))
    story.append(_para("4. Gráficos con lectura", styles["h2"]))
    if kind in ("general", "anual"):
        story.append(_chart_block("Evolución mensual", charts.monthly(chart_source), notes["monthly"], styles))
        story.append(_chart_block("Días de la semana", charts.weekday(chart_source), notes["weekday"], styles))
    story.append(_chart_block("Distribución de valoraciones", charts.distribution(subset), notes["distribution"], styles))
    story.append(_chart_block("Satisfechos vs incidencias", charts.sentiment(subset), notes["sentiment"], styles))
    story.append(_chart_block("Respuesta del propietario", charts.response_by_rating(chart_source), notes["response"], styles))
    if kind == "mensual":
        story.append(_chart_block("Semanas del mes", charts.weekly(subset), notes["weekly"], styles))
        story.append(_chart_block("Actividad diaria", charts.daily(subset), notes["daily"], styles))

    story.append(PageBreak())
    story.append(_para("5. Análisis temporal", styles["h2"]))
    if kind == "mensual":
        story.append(_para("Resumen semanal", styles["h3"]))
        story.append(_table(analytics.records(analytics.weekly_table(subset)), styles))
        story.append(Spacer(1, 6))
        story.append(_para("Detalle diario", styles["h3"]))
        story.append(_table(analytics.records(analytics.daily_table(subset)), styles, max_rows=30))
    else:
        story.append(_para("Resumen mensual", styles["h3"]))
        story.append(_table(analytics.records(analytics.monthly_table(chart_source)), styles, max_rows=24))
        story.append(Spacer(1, 6))
        story.append(_para("Comparativa anual", styles["h3"]))
        story.append(_table(analytics.records(analytics.yearly_table(frame)), styles))

    story.append(Spacer(1, 8))
    story.append(_para("6. Comentarios verificables", styles["h2"]))
    for item in analytics.verbatims(subset, True):
        story.append(_para(f"{item['date']} · {item['author']} · {item['rating']}★", styles["h3"]))
        story.append(_para(item["text"], styles["good"]))
    story.append(_para("Reseñas críticas a atender", styles["h3"]))
    for item in analytics.verbatims(subset, False):
        story.append(_para(f"{item['date']} · {item['author']} · {item['rating']}★", styles["h3"]))
        story.append(_para(item["text"], styles["bad"]))

    story.append(Spacer(1, 8))
    story.append(_para("7. Estrategia y plan de acción", styles["h2"]))
    story.append(_para("La estrategia ordena el esfuerzo en tres fases; el plan baja cada fase a tareas con responsable y plazo.", styles["body"]))
    story.append(_strategy_table(diagnosis.get("strategies", []), styles))
    story.append(Spacer(1, 8))
    story.append(_para("Motor de crecimiento · reseñas y captación", styles["h3"]))
    story.append(_growth_table(diagnosis.get("growth", []), styles))
    story.append(Spacer(1, 6))
    story.append(_recommendation_table(diagnosis["actions"], styles))

    story.append(Spacer(1, 8))
    story.append(_para("8. Trazabilidad y anexos", styles["h2"]))
    story.append(_methodology_table(client, frame, period))
    story.append(Spacer(1, 6))
    story.append(_para("Glosario de KPIs", styles["h3"]))
    story.append(_glossary_table(styles))

    story.append(Spacer(1, 10))
    story.append(_para("9. Próximo paso", styles["h2"]))
    cta = Table([[
        _para("Este informe se actualiza, no se rehace", styles["white"]),
        _para(f"La URL y el histórico quedan guardados. Siguiente paso: {WHATSAPP_URL} · {EMAIL}", styles["white"]),
    ]], colWidths=[70 * mm, 106 * mm])
    cta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cta)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=28 * mm,
        bottomMargin=20 * mm,
        title=f"{title} · {client.name}",
        author=f"{AUTHOR} · {BRAND}",
    )
    doc.build(story, onFirstPage=lambda canvas, document: _decorate(canvas, document, client, period), onLaterPages=lambda canvas, document: _decorate(canvas, document, client, period))
    return path


def export_pdf_package(client, frame):
    root = _client_folder(client)
    files = []
    files.append(export_brief(client, frame, filename="00_FICHA_DE_ENVIO.pdf"))
    files.append(export_pdf(client, frame, filename="01_informe_general.pdf"))
    for year in sorted(frame["anio"].unique().tolist(), reverse=True) if not frame.empty else []:
        files.append(export_pdf(client, frame, year=int(year), filename=f"02_anio_{int(year)}.pdf"))
    for month in sorted(frame["mes"].unique().tolist()) if not frame.empty else []:
        files.append(export_pdf(client, frame, month=month, filename=f"03_mes_{month}.pdf"))
    zip_path = root / f"PAQUETE_PDF_{slugify(client.name)}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "LEEME.txt",
            f"{BRAND}\n{AUTHOR}\nWhatsApp: {WHATSAPP}\nEmail: {EMAIL}\nCliente: {client.name}\nURL: {client.source_url}\nGenerado: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n",
        )
        for path in files:
            archive.write(path, str(path.relative_to(root)).replace("\\", "/"))
    return zip_path, files
