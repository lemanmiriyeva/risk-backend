import django_filters
from .models import Inventory


class InventoryFilterSet(django_filters.FilterSet):
    owner_type = django_filters.CharFilter(field_name='owner_type', lookup_expr='exact')

    class Meta:
        model = Inventory
        fields = ['owner_type']