import zipfile
from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import analytics, services
from .models import Client, Review


class DashboardTests(TestCase):
    def setUp(self):
        month = analytics.last_complete_month()
        year, number = (int(part) for part in month.split("-"))
        review_date = date(year, number, 5)
        self.month = month
        self.year = year
        self.client_obj = Client.objects.create(
            name="Local Prueba",
            source_url="https://www.google.com/maps/place/Local+Prueba/data=!1s0x1:0xabc",
            place_id="ChIJPrueba001",
            rating=4.5,
            review_total=485,
            photo_total=166,
            owner_photos=9,
            customer_photos=157,
            last_scraped=timezone.now(),
        )
        Review.objects.create(
            client=self.client_obj,
            review_id="r1",
            author="Ana",
            rating=5,
            date=review_date,
            text="La comida estaba riquísima y la atención fue excelente.",
            owner_response="¡Gracias, Ana!",
        )
        Review.objects.create(
            client=self.client_obj,
            review_id="r2",
            author="Luis",
            rating=1,
            date=review_date,
            text="Mucho retraso y el pedido llegó frío.",
            owner_response="",
        )

    def test_home_renders_rankings(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ranking de clientes")
        self.assertContains(response, "KPIs que recomiendo vigilar")

    def test_report_filters_by_month(self):
        response = self.client.get(reverse("client_report", args=[self.client_obj.pk]), {"vista": "mes", "month": self.month})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Desglose semanal")
        self.assertContains(response, "2. Lo que funciona")
        self.assertContains(response, "Cómo leer este informe")
        self.assertContains(response, "Reportes PDF profesionales")
        self.assertContains(response, "Ficha para enviar por correo")

    def test_incomplete_current_month_is_excluded(self):
        current = datetime.now().strftime("%Y-%m")
        last_complete = analytics.last_complete_month()
        if current > last_complete:
            Review.objects.create(
                client=self.client_obj,
                review_id="r3",
                author="Mes incompleto",
                rating=5,
                date=date(int(current[:4]), int(current[5:]), 1),
                text="Reseña del mes abierto.",
            )
            frame = analytics.report_frame(self.client_obj.reviews.all())
            self.assertNotIn(current, frame["mes"].tolist())
            self.assertIn(self.month, frame["mes"].tolist())

    def test_monthly_pdf_includes_incomplete_current_month(self):
        current = datetime.now().strftime("%Y-%m")
        last_complete = analytics.last_complete_month()
        if current > last_complete:
            Review.objects.create(
                client=self.client_obj,
                review_id="r4",
                author="Mes actual",
                rating=4,
                date=date(int(current[:4]), int(current[5:]), 1),
                text="Reseña del mes en curso.",
                owner_response="Gracias",
            )
            response = self.client.get(reverse("export_pdf", args=[self.client_obj.pk]), {"mes": current})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            package = self.client.get(reverse("export_pdf_package", args=[self.client_obj.pk]))
            archive = zipfile.ZipFile(BytesIO(b"".join(package.streaming_content)))
            self.assertTrue(any(f"03_mes_{current}.pdf" in name for name in archive.namelist()))

    def test_email_brief_pdf(self):
        response = self.client.get(reverse("export_brief", args=[self.client_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(b"%PDF" in b"".join(response.streaming_content)[:1024])

    def test_pdf_general_year_month_and_package(self):
        for query in ({}, {"anio": self.year}, {"mes": self.month}):
            response = self.client.get(reverse("export_pdf", args=[self.client_obj.pk]), query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertTrue(b"%PDF" in b"".join(response.streaming_content)[:1024])
        response = self.client.get(reverse("export_pdf_package", args=[self.client_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        archive = zipfile.ZipFile(BytesIO(b"".join(response.streaming_content)))
        names = archive.namelist()
        self.assertIn("LEEME.txt", names)
        self.assertTrue(any("00_FICHA_DE_ENVIO.pdf" in name for name in names))
        self.assertTrue(any("01_informe_general.pdf" in name for name in names))
        self.assertTrue(any(f"02_anio_{self.year}.pdf" in name for name in names))
        self.assertTrue(any(f"03_mes_{self.month}.pdf" in name for name in names))

    def test_new_client_form(self):
        url = "https://www.google.com/maps/place/Otro+Local/data=!1s0x2:0xdef"
        with patch("core.views.services.sync_client", return_value=self.client_obj) as sync:
            response = self.client.post(reverse("new_client"), {"url": url, "limit": 200})
        sync.assert_called_once_with(url, 200)
        self.assertRedirects(response, reverse("client_report", args=[self.client_obj.pk]) + "?vista=total")

    def test_normalize_url_adds_hl(self):
        normalized = services.normalize_url("https://www.google.com/maps/place/Local+Prueba")
        self.assertIn("hl=es", normalized)
        self.assertIn("google.com/maps/place", normalized)
