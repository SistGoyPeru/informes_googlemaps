from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils.text import slugify

from . import analytics, briefs, reports


def attachment_info(path, label):
    return {
        "path": path,
        "name": path.name,
        "label": label,
        "size": round(path.stat().st_size / 1024),
    }


def _text_content(client, data):
    return (
        f"ASUNTO:\n{data['subject']}\n\nCOMENTARIO SUGERIDO PARA EL ARCHIVO:\n{data['comment']}\n\nCUERPO COMPLETO PARA COPIAR:\n{data['body']}\n"
    )


def prepare_preview(client):
    raw_frame = analytics.enrich(analytics.to_frame(client.reviews.all()))
    data = briefs.email_brief(client, raw_frame)
    ficha_path = reports.export_brief(client, raw_frame, filename="00_FICHA_DE_ENVIO.pdf")
    txt_path = reports._client_folder(client) / f"ficha_correo_cliente_{client.pk}.txt"
    txt_path.write_text(_text_content(client, data), encoding="utf-8")
    items = [
        {
            "name": f"PAQUETE_PDF_{slugify(client.name)}.zip",
            "label": "Paquete completo de PDF",
            "size": "se genera al enviar",
            "path": None,
        },
        attachment_info(ficha_path, "Ficha de envío"),
        attachment_info(txt_path, "Texto para correo"),
    ]
    items[1]["download_url"] = reverse("export_brief", args=[client.pk])
    items[2]["download_url"] = reverse("export_brief_txt", args=[client.pk])
    return data, items


def prepare_attachments(client):
    raw_frame = analytics.enrich(analytics.to_frame(client.reviews.all()))
    complete_frame = analytics.complete_months(raw_frame)
    data = briefs.email_brief(client, raw_frame)
    zip_path, _ = reports.export_pdf_package(client, complete_frame, raw_frame)
    ficha_path = reports.export_brief(client, raw_frame, filename="00_FICHA_DE_ENVIO.pdf")
    txt_path = reports._client_folder(client) / f"ficha_correo_cliente_{client.pk}.txt"
    txt_path.write_text(_text_content(client, data), encoding="utf-8")
    return [
        attachment_info(zip_path, "Paquete completo de PDF"),
        attachment_info(ficha_path, "Ficha de envío"),
        attachment_info(txt_path, "Texto para correo"),
    ]


def send_report_email(client, subject, body, attachments):
    if not settings.EMAIL_READY:
        raise ValueError("Falta configurar GMAIL_APP_PASSWORD para enviar desde Gmail.")
    if not client.email:
        raise ValueError("Guarda el correo del cliente antes de enviar.")
    message = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [client.email],
        reply_to=[settings.DEFAULT_FROM_EMAIL],
    )
    for item in attachments:
        message.attach_file(str(item["path"]))
    return message.send(fail_silently=False)
