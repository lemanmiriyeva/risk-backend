import django_filters
from django.db.models import Q
from django.utils import timezone

from . import services
from .models import Ticket


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class TicketFilterSet(django_filters.FilterSet):
    status = CharInFilter(field_name='status', lookup_expr='in')
    priority = CharInFilter(field_name='priority', lookup_expr='in')
    ticket_type = CharInFilter(field_name='ticket_type', lookup_expr='in')
    category = django_filters.NumberFilter(field_name='category_id')
    department = django_filters.NumberFilter(method='filter_department')
    assignee = django_filters.NumberFilter(field_name='assignee_id')
    requester = django_filters.NumberFilter(field_name='requester_id')
    overdue = django_filters.BooleanFilter(method='filter_overdue')
    unassigned = django_filters.BooleanFilter(method='filter_unassigned')
    active = django_filters.BooleanFilter(method='filter_active')
    scope = django_filters.CharFilter(method='filter_scope')
    date_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Ticket
        fields = []

    def filter_department(self, qs, name, value):
        return qs.filter(department_links__department_id=value).distinct()

    def filter_overdue(self, qs, name, value):
        cond = Q(status__in=Ticket.ACTIVE_STATUSES, due_at__lt=timezone.now())
        return qs.filter(cond) if value else qs.exclude(cond)

    def filter_unassigned(self, qs, name, value):
        cond = Q(assignee__isnull=True, status__in=Ticket.ACTIVE_STATUSES)
        return qs.filter(cond) if value else qs.exclude(cond)

    def filter_active(self, qs, name, value):
        return qs.filter(status__in=Ticket.ACTIVE_STATUSES) if value else qs.exclude(status__in=Ticket.ACTIVE_STATUSES)

    def filter_scope(self, qs, name, value):
        user = self.request.user
        if value == 'mine':
            return qs.filter(requester=user)
        if value == 'assigned':
            return qs.filter(Q(assignee=user) | Q(department_links__assignee=user)).distinct()
        if value == 'department':
            ids = services.user_department_ids(user)
            return qs.filter(department_links__department_id__in=ids).distinct() if ids else qs.none()
        if value == 'watching':
            return qs.filter(watchers=user)
        return qs
