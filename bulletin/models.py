from django.db import models
from django.utils import timezone

from authentication.models import User


class BulletinCategory(models.Model):
    """
    Sənəd növləri (Fərman, Sərəncam, Daxili qayda və s.).

    Əvvəllər bu, `Circular.category` sahəsində sərt `choices` siyahısı idi.
    İndi ayrıca cədvəldir ki, modul admini panel üzərindən (kodu toxunmadan)
    yeni növ əlavə edə, sırasını dəyişə və ya lazım olmayanı deaktiv edə bilsin.

    Qeyd: köhnə `django_filters.ChoiceFilter(choices=Circular.CATEGORY_CHOICES)`
    Django 5.0 ilə uyğun gəlmirdi ("'super' object has no attribute
    '_set_choices'") - bu modelə keçid səbəbi yalnız "dinamik kateqoriya"
    tələbi deyil, həm də həmin xətanı kökündən aradan qaldırmaqdır (bax:
    filters.py - artıq ChoiceFilter istifadə olunmur).
    """

    ICON_CHOICES = [
        ("gavel", "Ədalət çəkisi"),
        ("assignment", "Tapşırıq"),
        ("rule", "Qayda"),
        ("description", "Sənəd"),
        ("article", "Məqalə"),
        ("policy", "Siyasət"),
        ("campaign", "Elan"),
        ("event_note", "Tədbir"),
        ("shield", "Qalxan"),
        ("folder", "Qovluq"),
    ]

    key = models.SlugField(
        max_length=50, unique=True, verbose_name="Açar",
        help_text="Kiçik hərflərlə, boşluqsuz (məs. ferman) - keçidlərdə istifadə olunur.",
    )
    label = models.CharField(max_length=100, verbose_name="Ad")
    plural_label = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Cəm forma",
        help_text="Boş buraxılsa, «Ad» sahəsi istifadə olunur.",
    )
    description = models.CharField(max_length=255, blank=True, default="", verbose_name="Qısa izah")
    icon = models.CharField(max_length=30, choices=ICON_CHOICES, default="description", verbose_name="İkon")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıra")
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Sənəd kateqoriyası"
        verbose_name_plural = "Sənəd kateqoriyaları"

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        if not self.plural_label:
            self.plural_label = self.label
        super().save(*args, **kwargs)


class Circular(models.Model):
    """
    Fərman / Sərəncam / Daxili qayda və (dinamik) digər kateqoriyalı sənədlər üçün ortaq model.

    `organization` boş qalarsa (null), sənəd BÜTÜN qurumlara aiddir (məs.
    Nazirlik səviyyəsində bir sərəncam) - əks halda yalnız həmin qurumun
    işçilərinə göstərilir. Bax: BulletinQuerysetMixin.
    """

    category = models.ForeignKey(
        BulletinCategory, on_delete=models.PROTECT, related_name="circulars",
        verbose_name="Növ",
        help_text="Kateqoriyalar 'Sənəd kateqoriyaları' bölməsindən idarə olunur.",
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
        return f"{self.category.label} — {self.title}"


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