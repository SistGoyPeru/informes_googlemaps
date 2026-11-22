from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("nuevo/", views.new_client, name="new_client"),
    path("cliente/<int:pk>/", views.client_report, name="client_report"),
    path("cliente/<int:pk>/actualizar/", views.update_client, name="update_client"),
    path("cliente/<int:pk>/agente/", views.agent_answer, name="agent_answer"),
    path("cliente/<int:pk>/exportar/csv/", views.export_csv, name="export_csv"),
    path("cliente/<int:pk>/exportar/ficha/txt/", views.export_brief_txt, name="export_brief_txt"),
    path("cliente/<int:pk>/exportar/ficha/", views.export_brief, name="export_brief"),
    path("cliente/<int:pk>/exportar/pdf/paquete/", views.export_pdf_package, name="export_pdf_package"),
    path("cliente/<int:pk>/exportar/pdf/", views.export_pdf, name="export_pdf"),
]
