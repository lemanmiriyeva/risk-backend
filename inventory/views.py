from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .filters import InventoryFilterSet
from core.permissions import ModuleAccessPermission
from .models import Inventory, InventoryOwnerPerson, InventoryOwnerDepartment
from .serializers import InventorySerializer, InventoryOwnerPersonSerializer, InventoryOwnerDepartmentSerializer


class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.select_related(
        'owner_person', 'owner_department', 'created_by', 'updated_by'
    ).all()
    serializer_class = InventorySerializer
    permission_classes = [ModuleAccessPermission]
    module_code = "inventory"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InventoryFilterSet
    search_fields = ['product_name', 'inventory_number', 'owner_person__full_name', 'owner_department__name']
    ordering_fields = ['created_at', 'updated_at', 'product_name', 'inventory_number']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'], url_path='owners/persons')
    def search_persons(self, request):
        q = request.query_params.get('q', '').strip()
        qs = InventoryOwnerPerson.objects.all()
        if q:
            qs = qs.filter(full_name__icontains=q)
        qs = qs.order_by('full_name')[:20]
        return Response(InventoryOwnerPersonSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='owners/departments')
    def search_departments(self, request):
        q = request.query_params.get('q', '').strip()
        qs = InventoryOwnerDepartment.objects.all()
        if q:
            qs = qs.filter(name__icontains=q)
        qs = qs.order_by('name')[:20]
        return Response(InventoryOwnerDepartmentSerializer(qs, many=True).data)