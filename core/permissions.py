import logging
from django.db.models import Q
from rest_framework.permissions import BasePermission

from .models import Module, SubModule

logger = logging.getLogger('colored')


# ---------------------------------------------------------------------------
# Helper funksiyalar (2FA, serializer, HasSystemAccess tərəfindən istifadə olunur)
# ---------------------------------------------------------------------------

def get_user_modules(user):
    """İstifadəçinin icazəli olduğu modullar (fərdi VƏ YA qurum əsaslı)."""
    if not user or not user.is_authenticated:
        return Module.objects.none()

    q = Q(permitted_users=user)
    org_id = getattr(user, "organization_id", None)
    if org_id:
        q |= Q(permitted_organizations=org_id)

    return Module.objects.filter(q).distinct()


def get_user_sub_modules(user, module=None):
    """İstifadəçinin icazəli olduğu alt modullar (əsas modula da icazəsi olmalıdır)."""
    if not user or not user.is_authenticated:
        return SubModule.objects.none()

    permitted_module_ids = get_user_modules(user).values_list("id", flat=True)

    q = Q(permitted_users=user)
    org_id = getattr(user, "organization_id", None)
    if org_id:
        q |= Q(permitted_organizations=org_id)

    qs = SubModule.objects.filter(q, module_id__in=permitted_module_ids).distinct()
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

class ModuleAccessPermission(BasePermission):
    """
    ViewSet-də module_name (məcburi) və sub_module_name (istəyə görə) təyin et:

        class RiskViewSet(ModelViewSet):
            permission_classes = [ModuleAccessPermission]
            module_name = "Risk"
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        module_name = getattr(view, 'module_name', None)
        if not module_name:
            return False

        try:
            module = Module.objects.get(title__iexact=module_name)
        except Module.DoesNotExist:
            logger.error(f"Module {module_name} does not exist.")
            return False

        if not module.has_permission(request.user):
            return False

        sub_module_name = getattr(view, 'sub_module_name', None)
        if sub_module_name:
            try:
                sub_module = SubModule.objects.get(module=module, title__iexact=sub_module_name)
            except SubModule.DoesNotExist:
                logger.error(f"SubModule {sub_module_name} does not exist under {module_name}.")
                return False
            return sub_module.has_permission(request.user)

        return True

