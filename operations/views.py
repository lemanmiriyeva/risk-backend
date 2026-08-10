import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.permissions import ModuleAccessPermission

from .filters import OperationFilterSet
from .models import Operation
from .serializers import OperationReviewSerializer, OperationSerializer
from .services import advance_approval_step

logger = logging.getLogger('colored')


class OperationViewSet(viewsets.ReadOnlyModelViewSet):
    """Mərkəzi 'Əməliyyatlar' siyahısı - CRUD loqları + təsdiq tələb edən əməliyyatlar."""

    queryset = Operation.objects.select_related(
        'user', 'organization', 'module', 'content_type'
    ).prefetch_related('approval_steps').all()
    serializer_class = OperationSerializer
    permission_classes = [ModuleAccessPermission]
    module_code = "operations"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OperationFilterSet
    search_fields = ['user_username_snapshot', 'description', 'object_repr', 'category_title']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()
        # Superuser - bütün əməliyyatları görür.
        if user.is_superuser:
            return qs
        # Qurum admini - yalnız öz qurumuna aid əməliyyatları görür.
        if getattr(user, "is_org_admin", False) and getattr(user, "organization_id", None):
            return qs.filter(organization_id=user.organization_id)
        # Adi istifadəçi - yalnız ÖZÜNÜN yaratdığı əməliyyatları görür.
        return qs.filter(user=user)


class OperationReviewView(APIView):
    """Cari mərhələnin təsdiqləyicisi (və ya superuser) tərəfindən təsdiq/rədd."""

    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def patch(self, request, id):
        user = request.user
        operation = get_object_or_404(Operation, id=id)

        if operation.operation_type != Operation.TYPE_APPROVAL:
            return Response(
                {"detail": "Bu əməliyyat təsdiq tələb etmir."}, status=HTTP_400_BAD_REQUEST
            )
        if operation.status not in (Operation.STATUS_PENDING, Operation.STATUS_IN_PROGRESS):
            return Response(
                {"detail": "Bu əməliyyat artıq yekunlaşıb."}, status=HTTP_400_BAD_REQUEST
            )

        step = operation.approval_steps.filter(step_number=operation.current_step).first()
        if not step:
            return Response({"detail": "Aktiv mərhələ tapılmadı."}, status=HTTP_400_BAD_REQUEST)
        if not user.is_superuser and step.approver_id and step.approver_id != user.id:
            return Response({"detail": "Bu mərhələni təsdiqləmək icazəniz yoxdur."}, status=HTTP_403_FORBIDDEN)

        serializer = OperationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        operation = advance_approval_step(
            operation=operation,
            reviewer=user,
            action=serializer.validated_data["action"],
            comment=serializer.validated_data.get("comment", ""),
        )

        logger.info(
            f"OperationReviewView.patch - {user.username} əməliyyat #{operation.id} üçün "
            f"{serializer.validated_data['action']} qərarı verdi"
        )

        out = OperationSerializer(operation, context={"request": request})
        return Response(out.data, status=HTTP_200_OK)