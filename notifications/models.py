from django.db import models

from core.models import TimestampsModel


class Notification(TimestampsModel):
    TYPE_ATTENDANCE_PERMISSION_NEW = "attendance_permission_new"
    TYPE_ATTENDANCE_PERMISSION_DEPT_APPROVED = "attendance_permission_dept_approved"
    TYPE_ATTENDANCE_PERMISSION_APPROVED = "attendance_permission_approved"
    TYPE_ATTENDANCE_PERMISSION_REJECTED = "attendance_permission_rejected"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_ATTENDANCE_PERMISSION_NEW, "Yeni icazə sorğusu"),
        (TYPE_ATTENDANCE_PERMISSION_DEPT_APPROVED, "Şöbə müdiri təsdiqlədi"),
        (TYPE_ATTENDANCE_PERMISSION_APPROVED, "İcazə təsdiqləndi"),
        (TYPE_ATTENDANCE_PERMISSION_REJECTED, "İcazə rədd edildi"),
        (TYPE_OTHER, "Digər"),
    ]

    recipient = models.ForeignKey(
        "authentication.User", on_delete=models.CASCADE,
        related_name="notifications", verbose_name="Alıcı",
    )
    notification_type = models.CharField(
        max_length=64, choices=TYPE_CHOICES, default=TYPE_OTHER, verbose_name="Növü",
    )
    title = models.CharField(max_length=255, verbose_name="Başlıq")
    body = models.CharField(max_length=500, blank=True, default="", verbose_name="Mətn")

    # Frontend-in klik olunduqda hara yönləndirəcəyini bilməsi üçün sərbəst keçid linki
    link = models.CharField(max_length=255, blank=True, default="", verbose_name="Keçid")

    # Bağlı olduğu obyekt (məs. AttendancePermission) - generic saxlamırıq, sadə tutub
    # app/model adını və id-ni ayrıca saxlayırıq ki, sorğu asan olsun.
    related_app = models.CharField(max_length=64, blank=True, default="")
    related_object_id = models.PositiveIntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False, verbose_name="Oxunub")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxunma tarixi")

    class Meta:
        verbose_name = "Bildiriş"
        verbose_name_plural = "Bildirişlər"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} | {self.title}"