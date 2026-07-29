import logging
from rest_framework.permissions import BasePermission

from .models import Module, SubModule

logger = logging.getLogger('colored')


# ---------------------------------------------------------------------------
# Helper funksiyalar (2FA, serializer, HasSystemAccess tərəfindən istifadə olunur)
# ---------------------------------------------------------------------------

def get_user_modules(user):
    """
    İstifadəçinin icazəli olduğu modullar.
    Giriş yalnız fərdi (permitted_users) əsasında verilir; permitted_organizations
    bir modulun hansı qurum(lar) üçün nəzərdə tutulduğunu göstərir (əhatə dairəsi),
    lakin tək başına o qurumun bütün user-lərinə giriş açmır.
    """
    if not user or not user.is_authenticated:
        return Module.objects.none()

    return Module.objects.filter(permitted_users=user).distinct()


def get_user_sub_modules(user, module=None):
    """İstifadəçinin icazəli olduğu alt modullar (əsas modula da fərdi icazəsi olmalıdır)."""
    if not user or not user.is_authenticated:
        return SubModule.objects.none()

    permitted_module_ids = get_user_modules(user).values_list("id", flat=True)

    qs = SubModule.objects.filter(
        permitted_users=user, module_id__in=permitted_module_ids
    ).distinct()
    if module is not None:
        qs = qs.filter(module=module)
    return qs


def user_has_any_module_access(user):
    if get_user_modules(user).exists():
        return True
    return get_user_sub_modules(user).exists()


def get_module_permissions(user):
    """Frontend/2FA üçün icazəli modul + alt-modul strukturu."""
    modules = get_user_modules(user)
    sub_modules_by_module = {}
    for sub in get_user_sub_modules(user).select_related("module"):
        sub_modules_by_module.setdefault(sub.module_id, []).append({
            "id": sub.id,
            "title": sub.title,
            "url_endpoint": sub.url_endpoint,
        })

    return [
        {
            "id": module.id,
            "title": module.title,
            "url_endpoint": module.url_endpoint,
            "sub_modules": sub_modules_by_module.get(module.id, []),
        }
        for module in modules
    ]


# ---------------------------------------------------------------------------
# DRF Permission class-ları
# ---------------------------------------------------------------------------

# authentication/permissions.py
class ModuleAccessPermission(BasePermission):
    """
    View-da aşağıdakılardan istənilən kombinasiyanı təyin et:

    1) Sadə tək submodul:
        module_code = "risk"
        sub_module_code = "risk_register"

    2) Bir neçə submoduldan HƏR HANSI BİRİ kifayətdir (OR):
        module_code = "risk"
        sub_module_codes = ["risk_register", "risk_view_table"]

    3) Əməliyyata (action) görə fərqli submodul tələbi:
        module_code = "risk"
        action_sub_module_codes = {
            "list": ["risk_register", "risk_view_table"],
            "retrieve": ["risk_register", "risk_view_table"],
            "create": ["risk_register"],
            "update": ["risk_register"],
            "partial_update": ["risk_register"],
            "destroy": ["risk_register"],
        }
        # təyin olunmayan action-lar üçün sub_module_code/sub_module_codes fallback kimi işlənir
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        module_code = getattr(view, 'module_code', None)
        if not module_code:
            return False

        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            logger.error(f"Module code='{module_code}' does not exist.")
            return False

        required_codes = self._resolve_required_sub_module_codes(view)

        if not required_codes:
            # heç bir submodul tələbi yoxdursa - sadəcə modula icazə kifayətdir
            return module.has_permission(request.user)

        for code in required_codes:
            try:
                sub_module = SubModule.objects.get(module=module, code=code)
            except SubModule.DoesNotExist:
                logger.error(f"SubModule code='{code}' does not exist under '{module_code}'.")
                continue
            if sub_module.has_permission(request.user):
                return True   # HƏR HANSI BİRİNƏ icazə varsa kifayətdir

        return False

    def _resolve_required_sub_module_codes(self, view):
        action = getattr(view, 'action', None)

        action_map = getattr(view, 'action_sub_module_codes', None)
        if action_map and action in action_map:
            return action_map[action]

        codes = getattr(view, 'sub_module_codes', None)
        if codes:
            return codes

        single = getattr(view, 'sub_module_code', None)
        if single:
            return [single]

        return []
# ---------------------------------------------------------------------------
# Qurum admini (is_org_admin) - öz qurumunu idarəetmə üçün helper-lər
# ---------------------------------------------------------------------------

class IsOrgAdmin(BasePermission):
    """
    request.user ya superuser, ya da is_org_admin=True olmalıdır.
    Superuser bütün qurumları, org admin isə YALNIZ öz qurumunu idarə edə bilər
    (view içində get_managed_organization() ilə təyin olunur).
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_superuser or user.is_org_admin)


def get_managed_organization(request):
    """
    Sorğunu edən user-in idarə etdiyi qurumu qaytarır:
      - is_org_admin (superuser deyil) -> öz `organization`-u (başqasını seçə bilməz)
      - superuser -> ?organization=<id> query param-ı ilə istənilən qurum
    Qurum tapılmasa/icazə yoxdursa None qaytarır (view 400/403 qaytarmalıdır).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        org_id = request.query_params.get("organization") or request.data.get("organization")
        if not org_id:
            return None
        from authentication.models import Organization
        return Organization.objects.filter(id=org_id).first()

    if user.is_org_admin:
        return user.organization

    return None