from django import forms


class ClientUrlForm(forms.Form):
    url = forms.URLField(
        label="URL de Google Maps",
        widget=forms.URLInput(attrs={"placeholder": "https://www.google.com/maps/place/...", "class": "url-input"}),
        help_text="Pega la URL completa o el link corto de Google Maps y extraeremos todas las reseñas, fotos, notas y contacto.",
    )
    country = forms.CharField(
        label="País (opcional)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej. España", "class": "url-input"}),
        help_text="Si lo dejas vacío, lo deducimos de la dirección.",
    )
    zone = forms.CharField(
        label="Zona (opcional)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Barcelona", "class": "url-input"}),
        help_text="Ciudad, distrito o zona comercial para agrupar el cliente.",
    )
