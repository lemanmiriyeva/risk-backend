
"""
Bu app-a xas skop/icazə yoxlamaları. core/permissions.py-dəki generic Module/SubModule
sistemi ilə QARIŞDIRILMIR - bu modul həmin sistemdən asılı deyil, sırf Role.is_manager_role,
Department.manager və User.is_apparatus_head sahələrinə əsaslanır.
"""


def is_department_manager(user):
    """
    Şöbə müdiri = (Role.is_manager_role=True) VƏ YA (öz idarə etdiyi departamentin
    Department.manager sahəsi məhz bu user-dirsə).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "role_id", None) and getattr(user.role, "is_manager_role", False):
        return True

    if user.department_id and user.department.manager_id == user.id:
        return True

    return False


def is_apparatus_head(user):
    """Aparat rəhbəri - qurumun icazələri son təsdiqləyən rəhbər şəxsi (vəzifə adından asılı olmayaraq)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser or getattr(user, "is_apparatus_head", False))


def get_visible_queryset(user, queryset):
    """
    GET (list) üçün: user-in roluna görə görə biləcəyi sorğuları filtrləyir.
    """
    if user.is_superuser:
        return queryset

    if is_apparatus_head(user):
        if not user.organization_id:
            return queryset.none()
        return queryset.filter(organization_id=user.organization_id)

    if is_department_manager(user):
        if not user.department_id:
            return queryset.filter(user=user)
        return queryset.filter(
            department_id=user.department_id,
            organization_id=user.organization_id,
        )

    return queryset.filter(user=user)


def can_review(user, permission_obj):
    """
    Təsdiq/rədd üçün: (icazə var mı, xəta_mesajı) formatında qaytarır.
    xəta_mesajı None-dursa icazə var deməkdir.
    """
    if user.is_superuser:
        return True, None

    if is_apparatus_head(user):
        if permission_obj.organization_id != user.organization_id:
            return False, "Bu icazə sizin qurumunuza aid deyil."
        return True, None

    if is_department_manager(user):
        if permission_obj.user_id == user.id:
            return False, "Öz icazənizi özünüz təsdiqləyə/rədd edə bilməzsiniz - bu, Aparat rəhbərinin səlahiyyətindədir."
        if permission_obj.department_id != user.department_id or permission_obj.organization_id != user.organization_id:
            return False, "Bu icazə sizin departamentinizə aid deyil."
        return True, None

    return False, "İcazəniz yoxdur."