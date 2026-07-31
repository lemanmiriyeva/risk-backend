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
        Giriş qaydaları:
          - Root (superuser): HƏMİŞƏ giriş var - bütün modullar avtomatik açıqdır.
          - Qurum admini (is_org_admin): qurumu bu modulun `permitted_organizations`
            sahəsindədirsə, AVTOMATİK giriş var (fərdi permitted_users qeydinə ehtiyac yoxdur).
          - Adi istifadəçi: YALNIZ fərdi (permitted_users) əsasında giriş var.
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if getattr(user, "is_org_admin", False):
            org_id = getattr(user, "organization_id", None)
            if org_id and self.permitted_organizations.filter(id=org_id).exists():
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
        if not self.permitted_organizations.exists():
            return True
        org_id = getattr(user, "organization_id", None)
        return bool(org_id) and self.permitted_organizations.filter(id=org_id).exists()

    def has_permission(self, user):
        """
        Giriş qaydaları (əsas modula da giriş şərtdir):
          - Root (superuser): HƏMİŞƏ giriş var.
          - Qurum admini: qurumu bu alt-modulun `permitted_organizations` sahəsindədirsə,
            AVTOMATİK giriş var (fərdi permitted_users qeydinə ehtiyac yoxdur).
          - Adi istifadəçi: YALNIZ fərdi (permitted_users) əsasında giriş var.
        """
        if not user or not user.is_authenticated:
            return False
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