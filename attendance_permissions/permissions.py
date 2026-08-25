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

# Sorğunu YARADAN şəxsin öz vəzifə sırasına (Role.order) görə hansı təsdiq
# axınından keçəcəyini müəyyən edir. Səbəb: şöbə müdiri/departament rəhbəri
# səviyyəsində olan şəxslər öz sorğusunu özü təsdiqləyə bilməz (can_review bunu
# artıq qadağan edir), ona görə həmin mərhələ ümumiyyətlə keçilməlidir.
#
#   order == 1         -> avtomatik təsdiqlənir, heç bir mərhələ yoxdur
#   order 2, 3 və ya 4  -> yalnız Aparat rəhbəri təsdiqləyir (şöbə müdiri mərhələsi keçilir)
#   order > 4 / rol yox -> normal 2 mərhələli axın (şöbə müdiri -> Aparat rəhbəri)
AUTO_APPROVE_ROLE_ORDER = 1
SKIP_DEPARTMENT_MAX_ROLE_ORDER = 4

FLOW_AUTO = "auto"
FLOW_APPARATUS_ONLY = "apparatus_only"
FLOW_FULL = "full"


def get_role_order(user):
    if not user or not getattr(user, "role_id", None):
        return None
    return getattr(user.role, "order", None)


def get_approval_flow(user):
    """
    Yeni icazə sorğusu yaradılanda hansı təsdiq axınının istifadə olunacağını
    sorğunu yaradan user-in vəzifə sırasına (Role.order) əsasən qaytarır.
    Qaytarır: FLOW_AUTO | FLOW_APPARATUS_ONLY | FLOW_FULL
    """
    order = get_role_order(user)
    if order == AUTO_APPROVE_ROLE_ORDER:
        return FLOW_AUTO
    if order is not None and 2 <= order <= SKIP_DEPARTMENT_MAX_ROLE_ORDER:
        return FLOW_APPARATUS_ONLY
    return FLOW_FULL


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


def get_department_descendant_ids(department):
    """
    Verilən departamentin öz id-si + bütün alt-şöbələrinin (children, nəvə-şöbələr də daxil)
    id-lərini qaytarır. Departament rəhbəri/direktoru yalnız öz department_id-sinə DEQIQ bərabər
    olan sorğuları deyil, öz iyerarxiyasındakı bütün alt-şöbələrin sorğularını da görməlidir.
    """
    ids = [department.id]
    for child in department.children.all():
        ids += get_department_descendant_ids(child)
    return ids


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
        department_ids = get_department_descendant_ids(user.department)
        return queryset.filter(
            department_id__in=department_ids,
            organization_id=user.organization_id,
        )

    return queryset.filter(user=user)


def get_department_manager(department):
    """
    Bildiriş göndərmək üçün: departamentin rəhbərini tapır.
    Əvvəlcə departamentin özündə axtarır (Department.manager, olmasa rolu manager olan işçi);
    tapılmasa YUXARI (parent) departamentlərə qalxaraq davam edir - çünki alt-şöbənin öz
    rəhbəri təyin olunmaya bilər, bu halda əsl rəhbər üst departamentin direktorudur.
    """
    from authentication.models import User

    current = department
    while current:
        if current.manager_id:
            return current.manager
        manager = User.objects.filter(department=current, role__is_manager_role=True, is_active=True).first()
        if manager:
            return manager
        current = current.parent
    return None


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
    from .models import AttendancePermission

    if permission_obj.status not in (
        AttendancePermission.STATUS_PENDING,
        AttendancePermission.STATUS_AWAITING_APPARATUS,
    ):
        return False, "Bu sorğuya artıq baxılıb, statusu dəyişdirilə bilməz."

    if user.is_superuser:
        return True, None

    if permission_obj.status == AttendancePermission.STATUS_PENDING:

        reviewer = get_configured_department_reviewer(
            permission_obj.department
        )

        if not reviewer:
            return False, (
                "Bu departament üçün icazə təsdiqləyicisi təyin edilməyib."
            )

        if reviewer.id != user.id:
            return False, (
                "Bu mərhələdə icazəyə yalnız təyin olunmuş "
                "şöbə müdiri və ya əvəzləyici baxa bilər."
            )

        if permission_obj.organization_id != user.organization_id:
            return False, "Bu icazə sizin qurumunuza aid deyil."

        return True, None

    # AWAITING_APPARATUS

    if not is_apparatus_head_enabled(permission_obj.organization):
        return False, (
            "Bu qurum üçün Aparat rəhbəri təsdiqi deaktiv edilib."
        )

    apparatus_head = get_configured_apparatus_head(
        permission_obj.organization
    )

    if not apparatus_head:
        return False, (
            "Bu qurum üçün Aparat rəhbəri təyin edilməyib."
        )

    if apparatus_head.id != user.id:
        return False, (
            "Bu mərhələdə sorğuya yalnız Aparat rəhbəri baxa bilər."
        )

    if permission_obj.organization_id != user.organization_id:
        return False, "Bu icazə sizin qurumunuza aid deyil."

    return True, None

def can_manage_attendance_permission_config(user):
    """
    İcazə konfiqurasiyasını yalnız:
      - superuser
      - öz qurumunun admini
    dəyişə bilər.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser:
        return True

    return bool(
        getattr(user, "is_org_admin", False)
        and getattr(user, "organization_id", None)
    )


def get_attendance_organization_config(organization):
    from .models import AttendancePermissionOrganizationConfig

    if not organization:
        return None

    config, _ = AttendancePermissionOrganizationConfig.objects.get_or_create(
        organization=organization,
        defaults={
            "apparatus_head_enabled": True,
        },
    )

    return config


def is_apparatus_head_enabled(organization):
    config = get_attendance_organization_config(organization)

    if not config:
        return True

    return config.apparatus_head_enabled


def get_configured_apparatus_head(organization):
    """
    Config-də seçilmiş Aparat rəhbərini qaytarır.
    Config yoxdursa mövcud köhnə mexanizmə fallback edir.
    """

    if not organization:
        return None

    config = get_attendance_organization_config(organization)

    if config and not config.apparatus_head_enabled:
        return None

    if config and config.apparatus_head_id:
        return config.apparatus_head

    return get_apparatus_head(organization)


def get_configured_department_reviewer(department):
    """
    Departament üçün workflow-da birinci mərhələdə baxacaq şəxsi qaytarır.

    manager_enabled=True:
        Department.manager

    manager_enabled=False:
        replacement_user
    """

    if not department:
        return None

    config = getattr(
        department,
        "attendance_permission_config",
        None,
    )

    if not config:
        return get_department_manager(department)

    if config.manager_enabled:
        return get_department_manager(department)

    return config.replacement_user
