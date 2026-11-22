import shutil
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
from django.test import TestCase, override_settings
from django.urls import reverse

from core import analytics
from core.models import Client, Review

TEMP_MEDIA = tempfile.mkdtemp(prefix="informes-media-")


class AnalyticsTests(TestCase):
    def test_enrich_and_kpis(self):
        frame = pd.DataFrame([
            {"review_id": "1", "author": "A", "rating": 5, "date": "2026-11-02", "text": "comida rica", "owner_response": "gracias"},
            {"review_id": "2", "author": "B", "rating": 1, "date": "2026-11-20", "text": "mucha espera", "owner_response": ""},
        ])
        source = analytics.enrich(frame)
        self.assertEqual(len(source), 2)
        kpis = analytics.reputation_kpis(source)
        self.assertEqual(kpis["total"], 2)
        self.assertEqual(kpis["average"], 3.0)
        self.assertEqual(kpis["negative"], 1)
        self.assertEqual(kpis["responses"], 1)
        self.assertEqual(analytics.week_options(source, "2026-11")[0]["number"], 1)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_obj = Client.objects.create(
            place_id="test-place",
            name="Local Prueba",
            source_url="https://www.google.com/maps/place/Local+Prueba?hl=es",
            rating=4.5,
            review_total=3,
            photo_total=10,
        )
        Review.objects.create(client=cls.client_obj, review_id="r1", author="A", rating=5, date=date(2026, 10, 2), text="rica comida", owner_response="gracias")
        Review.objects.create(client=cls.client_obj, review_id="r2", author="B", rating=2, date=date(2026, 11, 20), text="mucha espera")
        Review.objects.create(client=cls.client_obj, review_id="r3", author="C", rating=4, date=date(2026, 11, 21), text="buen precio")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_home_renders(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Local Prueba")

    def test_report_filters(self):
        url = reverse("client_report", args=[self.client_obj.pk])
        response = self.client.get(url, {"year": 2026, "month": "2026-11", "week": 4})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "noviembre 2026")
        self.assertContains(response, "Resumen semanal")

    def test_csv_exports(self):
        for kind in ("resumen", "resenas", "mensual", "anual", "semanal", "diario"):
            url = reverse("export_csv", args=[self.client_obj.pk]) + f"?tipo={kind}"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/csv", response["Content-Type"])

    def test_pdf_export(self):
        response = self.client.get(reverse("export_pdf", args=[self.client_obj.pk]))
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertTrue(any(Path(TEMP_MEDIA).rglob("*.pdf")))
