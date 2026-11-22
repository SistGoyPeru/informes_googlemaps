from django import forms


class ClientUrlForm(forms.Form):
    url = forms.URLField(
        label="URL de Google Maps",
        widget=forms.URLInput(attrs={"placeholder": "https://www.google.com/maps/place/...", "class": "url-input"}),
        help_text="Pega la URL completa o el link corto de Google Maps y extraeremos todas las reseñas, fotos, notas y contacto.",
    )
