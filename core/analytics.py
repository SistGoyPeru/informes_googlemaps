import calendar
from datetime import date, datetime

import pandas as pd

CHART_COLORS = {
    "volume": "#2563EB",
    "rating": "#1E3A8A",
    "positive": "#10B981",
    "negative": "#EF4444",
    "neutral": "#F59E0B",
    "accent": "#0EA5E9",
    "violet": "#7C3AED",
    "grid": "#E2E8F0",
    "text": "#0F172A",
}

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEK_RANGES = {1: "1-7", 2: "8-14", 3: "15-21", 4: "22-28", 5: "29-31"}
MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

THEMES_POSITIVE = [
    ("Comida sabrosa y de calidad", r"comida|rica|rico|sabor|buen|excelente|pollo|hamburguesa|calidad|buena"),
    ("Buena relación calidad-precio", r"precio|barat|económ|vale la pena|calidad precio"),
    ("Atención cercana y amable", r"atención|amable|trato|simpático|servicio|cercan"),
    ("Local limpio y bien decorado", r"limpi|decoración|ambiente|sitio|local"),
    ("Servicio rápido", r"rápido|rapidez|enseguida"),
]

THEMES_NEGATIVE = [
    ("Esperas y lentitud en el servicio", r"lent|esper|minut|tardan|tardo|demora|media hora"),
    ("Trato poco amable o sin saludo", r"educación|amable|saludo|hola|adiós|trato|malas contestaciones|corto"),
    ("Cantidad insuficiente o precio alto", r"cantidad|poca|pequeñ|caro|precio|patatas|alitas|surtidor"),
    ("Errores en el pedido", r"equivoc|error|pedido|olvid|falta|me pone"),
    ("Higiene o calidad inconsistente", r"sucio|asqueros|aceite|frí|congelad|calidad|pesim"),
    ("Sin opciones veganas o vegetarianas", r"vegan|vegetarian"),
]

THEME_ACTIONS = {
    "Esperas y lentitud en el servicio": "revisar tiempos de cocina/sala y reforzar personal en horas punta",
    "Trato poco amable o sin saludo": "establecer saludo obligatorio y protocolo de trato al cliente",
    "Cantidad insuficiente o precio alto": "revisar raciones y comunicar claramente el contenido de cada menú",
    "Errores en el pedido": "aplicar checklist de salida de cocina antes de entregar cada pedido",
    "Higiene o calidad inconsistente": "reforzar limpieza y control de temperatura/cocción en cada turno",
    "Sin opciones veganas o vegetarianas": "incorporar al menos dos opciones veganas/vegetarianas a la carta",
}


def month_label(month):
    try:
        year, number = month.split("-")
        return f"{MONTH_NAMES[int(number)]} {year}"
    except (ValueError, KeyError, AttributeError):
        return str(month)


def last_complete_month(today=None):
    today = today or date.today()
    year, month = today.year, today.month
    if today.day < calendar.monthrange(year, month)[1]:
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return f"{year:04d}-{month:02d}"


def complete_months(frame, today=None):
    if frame.empty:
        return frame
    cutoff = last_complete_month(today)
    return frame[frame["mes"] <= cutoff].copy()


def report_frame(reviews, today=None):
    return complete_months(enrich(to_frame(reviews)), today)


def to_frame(reviews):
    fields = ["review_id", "author", "rating", "date", "text", "owner_response"]
    if hasattr(reviews, "values"):
        rows = list(reviews.values(*fields))
    else:
        rows = [{field: getattr(row, field, None) for field in fields} for row in reviews]
    frame = pd.DataFrame(rows, columns=fields)
    frame["text"] = frame["text"].fillna("")
    frame["owner_response"] = frame["owner_response"].fillna("")
    return frame


