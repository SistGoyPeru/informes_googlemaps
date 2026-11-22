from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cliente/<int:pk>/", views.client_report, name="client_report"),
    path("cliente/<int:pk>/actualizar/", views.update_client, name="update_client"),
    path("cliente/<int:pk>/exportar/csv/", views.export_csv, name="export_csv"),
    path("cliente/<int:pk>/exportar/pdf/", views.export_pdf, name="export_pdf"),
]
