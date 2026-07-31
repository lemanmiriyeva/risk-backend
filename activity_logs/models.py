from django.db import models
from authentication.models import User


class ActivityLog(models.Model):
    """
    Bütün saytın ümumi fəaliyyət loqu (giriş/çıxış, hansı modula girildi/çıxıldı,
    harada nə dəyişiklik edildi, hara baxıldı və s.).

    DİQQƏT: Bu model 'risk' tətbiqindəki RiskLog modelindən TAMAMİLƏ ayrıdır və
    onu əvəz etmir. RiskLog yalnız Risk Reyestri modulunun öz tarixçəsini saxlayır,
    bu model isə bütün saytın loqunu saxlayır.
    """

    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_VIEWED = 'viewed'
    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_DELETED = 'deleted'
    ACTION_EXPORTED = 'exported'
    ACTION_OTHER = 'other'
    ACTION_CHOICES = [
        (ACTION_LOGIN, 'Daxil oldu'),
        (ACTION_LOGOUT, 'Çıxış etdi'),
        (ACTION_VIEWED, 'Baxdı'),
        (ACTION_CREATED, 'Yaratdı'),
        (ACTION_UPDATED, 'Dəyişiklik etdi'),
        (ACTION_DELETED, 'Sildi'),
        (ACTION_EXPORTED, 'İxrac etdi'),
        (ACTION_OTHER, 'Digər'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activity_logs', verbose_name="İstifadəçi"
    )
    user_username_snapshot = models.CharField(
        max_length=128, blank=True, default='', verbose_name="İstifadəçi adı (snapshot)"
    )

    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Əməliyyat növü")

    module_code = models.CharField(max_length=100, blank=True, default='', verbose_name="Modul kodu")
    module_title = models.CharField(max_length=150, blank=True, default='', verbose_name="Modul adı")
    sub_module_title = models.CharField(max_length=150, blank=True, default='', verbose_name="Alt modul adı")

    description = models.CharField(max_length=500, blank=True, default='', verbose_name="Təsvir")

    object_repr = models.CharField(max_length=255, blank=True, default='', verbose_name="Obyekt")
    changes = models.JSONField(null=True, blank=True, verbose_name="Dəyişikliklər")

    request_method = models.CharField(max_length=10, blank=True, default='', verbose_name="HTTP metodu")
    request_path = models.CharField(max_length=500, blank=True, default='', verbose_name="URL")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Status kodu")

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP ünvanı")
    user_agent = models.CharField(max_length=512, blank=True, default='', verbose_name="Brauzer/cihaz")

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Tarix/Vaxt")

    class Meta:
        ordering = ('-timestamp',)
        verbose_name = "Sayt loqu"
        verbose_name_plural = "Sayt loqları"
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['module_code', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.user_username_snapshot} ({self.timestamp})"