import re
import unicodedata

from django.db import migrations, models

COUNTRY_ALIASES = {
    "España": ("españa", "espana", "spain"),
    "Perú": ("perú", "peru"),
    "México": ("méxico", "mexico"),
    "Colombia": ("colombia",),
    "Argentina": ("argentina",),
    "Chile": ("chile",),
    "Ecuador": ("ecuador",),
    "Bolivia": ("bolivia",),
    "Uruguay": ("uruguay",),
    "Paraguay": ("paraguay",),
    "Venezuela": ("venezuela",),
    "Costa Rica": ("costa rica",),
    "Guatemala": ("guatemala",),
    "Panamá": ("panamá", "panama"),
    "República Dominicana": ("republica dominicana", "república dominicana"),
    "Portugal": ("portugal",),
    "Estados Unidos": ("estados unidos", "united states", "eeuu"),
}

COUNTRY_TLDS = {
    "es": "España", "pe": "Perú", "mx": "México", "co": "Colombia",
    "ar": "Argentina", "cl": "Chile", "ec": "Ecuador", "bo": "Bolivia",
    "uy": "Uruguay", "py": "Paraguay", "ve": "Venezuela", "cr": "Costa Rica",
    "gt": "Guatemala", "pa": "Panamá", "do": "República Dominicana",
    "pt": "Portugal", "us": "Estados Unidos",
}

ZONE_CANONICAL = {
    "ancon": "Ancón",
    "bocanegra": "Bocanegra",
    "barcelona": "Barcelona",
    "callao": "Callao",
    "chorrillos": "Chorrillos",
    "comas": "Comas",
    "lima": "Lima",
    "miraflores": "Miraflores",
    "san isidro": "San Isidro",
    "surco": "Surco",
}

ZONE_COUNTRY = {
    "ancon": "Perú",
    "bocanegra": "Perú",
    "callao": "Perú",
    "chorrillos": "Perú",
    "comas": "Perú",
    "lima": "Perú",
    "miraflores": "Perú",
    "san isidro": "Perú",
    "surco": "Perú",
    "barcelona": "España",
    "bilbao": "España",
    "madrid": "España",
    "malaga": "España",
    "sevilla": "España",
    "valencia": "España",
}


def _fold(value):
    normalized = unicodedata.normalize("NFKD", value or "").lower()
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip()


def _normalize_country(value):
    text = (value or "").strip()
    folded = _fold(text)
    if not folded or folded in ("sin pais", "sin pais."):
        return "Sin país"
    for name, aliases in COUNTRY_ALIASES.items():
        if folded == _fold(name) or any(folded == _fold(alias) for alias in aliases):
            return name
    return text


def _normalize_zone(value):
    text = (value or "").strip()
    if not text:
        return "Sin zona"
    text = re.sub(r"\s+(mz|lt|urb)\b.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(av|avenida|calle|cra|carrera)\.?\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\d{4,6}$", "", text).strip(" .,-")
    if not text:
        return "Sin zona"
    folded = _fold(text)
    if folded in ZONE_CANONICAL:
        return ZONE_CANONICAL[folded]
    return text.title() if text.islower() or text.isupper() else text


def _normalize_location(country, zone):
    normalized_zone = _normalize_zone(zone)
    normalized_country = _normalize_country(country)
    if normalized_country == "Sin país":
        normalized_country = ZONE_COUNTRY.get(_fold(normalized_zone), normalized_country)
    return normalized_country, normalized_zone


def _infer_location(address, source_url):
    text = (address or "").lower()
    netloc = (source_url or "").lower().split("//")[-1].split("/")[0].split(":")[0]
    country = "Sin país"
    for name, aliases in COUNTRY_ALIASES.items():
        if any(alias in text for alias in aliases):
            country = name
            break
    if country == "Sin país":
        for tld, name in COUNTRY_TLDS.items():
            if netloc.endswith(f".{tld}"):
                country = name
                break

    parts = [re.sub(r"^\d{4,6}[-\s]+", "", part.strip()).strip(" .-") for part in (address or "").split(",")]
    parts = [part for part in parts if part]
    aliases = tuple(alias for values in COUNTRY_ALIASES.values() for alias in values)
    parts = [part for part in parts if not any(alias in part.lower() for alias in aliases)]
    return _normalize_location(country, parts[-1] if parts else "Sin zona")


def backfill_location(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    for client in Client.objects.all():
        inferred_country, inferred_zone = _infer_location(client.address, client.source_url)
        country, zone = _normalize_location(
            client.country or inferred_country,
            client.zone or inferred_zone,
        )
        client.country = country
        client.zone = zone
        client.save(update_fields=["country", "zone"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="country",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="client",
            name="zone",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(backfill_location, migrations.RunPython.noop),
    ]
