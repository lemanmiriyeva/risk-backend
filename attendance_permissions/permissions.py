"""
Bu app-a xas skop/icazə yoxlamaları. core/permissions.py-dəki generic Module/SubModule
sistemi ilə QARIŞDIRILMIR - bu modul həmin sistemdən asılı deyil.

Aparat rəhbəri təyini İKİ yolla ola bilər (hər hansı biri kifayətdir):
  1) User.is_apparatus_head = True (konkret şəxsə əl ilə verilən istisna səlahiyyət)
  2) User.role.order == APPARATUS_HEAD_ROLE_ORDER (2) - yəni "Aparat rəhbəri" vəzifəsinin
     özündə sıra nömrəsi 2 olaraq təyin olunub və bu vəzifədə olan HƏR KƏS avtomatik
     Aparat rəhbəri sayılır. Bu yolla hər yeni işçiyə ayrıca checkbox basmaq lazım qalmır -
     sadəcə admin panelində "Aparat rəhbəri" vəzifəsinin (Role) sırasını 2 edin, kifayətdir.

Şöbə müdiri isə Role.is_manager_role=True VƏ YA Department.manager sahəsinə əsaslanır.
"""

APPARATUS_HEAD_ROLE_ORDER = 2


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
    """Aparat rəhbəri - qurumun icazələri son təsdiqləyən rəhbər şəxsi (yuxarıdakı iki yoldan biri kifayətdir)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or getattr(user, "is_apparatus_head", False):
        return True
    return bool(user.role_id and getattr(user.role, "order", None) == APPARATUS_HEAD_ROLE_ORDER)


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


def get_department_manager(department):
    """Bildiriş göndərmək üçün: departamentin rəhbərini tapır (Department.manager, olmasa rolu manager olan işçi)."""
    if not department:
        return None
    if department.manager_id:
        return department.manager
    from authentication.models import User
    return User.objects.filter(department=department, role__is_manager_role=True, is_active=True).first()


def get_apparatus_head(organization):
    """
    Bildiriş göndərmək üçün: qurumun Aparat rəhbərini tapır.
    Prioritet: (1) is_apparatus_head=True olan konkret şəxs, (2) vəzifəsinin (Role) order-i 2 olan şəxs.
    """
    if not organization:
        return None
    from authentication.models import User

    explicit = User.objects.filter(
        organization=organization, is_apparatus_head=True, is_active=True,
    ).first()
    if explicit:
        return explicit

    return User.objects.filter(
        organization=organization, role__order=APPARATUS_HEAD_ROLE_ORDER, is_active=True,
    ).first()


def get_apparatus_head_fallback_recipients(organization):
    """
    Aparat rəhbəri tapılmadıqda (rol təyin olunmayıb) bildirişin heç kimə getməməsinin
    qarşısını almaq üçün ehtiyat siyahı: əvvəlcə qurum admini, sonra superuser-lər.
    """
    if not organization:
        return []
    from authentication.models import User
    org_admins = list(User.objects.filter(organization=organization, is_org_admin=True, is_active=True))
    if org_admins:
        return org_admins
    return list(User.objects.filter(is_superuser=True, is_active=True))


def can_review(user, permission_obj):
    """
    Təsdiq/rədd üçün: (icazə var mı, xəta_mesajı) formatında qaytarır.
    xəta_mesajı None-dursa icazə var deməkdir.

    İki mərhələli axın:
      - status=PENDING            -> yalnız şöbə müdiri (və ya superuser) baxa bilər
      - status=AWAITING_APPARATUS -> yalnız Aparat rəhbəri (və ya superuser) baxa bilər
      - digər statuslar (approved/rejected) -> artıq bağlanıb, heç kim baxa bilməz
    """
    from .models import AttendancePermission

    if permission_obj.status not in (
        AttendancePermission.STATUS_PENDING, AttendancePermission.STATUS_AWAITING_APPARATUS,
    ):
        return False, "Bu sorğuya artıq baxılıb, statusu dəyişdirilə bilməz."

    if user.is_superuser:
        return True, None

    if permission_obj.status == AttendancePermission.STATUS_PENDING:
        if not is_department_manager(user):
            return False, "Bu mərhələdə sorğuya yalnız şöbə müdiri baxa bilər."
        if permission_obj.user_id == user.id:
            return False, "Öz icazənizi özünüz təsdiqləyə/rədd edə bilməzsiniz - bu, Aparat rəhbərinin səlahiyyətindədir."
        if permission_obj.department_id != user.department_id or permission_obj.organization_id != user.organization_id:
            return False, "Bu icazə sizin departamentinizə aid deyil."
        return True, None

    # status == AWAITING_APPARATUS
    if not is_apparatus_head(user):
        return False, "Bu mərhələdə sorğuya yalnız Aparat rəhbəri baxa bilər."
    if permission_obj.organization_id != user.organization_id:
        return False, "Bu icazə sizin qurumunuza aid deyil."
    return True, None