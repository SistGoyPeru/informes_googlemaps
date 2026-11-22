from django.db import models


class Client(models.Model):
    place_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    source_url = models.URLField(max_length=2000)
    category = models.CharField(max_length=120, blank=True)
    rating = models.FloatField(null=True, blank=True)
    review_total = models.PositiveIntegerField(default=0)
    photo_total = models.PositiveIntegerField(default=0)
    owner_photos = models.PositiveIntegerField(default=0)
    customer_photos = models.PositiveIntegerField(default=0)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=120, blank=True)
    hours = models.TextField(blank=True)
    rating_counts = models.JSONField(default=dict, blank=True)
    photos = models.JSONField(default=list, blank=True)
    login_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_scraped = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Review(models.Model):
    client = models.ForeignKey(Client, related_name="reviews", on_delete=models.CASCADE)
    review_id = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    rating = models.FloatField(null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    text = models.TextField(blank=True)
    owner_response = models.TextField(blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["client", "review_id"], name="unique_review_per_client"),
        ]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["rating"]),
        ]

    def __str__(self):
        return f"{self.author} · {self.rating}★"
