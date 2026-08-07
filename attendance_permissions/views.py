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
from .permissions import is_apparatus_head, can_review, get_visible_queryset, get_department_manager, get_apparatus_head
from .serializers import (
    AttendancePermissionSerializer,
    AttendancePermissionCreateSerializer,
    AttendancePermissionReviewSerializer,
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
                {"detail": "Aparat rəhbəri icazə sorğusu yarada bilməz - yalnız təsdiq/rədd edə bilər."},
                status=HTTP_403_FORBIDDEN,
            )

        serializer = AttendancePermissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(
            user=user,
            department=user.department,
            organization=user.organization,
            status=AttendancePermission.STATUS_PENDING,
        )

        logger.info(f"AttendancePermissionListCreateView.post - {user.username} yeni icazə sorğusu yaratdı (id={instance.id})")

        department_manager = get_department_manager(instance.department)
        notify(
            department_manager,
            title="Yeni icazə sorğusu",
            body=f"{user.name} {instance.date} tarixi üçün icazə sorğusu göndərdi.",
            notification_type=Notification.TYPE_ATTENDANCE_PERMISSION_NEW,
            link=f"/icazeler",
            related_app="attendance_permissions",
            related_object_id=instance.id,
        )

        out = AttendancePermissionSerializer(instance, context={"request": request})
        return Response(out.data, status=HTTP_201_CREATED)


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
            # Mərhələ 1: şöbə müdiri
            instance.department_reviewed_by = user
            instance.department_reviewed_at = now
            instance.department_review_comment = comment

            if action == "approve":
                instance.status = AttendancePermission.STATUS_AWAITING_APPARATUS
                instance.save(update_fields=[
                    "status", "department_reviewed_by", "department_reviewed_at", "department_review_comment",
                ])
                apparatus_head = get_apparatus_head(instance.organization)
                notify(
                    apparatus_head,
                    title="Təsdiq üçün icazə sorğusu",
                    body=f"{instance.user.name} - {instance.date} tarixli icazə sorğusu şöbə müdiri tərəfindən təsdiqləndi, sizin təsdiqinizi gözləyir.",
                    notification_type=Notification.TYPE_ATTENDANCE_PERMISSION_DEPT_APPROVED,
                    link=f"/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )
            else:
                # Şöbə müdiri rədd edibsə, proses burada bitir - son qərar sahələri də dolur
                instance.status = AttendancePermission.STATUS_REJECTED
                instance.reviewed_by = user
                instance.reviewed_at = now
                instance.review_comment = comment
                instance.save(update_fields=[
                    "status", "department_reviewed_by", "department_reviewed_at", "department_review_comment",
                    "reviewed_by", "reviewed_at", "review_comment",
                ])
                notify(
                    instance.user,
                    title="İcazə sorğunuz rədd edildi",
                    body=f"{instance.date} tarixli sorğunuz şöbə müdiri tərəfindən rədd edildi." + (f" Səbəb: {comment}" if comment else ""),
                    notification_type=Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED,
                    link=f"/icazeler",
                    related_app="attendance_permissions",
                    related_object_id=instance.id,
                )
        else:
            # Mərhələ 2 (son): Aparat rəhbəri
            instance.status = (
                AttendancePermission.STATUS_APPROVED if action == "approve"
                else AttendancePermission.STATUS_REJECTED
            )
            instance.reviewed_by = user
            instance.reviewed_at = now
            instance.review_comment = comment
            instance.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment"])

            notify(
                instance.user,
                title="İcazə sorğunuz təsdiqləndi" if action == "approve" else "İcazə sorğunuz rədd edildi",
                body=f"{instance.date} tarixli sorğunuz Aparat rəhbəri tərəfindən {'təsdiqləndi' if action == 'approve' else 'rədd edildi'}." + (f" Səbəb: {comment}" if comment else ""),
                notification_type=(
                    Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED if action == "approve"
                    else Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED
                ),
                link=f"/icazeler",
                related_app="attendance_permissions",
                related_object_id=instance.id,
            )

        logger.info(
            f"AttendancePermissionReviewView.patch - {user.username} icazəni {instance.status} etdi (id={instance.id})"
        )
        out = AttendancePermissionSerializer(instance, context={"request": request})
        return Response(out.data, status=HTTP_200_OK)