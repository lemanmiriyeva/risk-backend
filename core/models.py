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
    permitted_users = models.ManyToManyField(
        "authentication.User", related_name="modules", blank=True,
        verbose_name="Fərdi icazəli istifadəçilər"
    )
    permitted_organizations = models.ManyToManyField(
        "authentication.Organization", related_name="modules", blank=True,
        verbose_name="İcazəli qurumlar"
    )
    url_endpoint = models.CharField(max_length=120, verbose_name="Url linki")
    image = models.ImageField(upload_to='module_images/%Y/%m/%d', null=True, blank=True, verbose_name="Modul ikonu")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Modul"
        verbose_name_plural = "Modullar"

    def has_permission(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.permitted_users.filter(id=user.id).exists():
            return True
        org_id = getattr(user, "organization_id", None)
        if org_id and self.permitted_organizations.filter(id=org_id).exists():
            return True
        return False

    def get_permitted_sub_modules(self, user):
        if not self.has_permission(user):
            return self.sub_modules.none()
        return [sm for sm in self.sub_modules.all() if sm.has_permission(user)]


class SubModule(TimestampsModel):
    module = models.ForeignKey(
        Module, on_delete=models.CASCADE, related_name="sub_modules", verbose_name="Əsas modul"
    )
    title = models.CharField(max_length=120, verbose_name="Alt modul adı")
    description = models.TextField(verbose_name="Alt modul təsviri", null=True, blank=True)
    permitted_users = models.ManyToManyField(
        "authentication.User", related_name="sub_modules", blank=True,
        verbose_name="Fərdi icazəli istifadəçilər"
    )
    permitted_organizations = models.ManyToManyField(
        "authentication.Organization", related_name="sub_modules", blank=True,
        verbose_name="İcazəli qurumlar"
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

    def has_permission(self, user):
        if not self.module.has_permission(user):
            return False
        if not user or not user.is_authenticated:
            return False
        if self.permitted_users.filter(id=user.id).exists():
            return True
        org_id = getattr(user, "organization_id", None)
        if org_id and self.permitted_organizations.filter(id=org_id).exists():
            return True
        return False

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