from rest_framework.permissions import BasePermission, SAFE_METHODS

# Risk Reyestri ilə əlaqəli BÜTÜN icazələr - giriş məhdudiyyəti üçün istifadə olunur
RISK_RELATED_PERMISSIONS = [
    'risk.view_risk',
    'risk.add_risk',
    'risk.change_risk',
    'risk.delete_risk',
    'risk.view_risklog',
]


def user_has_any_risk_access(user):
    """
    İstifadəçinin Risk Reyestri ilə (risklər VƏ YA loqlar) bağlı
    heç olmasa bir icazəsi varmı? superuser həmişə True qaytarır.
    Login zamanı çağırılmaq üçün nəzərdə tutulub.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    return any(user.has_perm(p) for p in RISK_RELATED_PERMISSIONS)


class RiskPermission(BasePermission):
    """
    HTTP metodlarını Risk modelinin standart Django icazələrinə uyğunlaşdırır:
      GET/HEAD/OPTIONS  -> risks.view_risk
      POST              -> risks.add_risk
      PUT/PATCH         -> risks.change_risk
      DELETE            -> risks.delete_risk

    İstifadəçinin bu icazələri Group (vəzifə) və ya birbaşa user_permissions
    üzərindən alması kifayətdir - admin panelindən idarə olunur.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return user.has_perm('risk.view_risk')
        if request.method == 'POST':
            return user.has_perm('risk.add_risk')
        if request.method in ('PUT', 'PATCH'):
            return user.has_perm('risk.change_risk')
        if request.method == 'DELETE':
            return user.has_perm('risk.delete_risk')
        return False

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)