def enrich(frame):
    source = frame.copy()
    source["rating"] = pd.to_numeric(source["rating"], errors="coerce")
    source["date"] = pd.to_datetime(source["date"], errors="coerce")
    source = source.dropna(subset=["rating", "date"])
    source = source[source["rating"].between(1, 5)]
    if source.empty:
        return source
    source["mes"] = source["date"].dt.to_period("M").astype(str)
    source["anio"] = source["date"].dt.year.astype(int)
    source["dia"] = source["date"].dt.day.astype(int)
    source["semana_num"] = ((source["dia"] - 1) // 7 + 1).astype(int)
    source["semana"] = source["semana_num"].map(lambda n: f"Semana {n} ({WEEK_RANGES.get(n, '29-31')})")
    source["dia_semana_num"] = source["date"].dt.dayofweek.astype(int)
    source["dia_semana"] = source["dia_semana_num"].map(lambda n: DAY_NAMES[n])
    source["respondida"] = source["owner_response"].astype(str).str.strip() != ""
    return source


def reputation_kpis(source):
    if source.empty:
        return {key: 0 for key in [
            "total", "average", "satisfaction", "five", "five_rate", "positive",
            "positive_rate", "negative", "negative_rate", "balance", "responses",
            "response_rate", "negative_response_rate", "with_text",
        ]}
    ratings = source["rating"]
    total = len(source)
    positive = int((ratings >= 4).sum())
    negative = int((ratings <= 2).sum())
    five = int((ratings == 5).sum())
    average = float(ratings.mean())
    responses = int(source["respondida"].sum())
    negative_subset = source[ratings <= 2]
    return {
        "total": total,
        "average": average,
        "satisfaction": average / 5 * 100,
        "five": five,
        "five_rate": five / total * 100,
        "positive": positive,
        "positive_rate": positive / total * 100,
        "negative": negative,
        "negative_rate": negative / total * 100,
        "balance": (positive - negative) / total * 100,
        "responses": responses,
        "response_rate": responses / total * 100,
        "negative_response_rate": float(negative_subset["respondida"].mean() * 100) if negative else 0.0,
        "with_text": int((source["text"].astype(str).str.strip() != "").sum()),
    }


def _agg(frame):
    return {
        "Reseñas": ("rating", "size"),
        "Rating": ("rating", "mean"),
        "Positivas": ("rating", lambda values: int((values >= 4).sum())),
        "Incidencias": ("rating", lambda values: int((values <= 2).sum())),
        "Respuestas": ("respondida", "sum"),
        "5★": ("rating", lambda values: int((values == 5).sum())),
    }


def _finish(table):
    table["Rating"] = table["Rating"].round(2)
    table["% resp."] = (table["Respuestas"] / table["Reseñas"] * 100).round(1)
    table["% 5★"] = (table["5★"] / table["Reseñas"] * 100).round(1)
    return table.drop(columns=["5★"])


def monthly_table(frame):
    if frame.empty:
        return pd.DataFrame(columns=["Mes", "Reseñas", "Rating", "Positivas", "Incidencias", "Respuestas", "% resp.", "% 5★"])
    table = frame.groupby("mes", as_index=False).agg(**_agg(frame)).rename(columns={"mes": "Mes"}).sort_values("Mes")
    return _finish(table)


def yearly_table(frame):
    if frame.empty:
        return pd.DataFrame(columns=["Año", "Meses", "Reseñas", "Rating", "Positivas", "Incidencias", "Respuestas", "% resp.", "% 5★"])
    table = frame.groupby("anio", as_index=False).agg(**_agg(frame))
    months = frame.groupby("anio")["mes"].nunique().rename("Meses").reset_index()
    table = table.merge(months, on="anio").rename(columns={"anio": "Año"}).sort_values("Año")
    table = _finish(table)
    return table[["Año", "Meses", "Reseñas", "Rating", "Positivas", "Incidencias", "Respuestas", "% resp.", "% 5★"]]


def weekly_table(frame):
    columns = ["Semana", "Rango", "Reseñas", "Rating", "Positivas", "Incidencias", "Respuestas", "% resp.", "% 5★"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    table = frame.groupby(["semana_num", "semana"], as_index=False).agg(**_agg(frame)).sort_values("semana_num")
    table = _finish(table).rename(columns={"semana_num": "Semana", "semana": "Rango"})
    return table[columns]


def daily_table(frame):
    columns = ["Fecha", "Día", "Reseñas", "Rating", "Positivas", "Incidencias", "Respuestas", "% resp.", "% 5★"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame = frame.copy()
    frame["Fecha"] = frame["date"].dt.strftime("%d/%m/%Y")
    table = frame.groupby(["date", "Fecha", "dia_semana"], as_index=False).agg(**_agg(frame)).sort_values("date")
    table = _finish(table).rename(columns={"dia_semana": "Día"})
    return table[columns]


def week_options(frame, month):
    subset = frame[frame["mes"] == month] if not frame.empty else frame
    numbers = sorted(subset["semana_num"].unique()) if not subset.empty else []
    return [{"number": int(number), "label": f"Semana {number} ({WEEK_RANGES.get(number, '29-31')})"} for number in numbers]


def day_options(frame, month, week=None):
    subset = frame[frame["mes"] == month] if not frame.empty else frame
    if week and not subset.empty:
        subset = subset[subset["semana_num"] == week]
    if subset.empty:
        return []
    dates = sorted(subset["date"].unique())
    return [
        {"value": value.strftime("%Y-%m-%d"), "label": value.strftime("%d/%m/%Y")}
        for value in dates
    ]


def _categorized(frame, positive):
    selected = frame[frame["rating"] >= 4] if positive else frame[frame["rating"] <= 2]
    if selected.empty:
        return []
    texts = selected["text"].astype(str).str.lower()
    config = THEMES_POSITIVE if positive else THEMES_NEGATIVE
    results = []
    for label, pattern in config:
        count = int(texts.str.contains(pattern, case=False, regex=True, na=False).sum())
        if count:
            results.append({"label": label, "count": count, "action": THEME_ACTIONS.get(label, "revisar este punto")})
    return sorted(results, key=lambda item: (-item["count"], item["label"]))[:4]


def themes(frame):
    good = _categorized(frame, True)
    bad = _categorized(frame, False)
    return {
        "good": good,
        "bad": bad,
        "good_text": ", ".join(f"{item['label']} ({item['count']})" for item in good) or "sin comentarios suficientes",
        "bad_text": ", ".join(f"{item['label']} ({item['count']})" for item in bad) or "sin incidencias textuales destacables",
        "strength": f"Al cliente le gusta especialmente: {good[0]['label'].lower()}." if good else "No aparece un motivo claro en los comentarios de este periodo.",
        "correction": (
            f"Hay que corregir: {', '.join(item['label'].lower() for item in bad[:2])} → "
            + "; ".join(item["action"] for item in bad[:2]) + "."
        ) if bad else "No hay incidencias textuales destacables; mantener el nivel actual.",
    }


def verbatims(frame, positive, limit=4):
    subset = frame[frame["rating"] >= 4] if positive else frame[frame["rating"] <= 2]
    subset = subset[subset["text"].astype(str).str.strip() != ""].sort_values("date")
    rows = []
    for _, row in subset.head(limit).iterrows():
        rows.append({
            "date": row["date"].strftime("%d/%m/%Y") if pd.notna(row["date"]) else "fecha s/d",
            "author": row["author"] or "Cliente",
            "rating": int(row["rating"]),
            "text": str(row["text"])[:260],
        })
    return rows


def records(table):
    table = table.copy()
    for column in table.columns:
        if pd.api.types.is_float_dtype(table[column]):
            table[column] = table[column].round(2)
    return table.to_dict("records")


def parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce")
    return parsed.date() if pd.notna(parsed) else None
