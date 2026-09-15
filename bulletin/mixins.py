from django.db.models import Q


class BulletinOrgScopedMixin:
    """
    `core.mixins.OrganizationScopedMixin`-dən fərqli olaraq, bu app-da
    `organization = null` olan yazılar (sərəncam/xəbər) BÜTÜN qurumlara aid
    sayılır (məs. Nazirlik səviyyəsində elan olunan bir sərəncam). Ona görə
    adi işçi həm öz qurumunun, həm də ümumi (organization=null) yazılarını
    görməlidir.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()

        if user.is_superuser:
            return qs

        org_id = getattr(user, "organization_id", None)
        return qs.filter(Q(organization_id=org_id) | Q(organization__isnull=True))

    def perform_create(self, serializer):
        user = self.request.user
        organization = serializer.validated_data.get("organization")

        # Qurum admini yalnız ÖZ qurumu üçün (və ya hamıya aid, boş buraxaraq)
        # yaza bilər - başqa qurum adından yazı əlavə edə bilməz.
        if not user.is_superuser and organization is not None:
            org_id = getattr(user, "organization_id", None)
            if organization.id != org_id:
                organization = user.organization if org_id else None

        serializer.save(created_by=user, organization=organization)

    def perform_update(self, serializer):
        serializer.save()