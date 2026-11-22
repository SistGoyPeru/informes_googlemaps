import zipfile
from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from reportlab.lib import colors

from . import analytics, briefs, reports, services
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
        self.assertContains(response, "Descargar TXT para correo")
        self.assertNotIn("faltan días", response.content.decode("utf-8"))

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

    def test_monthly_pdf_excludes_incomplete_current_month(self):
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
            self.assertEqual(response.status_code, 404)
            page = self.client.get(reverse("client_report", args=[self.client_obj.pk]))
            self.assertNotContains(page, f"?mes={current}")
            package = self.client.get(reverse("export_pdf_package", args=[self.client_obj.pk]))
            archive = zipfile.ZipFile(BytesIO(b"".join(package.streaming_content)))
            self.assertFalse(any(f"03_mes_{current}.pdf" in name for name in archive.namelist()))

    def test_email_brief_pdf(self):
        data = briefs.email_brief(self.client_obj, analytics.report_frame(self.client_obj.reviews.all()))
        self.assertNotIn("en curso", data["comment"])
        self.assertNotIn("falt", data["comment"].lower())
        response = self.client.get(reverse("export_brief", args=[self.client_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(b"%PDF" in b"".join(response.streaming_content)[:1024])

    def test_email_brief_txt(self):
        response = self.client.get(reverse("export_brief_txt", args=[self.client_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])
        content = response.content.decode("utf-8")
        self.assertIn("ASUNTO:", content)
        self.assertIn("COMENTARIO SUGERIDO PARA EL ARCHIVO:", content)
        self.assertIn(self.client_obj.name, content)

    def test_pdf_table_headers_use_white_text(self):
        styles = reports._styles()
        table = reports._table([{"KPI": "Valor"}], styles)
        self.assertEqual(table._cellvalues[0][0].style.textColor, colors.white)
        actions = reports._recommendation_table([{"priority": "Alta", "title": "Acción", "detail": "Detalle", "kpi": "KPI"}], styles)
        self.assertEqual(actions._cellvalues[0][0].style.textColor, colors.white)

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

    def test_normalize_url_accepts_short_maps_link(self):
        normalized = services.normalize_url("https://maps.app.goo.gl/ahRZFdiMikNKeyyBA")
        self.assertIn("maps.app.goo.gl", normalized)
        self.assertIn("hl=es", normalized)

    def test_resolve_maps_url_follows_google_redirect(self):
        short = "https://maps.app.goo.gl/ahRZFdiMikNKeyyBA"
        long_url = "https://www.google.com/maps/place/Loom's/data=!1s0x12a49384281f7a1b:0x10c79d277a2756dc"
        with patch("core.services.urlopen") as opener:
            opener.return_value.__enter__.return_value.geturl.return_value = long_url
            resolved = services.resolve_maps_url(short)
        self.assertEqual(resolved, long_url)

    def test_scrape_client_normalizes_resolved_short_link(self):
        short = "https://maps.app.goo.gl/ahRZFdiMikNKeyyBA"
        long_url = "https://www.google.com/maps/place/Loom's/data=!1s0x12a49384281f7a1b:0x10c79d277a2756dc"
        with patch("core.services.resolve_maps_url", return_value=long_url), \
             patch("core.services.maps_scraper.scrape_basic", return_value={}), \
             patch("core.services.maps_scraper.scrape_reviews", return_value=[]), \
             patch("core.services.save_snapshot"):
            url, _, _ = services.scrape_client(short, 10)
        self.assertIn("google.com/maps/place", url)
        self.assertIn("hl=es", url)
