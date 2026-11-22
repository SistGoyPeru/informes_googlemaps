import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from core import services
from core.analytics import parse_date
from core.models import Client, Review

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class Command(BaseCommand):
    help = "Carga el histórico local de BURGER NUKENZI en la base de datos Django"

    def handle(self, *args, **options):
        payload = json.loads((DATA_DIR / "dashboard.json").read_text(encoding="utf-8"))
        place = payload.get("place") or {}
        summary = payload.get("summary") or {}
        reviews = payload.get("reviews") or []
        place_id = place.get("place_id") or summary.get("place_id") or services.maps_scraper.fallback_key(payload.get("source_url", ""))
        defaults = {
            "name": place.get("name") or summary.get("name") or "BURGER NUKENZI",
            "source_url": payload.get("source_url") or place.get("source_url", ""),
            "category": place.get("category", ""),
            "rating": place.get("rating") or summary.get("rating"),
            "review_total": int(place.get("review_total") or summary.get("review_total") or len(reviews)),
            "photo_total": int(place.get("photo_total") or summary.get("photo_total") or 0),
            "owner_photos": int(place.get("owner_photos") or summary.get("owner_photos") or 0),
            "customer_photos": int(place.get("customer_photos") or summary.get("customer_photos") or 0),
            "address": place.get("address") or summary.get("address", ""),
            "phone": place.get("phone") or summary.get("phone", ""),
            "hours": place.get("hours") or summary.get("hours", ""),
            "rating_counts": place.get("rating_counts") or summary.get("rating_counts") or {},
            "photos": place.get("photos") or [],
            "login_required": bool(place.get("login_required")),
            "last_scraped": timezone.now(),
        }
        client, _ = Client.objects.update_or_create(place_id=place_id, defaults=defaults)
        for row in reviews:
            Review.objects.update_or_create(
                client=client,
                review_id=row.get("review_id") or services.maps_scraper.fallback_key(str(row)),
                defaults={
                    "author": row.get("author", ""),
                    "rating": row.get("rating"),
                    "date": parse_date(row.get("date")),
                    "text": row.get("text", ""),
                    "owner_response": row.get("owner_response", ""),
                },
            )
        services.save_snapshot(client, place, reviews)
        self.stdout.write(self.style.SUCCESS(f"{client.name}: {client.reviews.count()} reseñas cargadas"))
