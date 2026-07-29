import logging
from rest_framework import viewsets, filters
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import ModuleAccessPermission
from core.mixins import OrganizationScopedMixin
from .models import Risk, RiskLog
from .serializers import RiskSerializer, RiskLogSerializer
from .filters import RiskFilterSet, RiskLogFilterSet
from . import services

logger = logging.getLogger('colored')


class ExportLogView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        export_type = request.data.get('export_type', 'unknown')
        row_count = request.data.get('row_count', 0)
        filters_applied = request.data.get('filters', {})
        user = request.user

        logger.info(
            f"Excel ixracı - {user.username} '{export_type}' cədvəlini ixrac etdi "
            f"({row_count} sətir, filtrlər={filters_applied})"
        )

        try:
            services.log_exported(
                user=user,
                export_type=export_type,
                row_count=row_count,
                filters=filters_applied,
                request=request,
            )
            return Response(status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"ExportLogView - xəta ({user.username}): {str(e)}")
            return Response({'detail': 'Export logu saxlanılmadı'}, status=status.HTTP_400_BAD_REQUEST)


class RiskViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Risk.objects.select_related('created_by', 'updated_by', 'organization').all()
    serializer_class = RiskSerializer
    permission_classes = [ModuleAccessPermission]
    module_code = "risk"

    action_sub_module_codes = {
        "list": ["risk_register", "risk_view_table"],
        "retrieve": ["risk_register", "risk_view_table"],
        "create": ["risk_register"],
        "update": ["risk_register"],
        "partial_update": ["risk_register"],
        "destroy": ["risk_register"],
    }

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RiskFilterSet
    search_fields = [
        'designation', 'legal_basis', 'international_framework',
        'national_legal_reference', 'standard_references',
    ]
    ordering_fields = ['risk_degree', 'created_at', 'updated_at', 'designation']
    ordering = ['-created_at']

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        try:
            if isinstance(response.data, dict) and 'results' in response.data:
                row_count = len(response.data['results'])
            else:
                row_count = len(response.data)
            services.log_viewed_list(
                user=request.user,
                row_count=row_count,
                filters=request.query_params.dict(),
                request=request,
            )
        except Exception as e:
            logger.error(f"RiskViewSet.list - baxış loqu yazıla bilmədi: {str(e)}")
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        try:
            services.log_viewed_detail(instance, request.user, request=request)
        except Exception as e:
            logger.error(f"RiskViewSet.retrieve - baxış loqu yazıla bilmədi: {str(e)}")
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        logger.info(
            f"RiskViewSet.update çağırıldı - method={request.method}, "
            f"user={request.user}, pk={kwargs.get('pk')}, data={request.data}"
        )
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"RiskViewSet.update nəticəsi - status={response.status_code}")
            return response
        except Exception as e:
            logger.error(f"RiskViewSet.update - xəta: {str(e)}")
            raise

    def partial_update(self, request, *args, **kwargs):
        logger.info(
            f"RiskViewSet.partial_update çağırıldı - method={request.method}, "
            f"user={request.user}, pk={kwargs.get('pk')}, data={request.data}"
        )
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"RiskViewSet.partial_update nəticəsi - status={response.status_code}")
            return response
        except Exception as e:
            logger.error(f"RiskViewSet.partial_update - xəta: {str(e)}")
            raise

    def perform_create(self, serializer):
        user = self.request.user
        org_id = getattr(user, "organization_id", None)

        if not org_id and not user.is_superuser:
            logger.error(f"RiskViewSet.perform_create - {user.username} üçün organization təyin edilməyib")
            raise Exception("İstifadəçinin qurumu təyin edilməyib.")

        try:
            instance = serializer.save(
                created_by=user,
                updated_by=user,
                organization=user.organization if org_id else None,
            )
            services.log_created(instance, user, request=self.request)
            logger.info(f"RiskViewSet - {user.username} yeni risk yaratdı (id={instance.id})")
        except Exception as e:
            logger.error(f"RiskViewSet.perform_create - xəta ({user.username}): {str(e)}")
            raise

    def perform_update(self, serializer):
        from types import SimpleNamespace
        user = self.request.user
        try:
            old_values = {f: getattr(serializer.instance, f) for f in services.TRACKED_FIELDS}
            updated = serializer.save(updated_by=user)
            services.log_updated(SimpleNamespace(**old_values), updated, user, request=self.request)
            logger.info(f"RiskViewSet - {user.username} riski yenilədi (id={updated.id})")
        except Exception as e:
            logger.error(f"RiskViewSet.perform_update - xəta ({user.username}): {str(e)}")
            raise

    def perform_destroy(self, instance):
        user = self.request.user
        try:
            services.log_deleted(instance, user, request=self.request)
            risk_id = instance.id
            instance.delete()
            logger.info(f"RiskViewSet - {user.username} riski sildi (id={risk_id})")
        except Exception as e:
            logger.error(f"RiskViewSet.perform_destroy - xəta ({user.username}): {str(e)}")
            raise


class RiskLogViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = RiskLog.objects.select_related('user', 'risk', 'organization').all()
    serializer_class = RiskLogSerializer
    permission_classes = [ModuleAccessPermission]
    module_code = "risk"
    sub_module_code = "risk_log"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RiskLogFilterSet
    search_fields = ['risk_designation', 'user_username_snapshot']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']