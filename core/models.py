from django.db import models

from django.utils import timezone
# Create your models here.
class TimestampsModel(models.Model):

    @classmethod
    def get_fields(cls, fields: tuple):
        return fields.__add__(('created_at', 'updated_at'))

    created_at = models.DateTimeField(null=True, blank=True, default=timezone.now, verbose_name="yaradılma tarixi")
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True, verbose_name="dəyişdirilmə tarixi")

    class Meta:
        abstract = True


class Module(TimestampsModel):
    title = models.CharField(max_length=255, verbose_name="Başlıq")
    path = models.CharField(max_length=255, verbose_name="Əsas path (baxış üçün)")
    permission = models.CharField(
        max_length=150,
        verbose_name="Görünmə üçün minimum permission",
        help_text="Məsələn: risk.view_risk"
    )

    elevated_permission = models.CharField(
        max_length=150, blank=True, null=True,
        verbose_name="Əlavə/Redaktə permission-u (opsional)",
        help_text="Boş buraxsanız, hər kəs 'path' sahəsinə yönləndirilir. "
                   "Doldursanız, bu permission-lardan biri olanlar 'elevated_path'-a gedir."
    )
    elevated_path = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Yüksək səlahiyyət path-i (opsional)",
        help_text="Məsələn: /risk (redaktə edə bilənlər üçün)"
    )

    order = models.PositiveIntegerField(default=0, verbose_name="Sıra")
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")

    class Meta:
        ordering = ["order"]
        verbose_name = "Modul"
        verbose_name_plural = "Modullar"

    def __str__(self):
        return self.title