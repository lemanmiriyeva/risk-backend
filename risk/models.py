from django.db import models
from authentication.models import User


class Risk(models.Model):
    TREATMENT_PREVENTION = 'prevention'
    TREATMENT_MITIGATION = 'mitigation'
    TREATMENT_TRANSFER = 'transfer'
    TREATMENT_ACCEPTANCE = 'acceptance'
    TREATMENT_CHOICES = [
        (TREATMENT_PREVENTION, 'Qarşısının alınması'),
        (TREATMENT_MITIGATION, 'Təsirin azaldılması'),
        (TREATMENT_TRANSFER, 'Ötürülmə'),
        (TREATMENT_ACCEPTANCE, 'Qəbul'),
    ]

    LEVEL_CRITICAL = 'critical'
    LEVEL_HIGH = 'high'
    LEVEL_MEDIUM = 'medium'
    LEVEL_LOW = 'low'
    LEVEL_CHOICES = [
        (LEVEL_CRITICAL, 'Kritik'),
        (LEVEL_HIGH, 'Yüksək'),
        (LEVEL_MEDIUM, 'Orta'),
        (LEVEL_LOW, 'Aşağı'),
    ]

    designation = models.CharField(max_length=255, verbose_name="Təyinat")
    legal_basis = models.TextField(blank=True, default='', verbose_name="Hüquqi əsas")
    international_framework = models.TextField(
        blank=True, default='', verbose_name="Beynəlxalq çərçivələr / Çərçivə istinadı"
    )
    national_legal_reference = models.TextField(blank=True, default='', verbose_name="Milli hüquqi istinad")

    asset_value = models.PositiveSmallIntegerField(verbose_name="Aktivin dəyəri (H)")   # 1-5
    probability = models.PositiveSmallIntegerField(verbose_name="Ehtimal (M)")           # 1-5
    impact = models.PositiveSmallIntegerField(verbose_name="Təsir (N)")                 # 1-5

    risk_degree = models.PositiveSmallIntegerField(default=0, editable=False, verbose_name="Risk dərəcəsi (P)")
    risk_level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default=LEVEL_LOW, editable=False, verbose_name="Risk səviyyəsi"
    )

    treatment_option = models.CharField(max_length=20, choices=TREATMENT_CHOICES, verbose_name="Emal variantı (Q)")
    residual_risk = models.TextField(blank=True, default='', verbose_name="Qalıq risk (T)")

    update_frequency = models.CharField(max_length=255, blank=True, default='', verbose_name="Yenilənmə tarixi/tezliyi")
    incident_notification_notes = models.TextField(blank=True, default='', verbose_name="İnsident bildirişi qeydləri")
    standard_references = models.TextField(blank=True, default='', verbose_name="Standartlara istinadlar")

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_risks', verbose_name="Riski yaradan"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_risks', verbose_name="Son dəyişikliyi edən"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ('-created_at',)
        verbose_name = "Risk"
        verbose_name_plural = "Risklər"

    def __str__(self):
        return self.designation

    def compute_risk(self):
        h = self.asset_value or 0
        m = self.probability or 0
        n = self.impact or 0
        degree = h * m * n
        if degree >= 60:
            level = self.LEVEL_CRITICAL
        elif degree >= 30:
            level = self.LEVEL_HIGH
        elif degree >= 12:
            level = self.LEVEL_MEDIUM
        else:
            level = self.LEVEL_LOW
        return degree, level

    def save(self, *args, **kwargs):
        self.risk_degree, self.risk_level = self.compute_risk()
        super().save(*args, **kwargs)

class RiskLog(models.Model):
    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_DELETED = 'deleted'
    ACTION_EXPORTED = 'exported'
    ACTION_VIEWED = 'viewed'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Yaradıldı'),
        (ACTION_UPDATED, 'Redaktə edildi'),
        (ACTION_DELETED, 'Silindi'),
        (ACTION_EXPORTED, 'Excel-ə ixrac edildi'),
        (ACTION_VIEWED, 'Baxıldı'),
    ]

    risk = models.ForeignKey(
        'Risk', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs', verbose_name="Risk"
    )
    risk_id_ref = models.PositiveIntegerField(verbose_name="Risk ID")
    risk_designation = models.CharField(max_length=255, blank=True, default='', verbose_name="Risk adı (snapshot)")

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="İstifadəçi"
    )
    user_username_snapshot = models.CharField(max_length=128, blank=True, default='', verbose_name="İstifadəçi adı (snapshot)")

    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Əməliyyat növü")

    changes = models.JSONField(null=True, blank=True, verbose_name="Dəyişikliklər")
    risk_snapshot = models.JSONField(null=True, blank=True, verbose_name="Silinmə anındakı tam surət")

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP ünvanı")
    user_agent = models.CharField(max_length=512, blank=True, default='', verbose_name="Brauzer/cihaz")

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Tarix/Vaxt")

    class Meta:
        ordering = ('-timestamp',)
        verbose_name = "Loq qeydi"
        verbose_name_plural = "Loq qeydləri"
        indexes = [
            models.Index(fields=['risk_id_ref', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.risk_designation} ({self.timestamp})"