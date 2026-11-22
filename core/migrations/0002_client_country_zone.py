import re

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
    return country, (parts[-1] if parts else "Sin zona")


def backfill_location(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    for client in Client.objects.all():
        country, zone = _infer_location(client.address, client.source_url)
        if not client.country:
            client.country = country
        if not client.zone:
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
