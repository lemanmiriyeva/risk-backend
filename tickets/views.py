import re
from datetime import timedelta

from django.db.models import Avg, Case, Count, ExpressionWrapper, F, IntegerField, Q, Value, When, DurationField
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status as http, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import Department, User
from authentication.permissions import HasSystemAccess
from core.permissions import ModuleAccessPermission

from . import services
from .filters import TicketFilterSet
from .models import Ticket, TicketCategory, TicketDepartment, SLA_HOURS
from .serializers import (
    AssigneeSerializer, AttachmentSerializer, CategorySerializer, CommentCreateSerializer,
    CommentSerializer, DepartmentMiniSerializer, DepartmentStatusSerializer,
    RatingSerializer, SetDepartmentsSerializer, StatusSerializer, TicketCreateSerializer,
    TicketDetailSerializer, TicketListSerializer, TicketUpdateSerializer, UserMiniSerializer,
    WatchersSerializer,
)


class TicketPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class TicketPermission(ModuleAccessPermission):
    """HasSystemAccess + 'tickets' modulu (hər kəsə açıqdır)."""

    def has_permission(self, request, view):
        return (
            HasSystemAccess().has_permission(request, view)
            and super().has_permission(request, view)
        )


PRIORITY_RANK = Case(
    When(priority=Ticket.PRIORITY_CRITICAL, then=Value(4)),
    When(priority=Ticket.PRIORITY_HIGH, then=Value(3)),
    When(priority=Ticket.PRIORITY_MEDIUM, then=Value(2)),
    default=Value(1), output_field=IntegerField(),
)


def departments_for(user):
    qs = Department.objects.select_related('manager', 'organization').order_by('order', 'title')
    if user.is_superuser or not user.organization_id:
        return qs
    return qs.filter(Q(organization_id=user.organization_id) | Q(organization__isnull=True))


