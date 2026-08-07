from django.db import models

from core.models import TimestampsModel


class AttendancePermission(TimestampsModel):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Gözləmədə"),
        (STATUS_APPROVED, "Təsdiqlənib"),
        (STATUS_REJECTED, "Rədd edilib"),
    ]

    user = models.ForeignKey(
        "authentication.User", on_delete=models.CASCADE,
        related_name="attendance_permissions", verbose_name="İstifadəçi",
    )

    date = models.DateField(verbose_name="Tarix")
    start_time = models.TimeField(verbose_name="Başlanğıc saatı")
    end_time = models.TimeField(verbose_name="Bitmə saatı")
    location = models.CharField(max_length=255, verbose_name="Yer")
    reason = models.TextField(blank=True, default="", verbose_name="Səbəb / qeyd")

    # Yaradılan an istifadəçidən avtomatik köçürülür - sonradan user öz departamentini/
    # qurumunu dəyişsə belə, bu konkret sorğunun aid olduğu skop dəyişməsin deyə saxlanılır.
    department = models.ForeignKey(
        "authentication.Department", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_permissions", verbose_name="Departament",
    )
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_permissions", verbose_name="Qurum",
    )

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Status",
    )
    reviewed_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_attendance_permissions", verbose_name="Təsdiqləyən / Rədd edən",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Baxılma tarixi")
    review_comment = models.TextField(blank=True, default="", verbose_name="Rəy / qeyd")

    class Meta:
        verbose_name = "İcazə"
        verbose_name_plural = "İcazələr"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} | {self.date} {self.start_time}-{self.end_time} | {self.location}"

    def save(self, *args, **kwargs):
        if self.user_id:
            if not self.department_id:
                self.department = self.user.department
            if not self.organization_id:
                self.organization = self.user.organization
        super().save(*args, **kwargs)