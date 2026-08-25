import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from notifications.models import Notification
from notifications.services import notify

from .models import AttendancePermission

from .serializers import (
    AttendancePermissionSerializer,
    AttendancePermissionCreateSerializer,
    AttendancePermissionReviewSerializer,
)
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from authentication.models import User, Department

from .models import (
    AttendancePermissionOrganizationConfig,
    AttendancePermissionDepartmentConfig,
)

from .serializers import (
    AttendancePermissionOrganizationConfigSerializer,
    AttendancePermissionDepartmentConfigSerializer,
    AttendancePermissionUserShortSerializer,
)

from .permissions import (
    is_apparatus_head,
    can_review,
    get_visible_queryset,
    get_department_manager,
    get_apparatus_head,

    get_configured_department_reviewer,
    get_configured_apparatus_head,

    is_apparatus_head_enabled,

    get_approval_flow,

    FLOW_AUTO,
    FLOW_APPARATUS_ONLY,
    FLOW_FULL, can_manage_attendance_permission_config,
)
logger = logging.getLogger("colored")


class AttendancePermissionListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        user = request.user
        queryset = AttendancePermission.objects.select_related(
            "user", "department", "organization", "reviewed_by"
        ).all()

        status_filter = request.query_params.get("status")
        queryset = get_visible_queryset(user, queryset)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        logger.info(f"AttendancePermissionListCreateView.get - {user.username} icazə siyahısını sorğuladı")
        serializer = AttendancePermissionSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=HTTP_200_OK)

    def post(self, request):
        user = request.user

        if is_apparatus_head(user) and not user.is_superuser:
            return Response(
                {
                    "detail": (
                        "Aparat rəhbəri icazə sorğusu yarada bilməz - "
                        "yalnız təsdiq/rədd edə bilər."
                    )
                },
                status=HTTP_403_FORBIDDEN,
            )

        serializer = AttendancePermissionCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        flow = get_approval_flow(user)

        # ---------------------------------------------------------
        # İLK STATUSU MÜƏYYƏN EDİRİK
        # ---------------------------------------------------------

        if flow == FLOW_AUTO:
            initial_status = AttendancePermission.STATUS_APPROVED

        elif flow == FLOW_APPARATUS_ONLY:
            initial_status = AttendancePermission.STATUS_AWAITING_APPARATUS

        else:
            initial_status = AttendancePermission.STATUS_PENDING

        # ---------------------------------------------------------
        # INSTANCE BURADA YARADILIR
        # Bundan sonra instance istifadə etmək olar.
        # ---------------------------------------------------------

        instance = serializer.save(
            user=user,
            department=user.department,
            organization=user.organization,
            status=initial_status,
        )

        logger.info(
            f"AttendancePermissionListCreateView.post - "
            f"{user.username} yeni icazə sorğusu yaratdı "
            f"(id={instance.id}, axın={flow})"
        )

        # =========================================================
        # 1. AUTO
        # =========================================================

        if flow == FLOW_AUTO:

            instance.reviewed_at = timezone.now()
            instance.review_comment = (
                "Vəzifə sırasına görə avtomatik təsdiqləndi"
            )

            instance.save(
                update_fields=[
                    "reviewed_at",
                    "review_comment",
                ]
            )

            notify(
                user,
                title="İcazəniz avtomatik təsdiqləndi",
                body=(
                    f"{instance.date} tarixli icazə sorğunuz "
                    f"vəzifənizə görə avtomatik təsdiqləndi."
                ),
                notification_type=(
                    Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED
                ),
                link="/icazeler",
                related_app="attendance_permissions",
                related_object_id=instance.id,
            )

        # =========================================================
        # 2. APARAT RƏHBƏRİ YALNIZ
        # =========================================================

        elif flow == FLOW_APPARATUS_ONLY:

            # Config-dən Aparat rəhbərini götürürük
            apparatus_head = get_configured_apparatus_head(
                instance.organization
            )

            # -----------------------------------------------------
            # Aparat rəhbəri deaktivdirsə:
            # Bu mərhələni tamamilə keçirik.
            # Sorğu avtomatik təsdiqlənir.
            # -----------------------------------------------------

            if not is_apparatus_head_enabled(
                    instance.organization
            ):
                instance.status = AttendancePermission.STATUS_APPROVED
                instance.reviewed_at = timezone.now()
                instance.review_comment = (
                    "Aparat rəhbəri təsdiqi konfiqurasiyada deaktiv "
                    "edildiyi üçün avtomatik təsdiqləndi."
                )

                instance.save(
                    update_fields=[
                        "status",
                        "reviewed_at",
                        "review_comment",
                    ]
                )

                notify(
                    user,
                    title="İcazəniz təsdiqləndi",
                    body=(
                        f"{instance.date} tarixli icazə sorğunuz "
                        f"Aparat rəhbəri mərhələsi deaktiv olduğu üçün "
                        f"avtomatik təsdiqləndi."
                    ),
                    notification_type=(
                        Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED
                    ),
                    link="/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )

            # -----------------------------------------------------
            # Aparat rəhbəri aktivdir, amma seçilməyib
            # -----------------------------------------------------

            elif not apparatus_head:

                instance.status = AttendancePermission.STATUS_REJECTED
                instance.reviewed_at = timezone.now()
                instance.review_comment = (
                    "Bu qurum üçün aktiv Aparat rəhbəri "
                    "təyin edilməyib."
                )

                instance.save(
                    update_fields=[
                        "status",
                        "reviewed_at",
                        "review_comment",
                    ]
                )

                notify(
                    user,
                    title="İcazə sorğusu yaradıla bilmədi",
                    body=(
                        "Qurum üçün Aparat rəhbəri təyin edilmədiyi "
                        "üçün icazə sorğunuz emal edilə bilmədi."
                    ),
                    notification_type=(
                        Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED
                    ),
                    link="/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )

                return Response(
                    {
                        "detail": (
                            "Bu qurum üçün aktiv Aparat rəhbəri "
                            "təyin edilməyib."
                        )
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            # -----------------------------------------------------
            # Aparat rəhbəri var → notification
            # -----------------------------------------------------

            else:

                notify(
                    apparatus_head,
                    title="Təsdiq üçün icazə sorğusu",
                    body=(
                        f"{user.name} - {instance.date} tarixli "
                        f"icazə sorğusu birbaşa sizin təsdiqinizi "
                        f"gözləyir."
                    ),
                    notification_type=(
                        Notification.TYPE_ATTENDANCE_PERMISSION_DEPT_APPROVED
                    ),
                    link="/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )

        # =========================================================
        # 3. FULL
        # ŞÖBƏ MÜDİRİ → APARAT RƏHBƏRİ
        # =========================================================

        else:

            department_reviewer = get_configured_department_reviewer(
                instance.department
            )

            # -----------------------------------------------------
            # Şöbə müdiri / əvəzləyici yoxdur
            # -----------------------------------------------------

            if not department_reviewer:
                instance.status = AttendancePermission.STATUS_REJECTED
                instance.reviewed_at = timezone.now()
                instance.review_comment = (
                    "Departament üçün şöbə müdiri və ya "
                    "əvəzləyici təyin edilməyib."
                )

                instance.save(
                    update_fields=[
                        "status",
                        "reviewed_at",
                        "review_comment",
                    ]
                )

                notify(
                    user,
                    title="İcazə sorğusu yaradıla bilmədi",
                    body=(
                        "Departament üçün icazə təsdiqləyicisi "
                        "təyin edilməyib."
                    ),
                    notification_type=(
                        Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED
                    ),
                    link="/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )

                return Response(
                    {
                        "detail": (
                            "Bu departament üçün icazə "
                            "təsdiqləyicisi təyin edilməyib."
                        )
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            # -----------------------------------------------------
            # Şöbə müdiri / əvəzləyiciyə notification
            # -----------------------------------------------------

            notify(
                department_reviewer,
                title="Yeni icazə sorğusu",
                body=(
                    f"{user.name} {instance.date} tarixi üçün "
                    f"icazə sorğusu göndərdi."
                ),
                notification_type=(
                    Notification.TYPE_ATTENDANCE_PERMISSION_NEW
                ),
                link="/icazeler",
                related_app="attendance_permissions",
                related_object_id=instance.id,
            )

        # =========================================================
        # RESPONSE
        # =========================================================

        out = AttendancePermissionSerializer(
            instance,
            context={"request": request},
        )

        return Response(
            out.data,
            status=HTTP_201_CREATED,
        )
class AttendancePermissionDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request, id):
        user = request.user
        instance = get_object_or_404(AttendancePermission, id=id)

        visible = get_visible_queryset(user, AttendancePermission.objects.filter(id=id)).exists()
        if not visible:
            return Response({"detail": "İcazəniz yoxdur."}, status=HTTP_403_FORBIDDEN)

        serializer = AttendancePermissionSerializer(instance, context={"request": request})
        return Response(serializer.data, status=HTTP_200_OK)


class AttendancePermissionReviewView(APIView):
    """Şöbə müdiri (1-ci mərhələ) / Aparat rəhbəri (2-ci, son mərhələ) tərəfindən təsdiq və ya rədd."""
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def patch(self, request, id):
        user = request.user
        instance = get_object_or_404(AttendancePermission, id=id)

        allowed, error_message = can_review(user, instance)
        if not allowed:
            logger.info(f"AttendancePermissionReviewView.patch - {user.username} rədd edildi: {error_message}")
            return Response({"detail": error_message}, status=HTTP_403_FORBIDDEN)

        serializer = AttendancePermissionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        comment = serializer.validated_data.get("comment", "")
        now = timezone.now()

        if instance.status == AttendancePermission.STATUS_PENDING:

            # ---------------------------------------------------------
            # MƏRHƏLƏ 1
            # Şöbə müdiri / əvəzləyici
            # ---------------------------------------------------------

            instance.department_reviewed_by = user
            instance.department_reviewed_at = now
            instance.department_review_comment = comment

            if action == "approve":

                # =====================================================
                # APARAT RƏHBƏRİ DEAKTİVDİRSƏ
                # İKİNCİ MƏRHƏLƏNİ KEÇİRİB BİRBAŞA APPROVED
                # =====================================================

                if not is_apparatus_head_enabled(
                        instance.organization
                ):

                    instance.status = AttendancePermission.STATUS_APPROVED
                    instance.reviewed_by = user
                    instance.reviewed_at = now
                    instance.review_comment = (
                        "Şöbə müdiri tərəfindən təsdiqləndi. "
                        "Aparat rəhbəri mərhələsi konfiqurasiyada "
                        "deaktiv edilib."
                    )

                    instance.save(
                        update_fields=[
                            "status",
                            "department_reviewed_by",
                            "department_reviewed_at",
                            "department_review_comment",
                            "reviewed_by",
                            "reviewed_at",
                            "review_comment",
                        ]
                    )

                    notify(
                        instance.user,
                        title="İcazəniz təsdiqləndi",
                        body=(
                            f"{instance.date} tarixli icazə sorğunuz "
                            f"şöbə müdiri tərəfindən təsdiqləndi."
                        ),
                        notification_type=(
                            Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED
                        ),
                        link="/icazeler",
                        related_app="attendance_permissions",
                        related_object_id=instance.id,
                    )

                else:

                    # =================================================
                    # APARAT RƏHBƏRİ AKTİVDİR
                    # NORMAL İKİ MƏRHƏLƏ
                    # =================================================

                    apparatus_head = get_configured_apparatus_head(
                        instance.organization
                    )

                    if not apparatus_head:
                        return Response(
                            {
                                "detail": (
                                    "Aparat rəhbəri aktivdir, "
                                    "lakin heç bir Aparat rəhbəri "
                                    "təyin edilməyib."
                                )
                            },
                            status=HTTP_400_BAD_REQUEST,
                        )

                    instance.status = (
                        AttendancePermission.STATUS_AWAITING_APPARATUS
                    )

                    instance.save(
                        update_fields=[
                            "status",
                            "department_reviewed_by",
                            "department_reviewed_at",
                            "department_review_comment",
                        ]
                    )

                    notify(
                        apparatus_head,
                        title="Təsdiq üçün icazə sorğusu",
                        body=(
                            f"{instance.user.name} - {instance.date} "
                            f"tarixli icazə sorğusu şöbə müdiri tərəfindən "
                            f"təsdiqləndi, sizin təsdiqinizi gözləyir."
                        ),
                        notification_type=(
                            Notification.TYPE_ATTENDANCE_PERMISSION_DEPT_APPROVED
                        ),
                        link="/icazeler",
                        related_app="attendance_permissions",
                        related_object_id=instance.id,
                    )

            else:
                # -----------------------------------------------------
                # ŞÖBƏ MÜDİRİ RƏDD EDİB
                # -----------------------------------------------------

                instance.status = AttendancePermission.STATUS_REJECTED
                instance.reviewed_by = user
                instance.reviewed_at = now
                instance.review_comment = comment

                instance.save(
                    update_fields=[
                        "status",
                        "department_reviewed_by",
                        "department_reviewed_at",
                        "department_review_comment",
                        "reviewed_by",
                        "reviewed_at",
                        "review_comment",
                    ]
                )

                notify(
                    instance.user,
                    title="İcazə sorğunuz rədd edildi",
                    body=(
                            f"{instance.date} tarixli sorğunuz şöbə müdiri "
                            f"tərəfindən rədd edildi."
                            + (f" Səbəb: {comment}" if comment else "")
                    ),
                    notification_type=(
                        Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED
                    ),
                    link="/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )
        else:
                # ---------------------------------------------------------
                # MƏRHƏLƏ 2 — APARAT RƏHBƏRİ
                # ---------------------------------------------------------

                if not is_apparatus_head_enabled(instance.organization):
                    return Response(
                        {
                            "detail": (
                                "Aparat rəhbəri təsdiq mərhələsi "
                                "deaktiv edilib."
                            )
                        },
                        status=HTTP_400_BAD_REQUEST,
                    )

                configured_head = get_configured_apparatus_head(
                    instance.organization
                )

                if not configured_head:
                    return Response(
                        {
                            "detail": (
                                "Aparat rəhbəri təyin edilməyib."
                            )
                        },
                        status=HTTP_400_BAD_REQUEST,
                    )

                if configured_head.id != user.id:
                    return Response(
                        {
                            "detail": (
                                "Bu sorğunu yalnız konfiqurasiyada "
                                "təyin edilmiş Aparat rəhbəri təsdiqləyə bilər."
                            )
                        },
                        status=HTTP_403_FORBIDDEN,
                    )

                instance.status = (
                    AttendancePermission.STATUS_APPROVED
                    if action == "approve"
                    else AttendancePermission.STATUS_REJECTED
                )

                instance.reviewed_by = user
                instance.reviewed_at = now
                instance.review_comment = comment

                instance.save(
                    update_fields=[
                        "status",
                        "reviewed_by",
                        "reviewed_at",
                        "review_comment",
                    ]
                )

                notify(
                    instance.user,
                    title=(
                        "İcazəniz təsdiqləndi"
                        if action == "approve"
                        else "İcazəniz rədd edildi"
                    ),
                    body=(
                            f"{instance.date} tarixli icazə sorğunuz "
                            f"Aparat rəhbəri tərəfindən "
                            f"{'təsdiqləndi' if action == 'approve' else 'rədd edildi'}."
                            + (f" Səbəb: {comment}" if comment else "")
                    ),
                    notification_type=(
                        Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED
                        if action == "approve"
                        else Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED
                    ),
                    link="/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )

        logger.info(
            f"AttendancePermissionReviewView.patch - {user.username} icazəni {instance.status} etdi (id={instance.id})"
        )
        out = AttendancePermissionSerializer(instance, context={"request": request})
        return Response(out.data, status=HTTP_200_OK)


class AttendancePermissionConfigView(APIView):
    """
    Qurum üzrə icazə konfiqurasiyası.

    GET:
        Aparat rəhbəri + bütün departamentlər + onların config-ləri

    PATCH:
        Aparat rəhbəri konfiqurasiyasını dəyişir.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def _check_access(self, user):
        if not can_manage_attendance_permission_config(user):
            return Response(
                {"detail": "İcazə konfiqurasiyasını idarə etmək səlahiyyətiniz yoxdur."},
                status=HTTP_403_FORBIDDEN,
            )

        return None

    def get(self, request):
        denied = self._check_access(request.user)
        if denied:
            return denied

        organization = request.user.organization

        if not organization:
            return Response(
                {"detail": "İstifadəçinin qurumu təyin edilməyib."},
                status=HTTP_400_BAD_REQUEST,
            )

        organization_config = (
            AttendancePermissionOrganizationConfig.objects
            .select_related("apparatus_head")
            .filter(organization=organization)
            .first()
        )

        if not organization_config:
            organization_config = (
                AttendancePermissionOrganizationConfig.objects.create(
                    organization=organization,
                    apparatus_head_enabled=True,
                )
            )

        departments = (
            Department.objects
            .filter(
                # Department modelində organization yoxdur.
                # User-lər vasitəsilə qurumun departamentlərini tapırıq.
                id__in=User.objects.filter(
                    organization=organization,
                    department__isnull=False,
                ).values("department_id").distinct()
            )
            .select_related("manager")
            .prefetch_related("attendance_permission_config")
            .order_by("order", "title")
        )

        department_configs = {
            config.department_id: config
            for config in AttendancePermissionDepartmentConfig.objects.filter(
                organization=organization,
                department__in=departments,
            ).select_related(
                "department",
                "replacement_user",
            )
        }

        department_data = []

        for department in departments:
            config = department_configs.get(department.id)

            if not config:
                config = AttendancePermissionDepartmentConfig.objects.create(
                    organization=organization,
                    department=department,
                    manager_enabled=True,
                )

            department_data.append(
                AttendancePermissionDepartmentConfigSerializer(
                    config,
                    context={"request": request},
                ).data
            )

        return Response(
            {
                "organization": {
                    "id": organization.id,
                    "title": organization.title,
                },
                "apparatus": AttendancePermissionOrganizationConfigSerializer(
                    organization_config,
                    context={"request": request},
                ).data,
                "departments": department_data,
            },
            status=HTTP_200_OK,
        )

    def patch(self, request):
        denied = self._check_access(request.user)
        if denied:
            return denied

        organization = request.user.organization

        config, _ = (
            AttendancePermissionOrganizationConfig.objects.get_or_create(
                organization=organization,
                defaults={
                    "apparatus_head_enabled": True,
                },
            )
        )

        serializer = AttendancePermissionOrganizationConfigSerializer(
            config,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=HTTP_200_OK,
        )


class AttendancePermissionDepartmentConfigView(APIView):
    """
    Konkret departamentin icazə workflow konfiqurasiyası.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def patch(self, request, department_id):
        user = request.user

        if not can_manage_attendance_permission_config(user):
            return Response(
                {"detail": "İcazə konfiqurasiyasını dəyişmək səlahiyyətiniz yoxdur."},
                status=HTTP_403_FORBIDDEN,
            )

        organization = user.organization

        department = get_object_or_404(
            Department,
            id=department_id,
        )

        # Departament həmin qurumda real istifadə olunurmu?
        belongs_to_org = User.objects.filter(
            organization=organization,
            department=department,
        ).exists()

        if not belongs_to_org:
            return Response(
                {"detail": "Bu departament sizin qurumunuza aid deyil."},
                status=HTTP_403_FORBIDDEN,
            )

        config, _ = (
            AttendancePermissionDepartmentConfig.objects.get_or_create(
                organization=organization,
                department=department,
            )
        )

        serializer = AttendancePermissionDepartmentConfigSerializer(
            config,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=HTTP_200_OK,
        )


class AttendancePermissionConfigUsersView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        if not can_manage_attendance_permission_config(request.user):
            return Response(
                {"detail": "Səlahiyyətiniz yoxdur."},
                status=HTTP_403_FORBIDDEN,
            )

        organization = request.user.organization

        users = (
            User.objects
            .filter(
                organization=organization,
                is_active=True,
            )
            .select_related(
                "department",
                "role",
            )
            .order_by("firstname", "lastname")
        )

        return Response(
            AttendancePermissionUserShortSerializer(
                users,
                many=True,
            ).data,
            status=HTTP_200_OK,
        )
