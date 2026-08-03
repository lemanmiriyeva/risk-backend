import logging
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger('colored')


class OrganizationScopedMixin:
    organization_field = "organization"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()

        if user.is_superuser:
            return qs

        org_id = getattr(user, "organization_id", None)
        if not org_id:
            logger.info(f"OrganizationScopedMixin - {user.username} üçün organization təyin edilməyib, boş nəticə")
            return qs.none()

        return qs.filter(**{self.organization_field: org_id})

    def perform_create(self, serializer):
        user = self.request.user
        org_id = getattr(user, "organization_id", None)

        if not org_id and not user.is_superuser:
            raise PermissionDenied("İstifadəçinin qurumu təyin edilməyib, əməliyyat mümkün deyil.")

        extra_fields = {}
        if org_id:
            extra_fields[self.organization_field] = user.organization

        serializer.save(**extra_fields)