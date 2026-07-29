from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger('colored')


class TimestampsModel(models.Model):

    @classmethod
    def get_fields(cls, fields: tuple):
        return fields.__add__(('created_at', 'updated_at'))

    created_at = models.DateTimeField(null=True, blank=True, default=timezone.now, verbose_name="yaradılma tarixi")
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True, verbose_name="dəyişdirilmə tarixi")

    class Meta:
        abstract = True


class Module(TimestampsModel):
    title = models.CharField(max_length=120, verbose_name="Modul adı")
    description = models.TextField(verbose_name="Modul təsviri", null=True, blank=True)
    code = models.SlugField(max_length=100, unique=True)
    permitted_users = models.ManyToManyField(
        "authentication.User", related_name="modules", blank=True,
        verbose_name="Fərdi icazəli istifadəçilər"
    )
    permitted_organizations = models.ManyToManyField(
        "authentication.Organization", related_name="modules", blank=True,
        verbose_name="Əlaqəli qurumlar (əhatə dairəsi)",
        help_text=(
            "Bu modulun hansı qurum(lar) üçün nəzərdə tutulduğunu göstərir. "
            "DİQQƏT: bu sahə tək başına heç bir user-ə giriş vermir — "
            "qurumun bütün işçilərinə avtomatik açılmır. Real giriş yalnız "
            "'Fərdi icazəli istifadəçilər' (permitted_users) sahəsi ilə verilir; "
            "burada seçilən qurum(lar) yalnız o sahəyə hansı user-lərin əlavə "
            "oluna biləcəyini məhdudlaşdırır (başqa qurumun işçisi əlavə edilə bilməz)."
        )
    )
    url_endpoint = models.CharField(max_length=120, verbose_name="Url linki")
    image = models.ImageField(upload_to='module_images/%Y/%m/%d', null=True, blank=True, verbose_name="Modul ikonu")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Modul"
        verbose_name_plural = "Modullar"

    def is_user_eligible(self, user):
        """
        İstifadəçi bu modula fərdi olaraq icazə üçün namizəd ola bilərmi?
        permitted_organizations boşdursa - məhdudiyyət yoxdur (istənilən user seçilə bilər).
        Doludursa - yalnız o qurum(lar)ın işçiləri seçilə bilər.
        """
        if not self.permitted_organizations.exists():
            return True
        org_id = getattr(user, "organization_id", None)
        return bool(org_id) and self.permitted_organizations.filter(id=org_id).exists()

    def has_permission(self, user):
        """
        Giriş YALNIZ fərdi (permitted_users) əsasında verilir.
        permitted_organizations giriş vermir — sadəcə hansı qurumun user-lərinin
        permitted_users-ə əlavə oluna biləcəyini müəyyən edir (bax: is_user_eligible).
        """
        if not user or not user.is_authenticated:
            return False
        return self.permitted_users.filter(id=user.id).exists()

    def get_permitted_sub_modules(self, user):
        if not self.has_permission(user):
            return self.sub_modules.none()
        return [sm for sm in self.sub_modules.all() if sm.has_permission(user)]


class SubModule(TimestampsModel):
    module = models.ForeignKey(
        Module, on_delete=models.CASCADE, related_name="sub_modules", verbose_name="Əsas modul"
    )
    title = models.CharField(max_length=120, verbose_name="Alt modul adı")
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(verbose_name="Alt modul təsviri", null=True, blank=True)
    permitted_users = models.ManyToManyField(
        "authentication.User", related_name="sub_modules", blank=True,
        verbose_name="Fərdi icazəli istifadəçilər"
    )
    permitted_organizations = models.ManyToManyField(
        "authentication.Organization", related_name="sub_modules", blank=True,
        verbose_name="Əlaqəli qurumlar (əhatə dairəsi)",
        help_text=(
            "Yalnız hansı qurum(lar)ın işçilərinin 'Fərdi icazəli istifadəçilər' "
            "sahəsinə əlavə oluna biləcəyini məhdudlaşdırır. Tək başına giriş vermir."
        )
    )
    url_endpoint = models.CharField(max_length=120, verbose_name="Url linki")
    image = models.ImageField(
        upload_to='sub_module_images/%Y/%m/%d', null=True, blank=True, verbose_name="Alt modul ikonu"
    )

    def __str__(self):
        return "%s / %s" % (self.module.title, self.title)

    class Meta:
        verbose_name = "Alt Modul"
        verbose_name_plural = "Alt Modullar"
        unique_together = ("module", "title")

    def is_user_eligible(self, user):
        if not self.permitted_organizations.exists():
            return True
        org_id = getattr(user, "organization_id", None)
        return bool(org_id) and self.permitted_organizations.filter(id=org_id).exists()

    def has_permission(self, user):
        """
        Alt modula giriş üçün: əsas modula da fərdi icazə olmalıdır (permitted_users
        vasitəsilə), VƏ bu alt modula da fərdi icazə olmalıdır. Qurum sahəsi
        (permitted_organizations) yalnız namizədliyi məhdudlaşdırır, giriş vermir.
        """
        if not user or not user.is_authenticated:
            return False
        if not self.module.has_permission(user):
            return False
        return self.permitted_users.filter(id=user.id).exists()

class Status(TimestampsModel):

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"

    INVOICE_STATUS_KEYS = [
        (PENDING, "Gözləmədə"),
        (COMPLETED, "Bitib"),
        (CANCELED, "Ləğv edilib"),
    ]

    code = models.CharField(max_length=128, default="PENDING", choices=INVOICE_STATUS_KEYS,
                             verbose_name="Statusun kodu")
    title = models.CharField(max_length=128, verbose_name="Statusun adı", null=True, blank=True,)
    color = models.CharField(max_length=128, verbose_name="Statusun rəngi", null=True, blank=True,)

    class Meta:
        verbose_name = "Status"
        verbose_name_plural = "Statuslar"

    def __str__(self):
        return "%s - %s" % (self.title, self.code)