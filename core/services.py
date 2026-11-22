import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from django.utils import timezone
from django.utils.text import slugify

from scraper import maps_scraper

from .analytics import parse_date
from .models import Client, Review

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

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


def _clean_zone_part(part):
    return re.sub(r"^\d{4,6}[-\s]+", "", part.strip()).strip(" .-")


def infer_location(address="", source_url=""):
    text = (address or "").lower()
    netloc = urlparse(source_url or "").netloc.lower().split(":")[0]
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

    parts = [_clean_zone_part(part) for part in (address or "").split(",")]
    parts = [part for part in parts if part]
    country_aliases = tuple(alias for aliases in COUNTRY_ALIASES.values() for alias in aliases)
    parts = [part for part in parts if not any(alias in part.lower() for alias in country_aliases)]
    zone = parts[-1] if parts else "Sin zona"
    return country, zone


def _is_google_short(url):
    host = urlparse(url or "").netloc.lower()
    return host == "goo.gl" or host.endswith(".goo.gl")


def resolve_maps_url(url):
    if not _is_google_short(url):
        return url
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=20) as response:
            return response.geturl() or url
    except (URLError, OSError):
        return url


def normalize_url(value):
    url = (value or "").strip()
    if not url:
        raise ValueError("Pega una URL de Google Maps.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    maps_place = "google." in host and "maps" in path
    maps_short = _is_google_short(url)
    if not maps_place and not maps_short:
        raise ValueError("La URL debe ser de Google Maps.")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("hl", "es")
    return urlunparse(parsed._replace(query=urlencode(query)))


def scrape_client(url):
    url = normalize_url(resolve_maps_url(url))
    place = maps_scraper.scrape_basic(url, headless=True)
    reviews = maps_scraper.scrape_reviews(url, headless=False, wait_seconds=180)
    return url, place, reviews


def save_snapshot(client, place, reviews):
    folder = DATA_DIR / "clients" / slugify(client.place_id or client.name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "place.json").write_text(json.dumps(place, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = maps_scraper.REVIEW_FIELDS
    with (folder / "reviews.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reviews)
    summary = {
        "name": client.name,
        "place_id": client.place_id,
        "rating": client.rating,
        "review_total": client.review_total,
        "reviews_exported": len(reviews),
        "rating_counts": client.rating_counts,
        "photo_total": client.photo_total,
        "owner_photos": client.owner_photos,
        "customer_photos": client.customer_photos,
        "address": client.address,
        "country": client.country,
        "zone": client.zone,
        "phone": client.phone,
        "hours": client.hours,
        "source_url": client.source_url,
    }
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_url": client.source_url,
        "summary": summary,
        "place": place,
        "reviews": reviews,
    }
    (folder / "dashboard.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "place.json").write_text(json.dumps(place, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "reviews.csv").write_text((folder / "reviews.csv").read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    (DATA_DIR / "dashboard.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (DATA_DIR / "resumen.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["campo", "valor"])
        for key, value in summary.items():
            writer.writerow([key, json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value])
    return folder


def sync_client(url, country="", zone=""):
    url, place, reviews = scrape_client(url)
    place_id = place.get("place_id") or maps_scraper.fallback_key(url)
    defaults = {
        "name": place.get("name") or "Cliente Google Maps",
        "source_url": url,
        "category": place.get("category", ""),
        "rating": place.get("rating"),
        "review_total": int(place.get("review_total") or len(reviews)),
        "photo_total": int(place.get("photo_total") or 0),
        "owner_photos": int(place.get("owner_photos") or 0),
        "customer_photos": int(place.get("customer_photos") or 0),
        "address": place.get("address", ""),
        "country": country or "",
        "zone": zone or "",
        "phone": place.get("phone", ""),
        "hours": place.get("hours", ""),
        "rating_counts": place.get("rating_counts") or {},
        "photos": place.get("photos") or [],
        "login_required": bool(place.get("login_required")),
        "last_scraped": timezone.now(),
    }
    existing = Client.objects.filter(place_id=place_id).first()
    inferred_country, inferred_zone = infer_location(defaults["address"], url)
    defaults["country"] = country or (existing.country if existing and existing.country else inferred_country)
    defaults["zone"] = zone or (existing.zone if existing and existing.zone else inferred_zone)
    client, _ = Client.objects.update_or_create(place_id=place_id, defaults=defaults)
    for row in reviews:
        review_id = row.get("review_id") or maps_scraper.fallback_key(
            f"{row.get('author', '')}{row.get('date', '')}{row.get('text', '')}"
        )
        Review.objects.update_or_create(
            client=client,
            review_id=review_id,
            defaults={
                "author": row.get("author", ""),
                "rating": row.get("rating"),
                "date": parse_date(row.get("date")),
                "text": row.get("text", ""),
                "owner_response": row.get("owner_response", ""),
            },
        )
    save_snapshot(client, place, reviews)
    return client


def refresh_client(client):
    return sync_client(client.source_url)
