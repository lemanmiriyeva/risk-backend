from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TimestampsModel


class Operation(TimestampsModel):

    TYPE_CRUD = 'crud'
    TYPE_APPROVAL = 'approval'
    TYPE_CHOICES = [
        (TYPE_CRUD, 'CRUD əməliyyatı'),
        (TYPE_APPROVAL, 'Təsdiq tələb edən əməliyyat'),
    ]

    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_DELETED = 'deleted'
    ACTION_EXPORTED = 'exported'
    ACTION_REQUESTED = 'requested'
    ACTION_REVIEWED = 'reviewed'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Yaratdı'),
        (ACTION_UPDATED, 'Redaktə etdi'),
        (ACTION_DELETED, 'Sildi'),
        (ACTION_EXPORTED, 'İxrac etdi'),
        (ACTION_REQUESTED, 'Sorğu göndərdi'),
        (ACTION_REVIEWED, 'Baxdı'),
    ]

    STATUS_COMPLETED = 'completed'
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Tamamlandı'),
        (STATUS_PENDING, 'Gözləmədə'),
        (STATUS_IN_PROGRESS, 'Baxılır'),
        (STATUS_APPROVED, 'Təsdiqləndi'),
        (STATUS_REJECTED, 'Rədd edildi'),
        (STATUS_CANCELED, 'Ləğv edildi'),
    ]

    operation_type = models.CharField(
        max_length=16, choices=TYPE_CHOICES, verbose_name="Əməliyyat tipi"
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, verbose_name="Hərəkət")
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_COMPLETED, verbose_name="Status"
    )

    # Kateqoriya = əməliyyatın aid olduğu modul
    module = models.ForeignKey(
        "core.Module", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", verbose_name="Modul"
    )
    category_code = models.CharField(max_length=100, blank=True, default='', verbose_name="Kateqoriya kodu")
    category_title = models.CharField(max_length=150, blank=True, default='', verbose_name="Kateqoriya (Modul adı)")

    user = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", verbose_name="İstifadəçi"
    )
    user_username_snapshot = models.CharField(
        max_length=128, blank=True, default='', verbose_name="İstifadəçi adı (snapshot)"
    )
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", verbose_name="Qurum"
    )

    # Əlaqəli əsl obyekt (Risk, AttendancePermission, İnventar sətri və s.) -
    # istənilən modeli dəstəkləyir, gələcək modullar üçün əlavə iş tələb olunmur.
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Obyekt tipi"
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="Obyekt ID")
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(max_length=255, blank=True, default='', verbose_name="Obyekt (snapshot)")

    description = models.CharField(max_length=500, blank=True, default='', verbose_name="Təsvir")
    changes = models.JSONField(null=True, blank=True, verbose_name="Dəyişikliklər")

    # Təsdiq axını üçün (operation_type=approval olduqda mənalıdır).
    # Mərhələ sayı modula görə sərbəstdir (bax: OperationApprovalStep).
    total_steps = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Mərhələ sayı")
    current_step = models.PositiveSmallIntegerField(default=0, verbose_name="Hazırkı mərhələ")

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP ünvanı")
    user_agent = models.CharField(max_length=512, blank=True, default='', verbose_name="Brauzer/cihaz")

    class Meta:
        ordering = ('-created_at',)
        verbose_name = "Əməliyyat"
        verbose_name_plural = "Əməliyyatlar"
        indexes = [
            models.Index(fields=['category_code', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        label = self.category_title or self.category_code or 'Əməliyyat'
        return f"{label} — {self.get_action_display()} ({self.get_status_display()})"


class OperationApprovalStep(TimestampsModel):
    """
    Bir təsdiq əməliyyatının tək bir mərhələsi. Hər modul öz mərhələ sayını
    və rollarını sərbəst təyin edə bilər (attendance_permissions-dakı 2 mərhələli
    'şöbə müdiri → aparat rəhbəri' axını buna bir nümunədir, amma başqa modul
    1 mərhələli və ya 3+ mərhələli ola bilər - məhdudiyyət yoxdur).
    """

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Gözləmədə'),
        (STATUS_APPROVED, 'Təsdiqləndi'),
        (STATUS_REJECTED, 'Rədd edildi'),
        (STATUS_SKIPPED, 'Keçildi'),
    ]

    operation = models.ForeignKey(
        Operation, on_delete=models.CASCADE, related_name="approval_steps", verbose_name="Əməliyyat"
    )
    step_number = models.PositiveSmallIntegerField(verbose_name="Mərhələ nömrəsi")
    role_label = models.CharField(max_length=150, blank=True, default='', verbose_name="Rol / vəzifə")

    approver = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operation_approval_steps", verbose_name="Təyin olunan təsdiqləyici"
    )
    reviewed_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_operation_steps", verbose_name="Baxan"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Status"
    )
    comment = models.TextField(blank=True, default='', verbose_name="Rəy / qeyd")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Baxılma tarixi")

    class Meta:
        ordering = ('operation_id', 'step_number')
        verbose_name = "Təsdiq mərhələsi"
        verbose_name_plural = "Təsdiq mərhələləri"
        unique_together = ('operation', 'step_number')

    def __str__(self):
        return f"Əməliyyat #{self.operation_id} - Mərhələ {self.step_number} ({self.get_status_display()})"