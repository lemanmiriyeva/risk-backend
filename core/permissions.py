import logging
from django.db.models import Q
from rest_framework.permissions import BasePermission

from .models import Module, SubModule

logger = logging.getLogger('colored')

def get_user_modules(user):
    if not user or not user.is_authenticated:
        return Module.objects.none()

    if user.is_superuser:
        return Module.objects.all()

    if getattr(user, "is_org_admin", False) and getattr(user, "organization_id", None):
        return Module.objects.filter(
            Q(permitted_users=user) | Q(permitted_organizations=user.organization_id)
        ).distinct()

    return Module.objects.filter(permitted_users=user).distinct()


def get_user_sub_modules(user, module=None):
    if not user or not user.is_authenticated:
        return SubModule.objects.none()

    permitted_module_ids = get_user_modules(user).values_list("id", flat=True)

    if user.is_superuser:
        qs = SubModule.objects.filter(module_id__in=permitted_module_ids)
    elif getattr(user, "is_org_admin", False) and getattr(user, "organization_id", None):
        qs = SubModule.objects.filter(
            Q(permitted_users=user) | Q(permitted_organizations=user.organization_id),
            module_id__in=permitted_module_ids,
        ).distinct()
    else:
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


class ModuleAccessPermission(BasePermission):

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

class IsOrgAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_superuser or user.is_org_admin)


def get_managed_organization(request):
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


def get_scoped_user(request, id):
    from rest_framework.response import Response
    from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND
    from authentication.models import User

    requester = request.user
    user = User.objects.filter(id=id).first()
    if not user:
        return None, Response({"detail": "İstifadəçi tapılmadı."}, status=HTTP_404_NOT_FOUND)

    if requester.is_superuser:
        return user, None

    if requester.is_org_admin:
        organization = get_managed_organization(request)
        if not organization:
            return None, Response({"detail": "İdarə etdiyiniz qurum təyin edilə bilmədi."}, status=HTTP_400_BAD_REQUEST)
        if user.organization_id != organization.id:
            return None, Response({"detail": "Bu istifadəçi sizin qurumunuza aid deyil."}, status=HTTP_403_FORBIDDEN)
        return user, None

    return None, Response({"detail": "İcazəniz yoxdur."}, status=HTTP_403_FORBIDDEN)