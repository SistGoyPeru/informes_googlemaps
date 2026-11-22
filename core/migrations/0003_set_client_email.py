from django.db import migrations

CLIENT_EMAIL = "dongwj2004@gmail.com"


def set_client_email(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    Client.objects.filter(name__icontains="BURGER NUKENZI").update(email=CLIENT_EMAIL)


def unset_client_email(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    Client.objects.filter(email=CLIENT_EMAIL).update(email="")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_client_email"),
    ]

    operations = [
        migrations.RunPython(set_client_email, unset_client_email),
    ]
