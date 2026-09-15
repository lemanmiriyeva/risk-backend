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
            "Bu sahədəki qurumun ADMİNİ (is_org_admin) modula AVTOMATİK giriş əldə edir. "
            "Qurumun adi işçiləri isə avtomatik giriş almır - onlara giriş yalnız "
            "'Fərdi icazəli istifadəçilər' (permitted_users) sahəsi ilə (və ya qurum "
            "admininin admin panelindən) verilir."
        )
    )
    admin_users = models.ManyToManyField(
        "authentication.User", related_name="administered_modules", blank=True,
        verbose_name="Modul adminləri (əlavə/redaktə icazəli)",
        help_text=(
            "Bu modul daxilində məzmun əlavə etmək/redaktə etmək səlahiyyəti olan "
            "istifadəçilər. Modul admini avtomatik olaraq modula giriş də əldə edir "
            "(permitted_users-a əlavə edilməsinə ehtiyac yoxdur). Konkret app-larda "
            "bu, `core.permissions.is_module_admin(user, module_code)` vasitəsilə "
            "yoxlanılıb 'add'/'change' səlahiyyəti kimi tətbiq oluna bilər."
        ),
    )
    url_endpoint = models.CharField(max_length=120, verbose_name="Url linki")
    image = models.ImageField(upload_to='module_images/%Y/%m/%d', null=True, blank=True, verbose_name="Modul ikonu")
    is_public = models.BooleanField(
        default=False, verbose_name="Hər kəsə açıq",
        help_text=(
            "Aktiv edilsə, bu modul VƏ onun bütün alt modulları qurum/istifadəçi "
            "icazələrindən asılı olmayaraq bütün autentifikasiya olunmuş istifadəçilərə "
            "görünür və açıq olur."
        ),
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Modul"
        verbose_name_plural = "Modullar"

    def is_user_eligible(self, user):
        if self.is_public:
            return True
        if not self.permitted_organizations.exists():
            return True
        org_id = getattr(user, "organization_id", None)
        return bool(org_id) and self.permitted_organizations.filter(id=org_id).exists()

    def is_admin_user(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return self.admin_users.filter(id=user.id).exists()

    def has_permission(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if self.is_public:
            return True
        if getattr(user, "is_org_admin", False):
            org_id = getattr(user, "organization_id", None)
            if org_id and self.permitted_organizations.filter(id=org_id).exists():
                return True
        if self.admin_users.filter(id=user.id).exists():
            return True
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
            "Bu sahədəki qurumun ADMİNİ (is_org_admin) alt-modula AVTOMATİK giriş əldə edir "
            "(əsas modula da girişi olduğu halda). Qurumun adi işçiləri isə avtomatik giriş "
            "almır - onlara giriş yalnız 'Fərdi icazəli istifadəçilər' (permitted_users) sahəsi "
            "ilə (və ya qurum admininin admin panelindən) verilir."
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
        if self.module.is_public:
            return True
        if not self.permitted_organizations.exists():
            return True
        org_id = getattr(user, "organization_id", None)
        return bool(org_id) and self.permitted_organizations.filter(id=org_id).exists()

    def has_permission(self, user):
        if not user or not user.is_authenticated:
            return False
        # Modul "hər kəsə açıq" (is_public) olaraq işarələnibsə, əsas modulla
        # birlikdə bütün alt modulları da avtomatik hər kəsə açıq olur.
        if self.module.is_public:
            return True
        if not self.module.has_permission(user):
            return False
        if user.is_superuser:
            return True
        if getattr(user, "is_org_admin", False):
            org_id = getattr(user, "organization_id", None)
            if org_id and self.permitted_organizations.filter(id=org_id).exists():
                return True
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