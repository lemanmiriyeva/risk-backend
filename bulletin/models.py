from django.db import models
from django.utils import timezone

from authentication.models import User


class Circular(models.Model):
    """
    Sərəncamlar / Fərmanlar / Daxili qaydalar üçün ortaq model.

    `organization` boş qalarsa (null), sənəd BÜTÜN qurumlara aiddir (məs.
    Nazirlik səviyyəsində bir sərəncam) - əks halda yalnız həmin qurumun
    işçilərinə göstərilir. Bax: BulletinQuerysetMixin.
    """

    CATEGORY_SERENCAM = "serencam"
    CATEGORY_FERMAN = "ferman"
    CATEGORY_DAXILI_QAYDA = "daxili_qayda"
    CATEGORY_CHOICES = [
        (CATEGORY_SERENCAM, "Sərəncam"),
        (CATEGORY_FERMAN, "Fərman"),
        (CATEGORY_DAXILI_QAYDA, "Daxili qayda"),
    ]

    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, verbose_name="Növ"
    )
    title = models.CharField(max_length=255, verbose_name="Başlıq")
    number = models.CharField(max_length=50, blank=True, default="", verbose_name="Nömrə")
    document_date = models.DateField(
        null=True, blank=True, verbose_name="Sənəd tarixi",
        help_text="Sərəncam/fərmanın imzalandığı tarix.",
    )
    file = models.FileField(
        upload_to="bulletin/circulars/%Y/%m/", null=True, blank=True,
        verbose_name="Fayl (PDF və s.)",
    )
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.CASCADE, related_name="circulars",
        null=True, blank=True, verbose_name="Qurum",
        help_text="Boş buraxılsa, bu sənəd BÜTÜN qurumların işçilərinə görünür.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_circulars", verbose_name="Yaradan",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ("-document_date", "-created_at")
        verbose_name = "Sərəncam / Fərman / Daxili qayda"
        verbose_name_plural = "Sərəncamlar, Fərmanlar, Daxili qaydalar"

    def __str__(self):
        return f"{self.get_category_display()} — {self.title}"


class NewsPost(models.Model):
    """Xəbərlər lövhəsi üçün xəbər yazıları."""

    title = models.CharField(max_length=255, verbose_name="Başlıq")
    summary = models.CharField(max_length=500, blank=True, default="", verbose_name="Qısa xülasə")
    body = models.TextField(blank=True, default="", verbose_name="Mətn")
    image = models.ImageField(
        upload_to="bulletin/news/%Y/%m/", null=True, blank=True, verbose_name="Şəkil",
    )
    published_at = models.DateTimeField(default=timezone.now, verbose_name="Dərc tarixi")
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.CASCADE, related_name="news_posts",
        null=True, blank=True, verbose_name="Qurum",
        help_text="Boş buraxılsa, bu xəbər BÜTÜN qurumların işçilərinə görünür.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_news", verbose_name="Yaradan",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ("-published_at",)
        verbose_name = "Xəbər"
        verbose_name_plural = "Xəbərlər"

    def __str__(self):
        return self.title