from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.permissions import ModuleAccessPermission, is_module_admin

BULLETIN_MODULE_CODE = "bulletin"


class BulletinEditorPermission(BasePermission):
    """
    Baxış (GET/HEAD/OPTIONS) - modula girişi olan HƏR KƏS üçün açıqdır
    (bax: `ModuleAccessPermission` / `Module.has_permission`).

    Yaratma/redaktə/silmə - yalnız superuser, qurum admini, ya da bu modulun
    admini (bax: Module.admin_users / core.permissions.is_module_admin) üçün.
    """

    def has_permission(self, request, view):
        if not ModuleAccessPermission().has_permission(request, view):
            return False

        if request.method in SAFE_METHODS:
            return True

        user = request.user
        return bool(
            user.is_superuser
            or getattr(user, "is_org_admin", False)
            or is_module_admin(user, BULLETIN_MODULE_CODE)
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return self.has_permission(request, view)

class BulletinCategoryPermission(BasePermission):
    """
    Kateqoriyalara (Sərəncam/Fərman/Daxili qayda növləri) BAXIŞ - modula
    girişi olan hər kəs üçün.

    Yeni kateqoriya ƏLAVƏ ETMƏK / redaktə / silmək - YALNIZ bu modulun
    təyin edilmiş admini (Module.admin_users) və superuser üçün.

    Diqqət: `BulletinEditorPermission`-dan fərqli olaraq burada qurum admini
    (is_org_admin) KİFAYƏT DEYİL - kateqoriya siyahısı bütün qurumlar üçün
    ortaq olduğundan, onu yalnız modulun öz admini idarə etməlidir.
    """

    def has_permission(self, request, view):
        if not ModuleAccessPermission().has_permission(request, view):
            return False

        if request.method in SAFE_METHODS:
            return True

        return bool(is_module_admin(request.user, BULLETIN_MODULE_CODE))

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return self.has_permission(request, view)
