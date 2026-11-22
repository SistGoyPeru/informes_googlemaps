from django import forms


class ClientUrlForm(forms.Form):
    url = forms.URLField(
        label="URL de Google Maps",
        widget=forms.URLInput(attrs={"placeholder": "https://www.google.com/maps/place/...", "class": "url-input"}),
        help_text="Pega la URL completa del local y extraeremos reseñas, fotos, notas y contacto.",
    )
    limit = forms.IntegerField(
        label="Máximo de reseñas",
        initial=500,
        min_value=10,
        max_value=5000,
        widget=forms.NumberInput(attrs={"class": "limit-input"}),
    )
    email = forms.EmailField(
        label="Correo del cliente",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "cliente@ejemplo.com", "class": "email-input"}),
        help_text="Se guarda para poder enviar el informe directamente a su correo.",
    )


class ClientEmailForm(forms.Form):
    email = forms.EmailField(label="Correo del cliente", required=False)
