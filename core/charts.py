import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analytics import CHART_COLORS

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


def _encode(figure):
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _base(title, height=3.4):
    figure, axes = plt.subplots(figsize=(8.2, height), dpi=130)
    axes.set_title(title, color=CHART_COLORS["text"], fontsize=12, fontweight="bold", pad=12)
    axes.grid(axis="y", color=CHART_COLORS["grid"], alpha=0.7)
    axes.set_axisbelow(True)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    return figure, axes


def _volume_rating(labels, volume, rating, title):
    if not len(labels):
        return ""
    figure, axes = _base(title)
    positions = range(len(labels))
    axes.bar(positions, volume, color=CHART_COLORS["volume"], width=0.58, label="Reseñas")
    axes.set_xticks(list(positions))
    axes.set_xticklabels(labels, rotation=28, ha="right", fontsize=8)
    axes.set_ylabel("Reseñas", color=CHART_COLORS["volume"])
    secondary = axes.twinx()
    secondary.plot(positions, rating, color=CHART_COLORS["rating"], marker="o", linewidth=2.4, label="Rating")
    secondary.set_ylim(1, 5.2)
    secondary.set_ylabel("Rating", color=CHART_COLORS["rating"])
    secondary.spines["top"].set_visible(False)
    figure.tight_layout()
    return _encode(figure)


def monthly(frame):
    table = frame.groupby("mes").agg(resenas=("rating", "size"), rating=("rating", "mean")).reset_index()
    return _volume_rating(table["mes"].tolist(), table["resenas"].tolist(), table["rating"].tolist(), "Evolución mensual: volumen y rating")


def weekly(frame):
    table = frame.groupby("semana_num").agg(resenas=("rating", "size"), rating=("rating", "mean")).reset_index()
    labels = [f"S{int(value)}" for value in table["semana_num"]]
    return _volume_rating(labels, table["resenas"].tolist(), table["rating"].tolist(), "Volumen y rating por semana")


def daily(frame):
    table = frame.groupby("date").agg(resenas=("rating", "size"), rating=("rating", "mean")).reset_index()
    labels = [value.strftime("%d/%m") for value in table["date"]]
    return _volume_rating(labels, table["resenas"].tolist(), table["rating"].tolist(), "Actividad diaria")


def weekday(frame):
    table = (
        frame.groupby(["dia_semana_num", "dia_semana"])
        .agg(resenas=("rating", "size"), rating=("rating", "mean"))
        .reset_index()
        .sort_values("dia_semana_num")
    )
    return _volume_rating(table["dia_semana"].tolist(), table["resenas"].tolist(), table["rating"].tolist(), "Días de la semana con más reseñas")


def distribution(frame):
    if frame.empty:
        return ""
    counts = frame["rating"].value_counts().reindex(range(1, 6), fill_value=0)
    colors = [CHART_COLORS["negative"], "#F97316", CHART_COLORS["neutral"], "#34D399", CHART_COLORS["positive"]]
    figure, axes = _base("Distribución de valoraciones", 3.1)
    bars = axes.bar([f"{star}★" for star in counts.index], counts.values, color=colors, width=0.62)
    axes.bar_label(bars, padding=3, fontsize=9)
    axes.set_ylim(0, max(counts.values) * 1.15 if max(counts.values) else 1)
    figure.tight_layout()
    return _encode(figure)


def response_by_rating(frame):
    if frame.empty:
        return ""
    grouped = frame.groupby("rating")["respondida"].agg(["mean", "size"]).reset_index()
    colors = [CHART_COLORS["negative"], "#F97316", CHART_COLORS["neutral"], "#34D399", CHART_COLORS["positive"]][: len(grouped)]
    figure, axes = _base("Respuesta del propietario por valoración", 3.1)
    values = grouped["mean"].tolist()
    bars = axes.bar([f"{int(star)}★" for star in grouped["rating"]], [value * 100 for value in values], color=colors, width=0.62)
    axes.bar_label(bars, labels=[f"{value * 100:.0f}%" for value in values], padding=3, fontsize=9)
    axes.set_ylim(0, 105)
    axes.set_ylabel("% respondidas")
    figure.tight_layout()
    return _encode(figure)


def cumulative(frame):
    if frame.empty:
        return ""
    ordered = frame.sort_values("date")
    values = list(range(1, len(ordered) + 1))
    figure, axes = _base("Crecimiento acumulado de reseñas", 3.1)
    axes.fill_between(range(len(values)), values, color=CHART_COLORS["volume"], alpha=0.14)
    axes.plot(range(len(values)), values, color=CHART_COLORS["volume"], linewidth=2.3)
    axes.set_ylabel("Reseñas acumuladas")
    axes.set_xlabel("Cronología")
    figure.tight_layout()
    return _encode(figure)
