from rest_framework.permissions import BasePermission
from core.permissions import user_has_any_module_access


class HasSystemAccess(BasePermission):
    message = "Bu sistemə giriş icazəniz yoxdur. Zəhmət olmasa sistem administratoru ilə əlaqə saxlayın."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not user.two_fa_confirmed:
            return False
        if not user.is_approved:
            return False
        return user_has_any_module_access(user)