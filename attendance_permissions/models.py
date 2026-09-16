from django.db import models

from core.models import TimestampsModel


class AttendancePermission(TimestampsModel):
    STATUS_PENDING = "pending"                    # Şöbə müdirinin baxmasını gözləyir
    STATUS_AWAITING_APPARATUS = "awaiting_apparatus"  # Şöbə müdiri təsdiqləyib, Aparat rəhbərini gözləyir
    STATUS_APPROVED = "approved"                   # Aparat rəhbəri (son mərhələ) təsdiqləyib
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Gözləmədə"),
        (STATUS_AWAITING_APPARATUS, "Aparat rəhbərinin təsdiqini gözləyir"),
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
    location = models.CharField(max_length=255, blank=True, default="", verbose_name="Yer")
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
        max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Status",
    )

    # Mərhələ 1: şöbə müdirinin baxışı
    department_reviewed_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="department_reviewed_attendance_permissions", verbose_name="Şöbə müdiri (baxan)",
    )
    department_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Şöbə müdirinin baxma tarixi")
    department_review_comment = models.TextField(blank=True, default="", verbose_name="Şöbə müdirinin rəyi")

    # Mərhələ 2 (son): Aparat rəhbərinin baxışı. Şöbə müdiri sorğunu rədd edərsə də
    # bu sahələr dolur (proses orada bitdiyi üçün "son qərar" kimi qeyd olunur).
    reviewed_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_attendance_permissions", verbose_name="Son qərarı verən",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Son baxılma tarixi")
    review_comment = models.TextField(blank=True, default="", verbose_name="Son rəy / qeyd")

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

class AttendancePermissionOrganizationConfig(TimestampsModel):
    """
    Qurum üzrə icazə workflow konfiqurasiyası.

    Aparat rəhbərinin icazə workflow-da aktiv olub-olmamasını
    və konkret Aparat rəhbərini təyin edir.
    """

    organization = models.OneToOneField(
        "authentication.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_permission_config",
        verbose_name="Qurum",
    )

    apparatus_head_enabled = models.BooleanField(
        default=True,
        verbose_name="Aparat rəhbəri aktivdir",
    )

    apparatus_head = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_apparatus_head_configs",
        verbose_name="Aparat rəhbəri",
    )

    class Meta:
        verbose_name = "İcazə konfiqurasiyası"
        verbose_name_plural = "İcazə konfiqurasiyaları"

    def __str__(self):
        return f"{self.organization.title} - İcazə konfiqurasiyası"


class AttendancePermissionDepartmentConfig(TimestampsModel):
    """
    Hər departament üçün ayrıca icazə workflow konfiqurasiyası.

    manager_enabled=False olduqda replacement_user seçilməlidir.
    """

    organization = models.ForeignKey(
        "authentication.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_permission_department_configs",
        verbose_name="Qurum",
    )

    department = models.OneToOneField(
        "authentication.Department",
        on_delete=models.CASCADE,
        related_name="attendance_permission_config",
        verbose_name="Departament",
    )

    manager_enabled = models.BooleanField(
        default=True,
        verbose_name="Şöbə müdiri aktivdir",
    )

    replacement_user = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_permission_replacement_configs",
        verbose_name="Əvəzləyici şəxs",
    )

    # manager_enabled=False olduqda (yəni şöbə müdiri yoxdursa/təyin edilməyibsə)
    # sorğu 1-ci mərhələdə kimə göndərilsin:
    #   FALLBACK_REPLACEMENT - aşağıdakı `replacement_user`-ə (əvəzləyici, adi 1-ci
    #       mərhələ kimi baxır, sonra normal axınla Aparat rəhbərinə keçir)
    #   FALLBACK_APPARATUS   - 1-ci mərhələ tamamilə keçilir, sorğu birbaşa
    #       Aparat rəhbərinə (2-ci/son mərhələ) göndərilir
    FALLBACK_REPLACEMENT = "replacement"
    FALLBACK_APPARATUS = "apparatus"
    NO_MANAGER_FALLBACK_CHOICES = [
        (FALLBACK_REPLACEMENT, "Əvəzləyici şəxs (1-ci mərhələdə baxır)"),
        (FALLBACK_APPARATUS, "Birbaşa Aparat rəhbəri (2-ci/son mərhələ)"),
    ]

    no_manager_fallback = models.CharField(
        max_length=16,
        choices=NO_MANAGER_FALLBACK_CHOICES,
        default=FALLBACK_REPLACEMENT,
        verbose_name="Şöbə müdiri yoxdursa",
        help_text=(
            "Şöbə müdiri aktiv deyilsə (manager_enabled=False), sorğu kimə "
            "göndərilsin: əvəzləyici şəxsə, yoxsa birbaşa Aparat rəhbərinə "
            "(1-ci mərhələ tamamilə keçilərək)."
        ),
    )

    class Meta:
        verbose_name = "Departament icazə konfiqurasiyası"
        verbose_name_plural = "Departament icazə konfiqurasiyaları"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "department"],
                name="unique_attendance_permission_department_config",
            )
        ]

    def __str__(self):
        return f"{self.organization.title} / {self.department.title}"

class LeavePeriod(TimestampsModel):
    """
    Məzuniyyət dövrü və həmin dövr üçün əvəzləyici şəxs.

    Yalnız ŞÖBƏ MÜDİRİ və ondan YUXARI vəzifələr üçün nəzərdə tutulub
    (bax: `can_set_leave_period`), çünki məqsəd icazə sorğularını təsdiq
    edən şəxsin məzuniyyətdə olduğu müddətdə işlərin dayanmamasıdır.

    AVTOMATİK GERİ QAYITMA:
    Bu model «həqiqət mənbəyi»dir - departament konfiqurasiyasındakı
    `replacement_user` sahəsi ÜZƏRİNƏ YAZILMIR. Əvəzləmə hər sorğuda
    tarixə görə HESABLANIR (bax: `get_active_delegate_for`), ona görə
    məzuniyyət bitən kimi heç bir cron/planlayıcı olmadan avtomatik
    olaraq köhnə vəziyyətə qayıdır. Eyni səbəbdən keçmiş dövrlər tarixçə
    kimi saxlanılır və audit üçün əlçatan qalır.
    """

    user = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="leave_periods",
        verbose_name="Əməkdaş",
    )
    replacement_user = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="leave_delegations",
        verbose_name="Əvəzləyici şəxs",
        help_text="Məzuniyyət dövründə işləri həll edəcək şəxs.",
    )
    start_date = models.DateField(verbose_name="Başlama tarixi")
    end_date = models.DateField(verbose_name="Bitmə tarixi")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Qeyd")
    is_cancelled = models.BooleanField(
        default=False,
        verbose_name="Ləğv edilib",
        help_text="Məzuniyyət vaxtından əvvəl bitirilibsə işarələnir.",
    )

    class Meta:
        ordering = ("-start_date",)
        verbose_name = "Məzuniyyət dövrü"
        verbose_name_plural = "Məzuniyyət dövrləri"
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="leave_period_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.start_date} / {self.end_date}"

    def covers(self, day):
        return (
            not self.is_cancelled
            and self.start_date <= day <= self.end_date
        )

    @property
    def is_active_now(self):
        from django.utils import timezone
        return self.covers(timezone.localdate())
