import django_filters
from .models import Risk, RiskLog


class RiskFilterSet(django_filters.FilterSet):

    risk_level = django_filters.CharFilter(field_name='risk_level', lookup_expr='iexact')
    treatment_option = django_filters.CharFilter(field_name='treatment_option', lookup_expr='iexact')
    organization = django_filters.NumberFilter(field_name='organization_id', lookup_expr='exact')

    class Meta:
        model = Risk
        fields = ['risk_level', 'treatment_option', 'organization']


class RiskLogFilterSet(django_filters.FilterSet):
    action_type = django_filters.CharFilter(field_name='action_type', lookup_expr='iexact')
    risk_id_ref = django_filters.NumberFilter(field_name='risk_id_ref')
    organization = django_filters.NumberFilter(field_name='organization_id', lookup_expr='exact')

    class Meta:
        model = RiskLog
        fields = ['action_type', 'risk_id_ref', 'organization']