class TicketViewSet(viewsets.GenericViewSet):
    permission_classes = [TicketPermission]
    module_code = services.MODULE_CODE
    queryset = Ticket.objects.all()
    pagination_class = TicketPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = TicketFilterSet
    ordering_fields = ['created_at', 'updated_at', 'last_activity_at', 'due_at', 'status', 'priority_rank', 'id']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = services.visible_queryset(self.request.user, Ticket.objects.all())
        qs = qs.select_related(
            'category', 'requester', 'requester_department', 'assignee', 'organization',
        ).prefetch_related(
            'department_links__department__manager', 'comments', 'watchers',
        ).annotate(priority_rank=PRIORITY_RANK)
        return qs

    def get_serializer_class(self):
        return TicketDetailSerializer if self.action == 'retrieve' else TicketListSerializer

    def get_serializer_context(self):
        return {'request': self.request}

    def _get(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    def _detail(self, ticket):
        ticket = self._get(ticket.pk)
        return Response(TicketDetailSerializer(ticket, context=self.get_serializer_context()).data)

    # ---- siyahı / axtarış
    def filter_queryset(self, qs):
        qs = super().filter_queryset(qs)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            m = re.fullmatch(r'(?i)(?:tkt-?)?0*(\d+)', search)
            cond = (
                Q(title__icontains=search) | Q(description__icontains=search)
                | Q(requester__firstname__icontains=search) | Q(requester__lastname__icontains=search)
            )
            if m:
                cond |= Q(pk=int(m.group(1)))
            qs = qs.filter(cond)
        return qs

    def list(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        ser = TicketListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(ser.data)

    def retrieve(self, request, pk=None):
        ticket = self._get(pk)
        return Response(TicketDetailSerializer(ticket, context=self.get_serializer_context()).data)

    def create(self, request):
        ser = TicketCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ticket = services.create_ticket(
            user=request.user, data=d,
            department_ids=d.get('departments'), watcher_ids=d.get('watchers'),
        )
        return Response(
            TicketDetailSerializer(self._get(ticket.pk), context=self.get_serializer_context()).data,
            status=http.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        ticket = self._get(pk)
        ser = TicketUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        services.update_ticket_fields(ticket, request.user, ser.validated_data)
        return self._detail(ticket)

    # ---- workflow
    @action(detail=True, methods=['post'])
    def status(self, request, pk=None):
        ticket = self._get(pk)
        ser = StatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.change_status(ticket, request.user, ser.validated_data['status'], ser.validated_data['comment'])
        return self._detail(ticket)

    @action(detail=True, methods=['put'])
    def departments(self, request, pk=None):
        ticket = self._get(pk)
        ser = SetDepartmentsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.set_departments(ticket, request.user, ser.validated_data['departments'])
        return self._detail(ticket)

    @action(detail=True, methods=['post'], url_path='department-status')
    def department_status(self, request, pk=None):
        ticket = self._get(pk)
        ser = DepartmentStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        services.set_department_status(ticket, request.user, d['department'], d['status'], d['note'])
        return self._detail(ticket)

    @action(detail=True, methods=['post'])
    def assignee(self, request, pk=None):
        ticket = self._get(pk)
        ser = AssigneeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.set_assignee(ticket, request.user, ser.validated_data['assignee'])
        return self._detail(ticket)

    @action(detail=True, methods=['post'])
    def take(self, request, pk=None):
        ticket = self._get(pk)
        services.take_ticket(ticket, request.user)
        return self._detail(ticket)

    @action(detail=True, methods=['post'])
    def comments(self, request, pk=None):
        ticket = self._get(pk)
        ser = CommentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        comment = services.add_comment(
            ticket, request.user, ser.validated_data['body'], ser.validated_data['is_internal'])
        # fayllar ayrıca /attachments/ ilə yüklənir; şərhə bağlamaq üçün comment id qaytarılır
        out = CommentSerializer(comment, context=self.get_serializer_context()).data
        return Response(out, status=http.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def attachments(self, request, pk=None):
        ticket = self._get(pk)
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files:
            return Response({'file': 'Fayl seçilməyib.'}, status=http.HTTP_400_BAD_REQUEST)
        comment = None
        comment_id = request.data.get('comment')
        if comment_id:
            comment = get_object_or_404(ticket.comments, pk=comment_id)
            if comment.author_id != request.user.id:
                raise PermissionDenied("Yalnız öz şərhinizə fayl əlavə edə bilərsiniz.")
        internal = str(request.data.get('is_internal', '')).lower() in ('1', 'true') or (comment and comment.is_internal)
        if internal and not services.is_agent(ticket, request.user):
            raise PermissionDenied("Daxili fayl yalnız şöbə əməkdaşları əlavə edə bilər.")
        created = [services.add_attachment(ticket, request.user, f, comment, bool(internal)) for f in files]
        return Response(
            AttachmentSerializer(created, many=True, context=self.get_serializer_context()).data,
            status=http.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def watch(self, request, pk=None):
        ticket = self._get(pk)
        services.set_watching(ticket, request.user, True)
        return self._detail(ticket)

    @action(detail=True, methods=['post'])
    def unwatch(self, request, pk=None):
        ticket = self._get(pk)
        services.set_watching(ticket, request.user, False)
        return self._detail(ticket)

    @action(detail=True, methods=['post'])
    def watchers(self, request, pk=None):
        ticket = self._get(pk)
        ser = WatchersSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.add_watchers(ticket, request.user, ser.validated_data['users'])
        return self._detail(ticket)

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        ticket = self._get(pk)
        ser = RatingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.rate_ticket(ticket, request.user, ser.validated_data['rating'], ser.validated_data['comment'])
        return self._detail(ticket)

    # ---- statistika
    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.filter_queryset(self.get_queryset()).order_by()
        now = timezone.now()
        active = qs.filter(status__in=Ticket.ACTIVE_STATUSES)
        by_status = {s: 0 for s, _ in Ticket.STATUS_CHOICES}
        for row in qs.values('status').annotate(c=Count('id', distinct=True)):
            by_status[row['status']] = row['c']
        by_priority = {p: 0 for p, _ in Ticket.PRIORITY_CHOICES}
        for row in active.values('priority').annotate(c=Count('id', distinct=True)):
            by_priority[row['priority']] = row['c']

        solved = qs.filter(resolved_at__isnull=False)
        avg = solved.annotate(
            d=ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
        ).aggregate(a=Avg('d'))['a']
        total_solved = solved.count()
        within_sla = solved.filter(resolved_at__lte=F('due_at')).count()
        ratings = qs.filter(rating__isnull=False).aggregate(a=Avg('rating'), c=Count('id'))

        dept_rows = (
            TicketDepartment.objects.filter(ticket__in=active.values('id'))
            .values('department_id', 'department__title', 'department__shortname')
            .annotate(c=Count('ticket_id', distinct=True)).order_by('-c')[:8]
        )
        since = (now - timedelta(days=13)).date()
        created = {r['d']: r['c'] for r in qs.filter(created_at__date__gte=since)
                   .values(d=F('created_at__date')).annotate(c=Count('id', distinct=True))}
        resolved = {r['d']: r['c'] for r in qs.filter(resolved_at__date__gte=since)
                    .values(d=F('resolved_at__date')).annotate(c=Count('id', distinct=True))}
        trend = []
        for i in range(14):
            day = since + timedelta(days=i)
            trend.append({'date': day.isoformat(), 'created': created.get(day, 0), 'resolved': resolved.get(day, 0)})

        return Response({
            'total': qs.count(),
            'active': active.count(),
            'overdue': active.filter(due_at__lt=now).count(),
            'unassigned': active.filter(assignee__isnull=True).count(),
            'by_status': by_status,
            'by_priority': by_priority,
            'avg_resolution_hours': round(avg.total_seconds() / 3600, 1) if avg else None,
            'sla_compliance': round(within_sla * 100 / total_solved) if total_solved else None,
            'avg_rating': round(ratings['a'], 1) if ratings['a'] else None,
            'rating_count': ratings['c'],
            'by_department': [
                {'id': r['department_id'], 'title': r['department__shortname'] or r['department__title'], 'count': r['c']}
                for r in dept_rows
            ],
            'trend': trend,
        })


class TicketMetaView(APIView):
    """Forma və filtrlər üçün: kateqoriyalar, şöbələr, enum-lar, SLA qaydaları."""
    permission_classes = [TicketPermission]
    module_code = services.MODULE_CODE

    def get(self, request):
        user = request.user
        return Response({
            'statuses': [{'value': v, 'label': l} for v, l in Ticket.STATUS_CHOICES],
            'priorities': [{'value': v, 'label': l, 'sla_first_response_h': SLA_HOURS[v][0], 'sla_resolution_h': SLA_HOURS[v][1]}
                           for v, l in Ticket.PRIORITY_CHOICES],
            'types': [{'value': v, 'label': l} for v, l in Ticket.TYPE_CHOICES],
            'categories': CategorySerializer(TicketCategory.objects.filter(is_active=True), many=True).data,
            'departments': DepartmentMiniSerializer(departments_for(user), many=True).data,
            'is_admin': services.is_ticket_admin(user),
            'my_department': user.department_id,
            'my_departments': sorted(services.user_department_ids(user)),
        })


class TicketUsersView(APIView):
    """Icraçı / izləyici seçimi üçün istifadəçi axtarışı."""
    permission_classes = [TicketPermission]
    module_code = services.MODULE_CODE

    def get(self, request):
        user = request.user
        qs = User.objects.filter(is_active=True, is_approved=True).select_related('department')
        if not user.is_superuser and user.organization_id:
            qs = qs.filter(organization_id=user.organization_id)
        dept = request.query_params.get('department')
        if dept:
            ids = {int(dept)} | set(Department.objects.filter(parent_id=dept).values_list('id', flat=True)) \
                if str(dept).isdigit() else set()
            qs = qs.filter(department_id__in=ids)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(firstname__icontains=q) | Q(lastname__icontains=q) | Q(username__icontains=q))
        return Response(UserMiniSerializer(qs.order_by('firstname', 'lastname')[:30], many=True).data)


class CategoryViewSet(viewsets.ModelViewSet):
    """Kateqoriyalar: oxumaq hamıya, yaratmaq/redaktə yalnız ticket adminlərinə."""
    permission_classes = [TicketPermission]
    module_code = services.MODULE_CODE
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        qs = TicketCategory.objects.select_related('default_department')
        if self.action == 'list' and not services.is_ticket_admin(self.request.user):
            qs = qs.filter(is_active=True)
        return qs

    def _check_admin(self):
        if not services.is_ticket_admin(self.request.user):
            raise PermissionDenied("Kateqoriyaları yalnız ticket adminləri idarə edə bilər.")

    def create(self, request, *args, **kwargs):
        self._check_admin()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._check_admin()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._check_admin()
        cat = self.get_object()
        if cat.tickets.exists():
            # müraciətləri olan kateqoriya silinmir, deaktiv edilir
            cat.is_active = False
            cat.save(update_fields=['is_active', 'updated_at'])
            return Response(CategorySerializer(cat).data)
        return super().destroy(request, *args, **kwargs)
