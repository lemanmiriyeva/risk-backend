"""
Təlimlər modulu üçün icazələr.

Modul quruluşu (bax: core.Module / core.SubModule, seed: core/management/commands/seed_modules.py):

    trainings (Təlimlər)
      ├── training_materials  (Təlim materialları)  - video, quiz, rəy
      └── training_statistics (Təlim statistikası) - baxış, quiz və rəy statistikası

Hər alt modulun GİRİŞİ (kim görür) və ADMİNİ (kim idarə edir) ayrı-ayrılıqda
təyin olunur (SubModule.permitted_users / SubModule.admin_users). Ona görə
"materiallar"ın admini ilə "statistika"nın admini fərqli şəxslər ola bilər, və
modula icazəsi olmayan istifadəçi bu bölmələri ümumiyyətlə görmür.
"""
from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from authentication.models import User
from authentication.permissions import HasSystemAccess
from core.models import SubModule
from core.permissions import ModuleAccessPermission, is_sub_module_admin

TRAININGS_MODULE_CODE = "trainings"
MATERIALS_SUB_MODULE_CODE = "training_materials"
STATISTICS_SUB_MODULE_CODE = "training_statistics"


def can_manage_materials(user):
    return is_sub_module_admin(user, TRAININGS_MODULE_CODE, MATERIALS_SUB_MODULE_CODE)


def can_manage_statistics(user):
    return is_sub_module_admin(user, TRAININGS_MODULE_CODE, STATISTICS_SUB_MODULE_CODE)


def _has_sub_module_access(user, sub_module_code):
    sub = SubModule.objects.select_related("module").filter(
        module__code=TRAININGS_MODULE_CODE, code=sub_module_code
    ).first()
    return bool(sub and sub.has_permission(user))


def can_view_materials(user):
    return _has_sub_module_access(user, MATERIALS_SUB_MODULE_CODE)


def can_view_statistics(user):
    return _has_sub_module_access(user, STATISTICS_SUB_MODULE_CODE)


class _SubModuleAccess(BasePermission):
    sub_module_code = None
    message = "Bu bölməyə giriş icazəniz yoxdur."

    def has_permission(self, request, view):
        if not HasSystemAccess().has_permission(request, view):
            return False
        # ModuleAccessPermission view-dan module_code / sub_module_code oxuyur.
        view.module_code = TRAININGS_MODULE_CODE
        view.sub_module_code = self.sub_module_code
        return ModuleAccessPermission().has_permission(request, view)


class TrainingMaterialsPermission(_SubModuleAccess):
    """
    Baxış (GET) və istifadəçi əməliyyatları (videoya baxış, quiz göndərmə, rəy) -
    "Təlim materialları" alt moduluna girişi olan hər kəs.
    Yaratma/redaktə/silmə və quiz tərtibi - yalnız bu alt modulun admini.

    View öz "istifadəçi" action-larını `user_actions` siyahısında elan edir ki,
    POST olsalar da admin səlahiyyəti tələb olunmasın.
    """

    sub_module_code = MATERIALS_SUB_MODULE_CODE

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) in getattr(view, "user_actions", ()):
            return True
        return can_manage_materials(request.user)


class TrainingStatisticsPermission(_SubModuleAccess):
    """
    Baxış - "Təlim statistikası" alt moduluna girişi olan hər kəs.
    Dəyişiklik (məs. istifadəçinin baxış qeydini sıfırlamaq, quiz cəhdini silmək) -
    yalnız bu alt modulun admini.
    """

    sub_module_code = STATISTICS_SUB_MODULE_CODE

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return can_manage_statistics(request.user)


def org_scope_q(user, field="organization"):
    """Superuser hər şeyi görür; digərləri öz qurumunun + ümumi (null) yazılarını."""
    if user.is_superuser:
        return Q()
    org_id = getattr(user, "organization_id", None)
    return Q(**{f"{field}_id": org_id}) | Q(**{f"{field}__isnull": True})


def statistics_user_scope(user):
    """Statistikada görünən istifadəçilər: superuser - hamı, digərləri - öz qurumu."""
    qs = User.objects.all()
    if user.is_superuser:
        return qs
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return qs.none()
    return qs.filter(organization_id=org_id)


def materials_audience_user_ids(training=None):
    """
    "Təlim materialları" alt moduluna girişi olan (yəni təlimə baxmalı olan)
    aktiv istifadəçilərin id-ləri. `SubModule.has_permission` qaydalarını
    istifadəçi-istifadəçi yoxlamaq əvəzinə toplu sorğularla təkrarlayır.

    `training.organization` təyin olunubsa, yalnız həmin qurumun işçiləri.
    """
    sub = SubModule.objects.select_related("module").filter(
        module__code=TRAININGS_MODULE_CODE, code=MATERIALS_SUB_MODULE_CODE
    ).first()
    if not sub:
        return set()
    module = sub.module

    users = User.objects.filter(is_active=True)
    if training is not None and training.organization_id:
        users = users.filter(organization_id=training.organization_id)

    if module.is_public:
        return set(users.exclude(is_superuser=True).values_list("id", flat=True))

    module_admin_ids = set(module.admin_users.values_list("id", flat=True))
    module_org_ids = set(module.permitted_organizations.values_list("id", flat=True))
    sub_org_ids = set(sub.permitted_organizations.values_list("id", flat=True))

    module_access = users.filter(
        Q(is_superuser=True)
        | Q(is_org_admin=True, organization_id__in=module_org_ids)
        | Q(id__in=module_admin_ids)
        | Q(id__in=module.permitted_users.values("id"))
    )
    sub_access = module_access.filter(
        Q(is_superuser=True)
        | Q(is_org_admin=True, organization_id__in=sub_org_ids)
        | Q(id__in=module_admin_ids)
        | Q(id__in=sub.admin_users.values("id"))
        | Q(id__in=sub.permitted_users.values("id"))
    )
    # Superuser-lər sistem adminidir, "təlimə baxmalı olan" auditoriyaya daxil edilmir.
    return set(sub_access.exclude(is_superuser=True).values_list("id", flat=True))
