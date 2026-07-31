import django_filters
from .models import ActivityLog


class ActivityLogFilterSet(django_filters.FilterSet):
    action_type = django_filters.CharFilter(field_name='action_type', lookup_expr='iexact')
    module_code = django_filters.CharFilter(field_name='module_code', lookup_expr='iexact')
    user = django_filters.NumberFilter(field_name='user_id', lookup_expr='exact')
    date_from = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = ActivityLog
        fields = ['action_type', 'module_code', 'user', 'date_from', 'date_to']