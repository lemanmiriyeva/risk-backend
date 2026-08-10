import django_filters

from .models import Operation


class OperationFilterSet(django_filters.FilterSet):
    category_code = django_filters.CharFilter(field_name='category_code', lookup_expr='iexact')
    operation_type = django_filters.CharFilter(field_name='operation_type', lookup_expr='iexact')
    action = django_filters.CharFilter(field_name='action', lookup_expr='iexact')
    status = django_filters.CharFilter(field_name='status', lookup_expr='iexact')
    user = django_filters.NumberFilter(field_name='user_id', lookup_expr='exact')
    organization = django_filters.NumberFilter(field_name='organization_id', lookup_expr='exact')
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Operation
        fields = [
            'category_code', 'operation_type', 'action', 'status',
            'user', 'organization', 'date_from', 'date_to',
        ]