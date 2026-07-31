import logging
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import ModuleAccessPermission
from .models import ActivityLog
from .serializers import ActivityLogSerializer
from .filters import ActivityLogFilterSet

logger = logging.getLogger('colored')


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Saytın bütün fəaliyyət loqlarına baxış üçün READ-ONLY endpoint.

    Giriş qaydası:
      - Superuser (root): bütün sistemin loqlarını görür.
      - Qurum admini (is_org_admin): yalnız öz qurumunun işçilərinin loqlarını görür.
      - Adi istifadəçi: yalnız özünə aid loqları görür (bu modula giriş verilibsə).
    """
    queryset = ActivityLog.objects.select_related('user', 'user__organization').all()
    serializer_class = ActivityLogSerializer
    permission_classes = [ModuleAccessPermission]
    module_code = "activity_logs"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActivityLogFilterSet
    search_fields = ['user_username_snapshot', 'description', 'request_path', 'module_title']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        if getattr(user, "is_org_admin", False) and getattr(user, "organization_id", None):
            return qs.filter(user__organization_id=user.organization_id)
        return qs.filter(user=user)