from rest_framework import serializers

from authentication.models import Department, User
from core.media_urls import media_url

from . import services
from .models import (
    Ticket, TicketActivity, TicketAssignee, TicketAttachment, TicketCategory, TicketComment, TicketDepartment,
)


class UserMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    department_title = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'name', 'username', 'department_title')

    def get_department_title(self, obj):
        return obj.department.title if obj.department_id else None


class DepartmentMiniSerializer(serializers.ModelSerializer):
    manager_name = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ('id', 'title', 'shortname', 'manager_name', 'organization_name')

    def get_manager_name(self, obj):
        return obj.manager.name if obj.manager_id else None

    def get_organization_name(self, obj):
        return obj.organization.title if obj.organization_id else None


class CategorySerializer(serializers.ModelSerializer):
    default_department_title = serializers.SerializerMethodField()

    class Meta:
        model = TicketCategory
        fields = (
            'id', 'title', 'code', 'description', 'color', 'default_department',
            'default_department_title', 'default_priority', 'is_active', 'order',
        )

    def get_default_department_title(self, obj):
        return obj.default_department.title if obj.default_department_id else None

    def validate_default_priority(self, value):
        if value not in dict(Ticket.PRIORITY_CHOICES):
            raise serializers.ValidationError('Yanlış prioritet.')
        return value


class TicketDepartmentSerializer(serializers.ModelSerializer):
    department_title = serializers.CharField(source='department.title', read_only=True)
    department_shortname = serializers.CharField(source='department.shortname', read_only=True)
    assignee_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = TicketDepartment
        fields = (
            'id', 'department', 'department_title', 'department_shortname', 'manager_name',
            'assignee', 'assignee_name', 'is_primary', 'status', 'status_display', 'note', 'completed_at',
        )

    def get_assignee_name(self, obj):
        return obj.assignee.name if obj.assignee_id else None

    def get_manager_name(self, obj):
        d = obj.department
        return d.manager.name if d.manager_id else None


class TicketAssigneeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    department_title = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TicketAssignee
        fields = (
            'id', 'user', 'name', 'department', 'department_title', 'status', 'status_display',
            'self_assigned', 'note', 'started_at', 'completed_at', 'created_at',
        )

    def get_department_title(self, obj):
        d = obj.department
        return (d.shortname or d.title) if d else None


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = ('id', 'original_name', 'size', 'content_type', 'url', 'comment',
                  'uploaded_by', 'uploaded_by_name', 'created_at', 'is_internal')

    def get_url(self, obj):
        return media_url(self.context.get('request'), obj.file)

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.name if obj.uploaded_by_id else None


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_department = serializers.SerializerMethodField()
    is_requester = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TicketComment
        fields = ('id', 'author', 'author_name', 'author_department', 'is_requester', 'body',
                  'is_internal', 'attachments', 'created_at')

    def get_author_name(self, obj):
        return obj.author.name if obj.author_id else 'Silinmiş istifadəçi'

    def get_author_department(self, obj):
        return obj.author.department.shortname or obj.author.department.title if obj.author_id and obj.author.department_id else None

    def get_is_requester(self, obj):
        return obj.author_id == obj.ticket.requester_id


class ActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = TicketActivity
        fields = ('id', 'actor', 'actor_name', 'action', 'data', 'created_at')

    def get_actor_name(self, obj):
        return obj.actor.name if obj.actor_id else 'Sistem'


class TicketListSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    type_display = serializers.CharField(source='get_ticket_type_display', read_only=True)
    category_title = serializers.SerializerMethodField()
    category_color = serializers.SerializerMethodField()
    requester_name = serializers.SerializerMethodField()
    requester_department = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    assignees = serializers.SerializerMethodField()
    departments = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)
    first_response_overdue = serializers.BooleanField(read_only=True)
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            'id', 'number', 'title', 'ticket_type', 'type_display',
            'status', 'status_display', 'priority', 'priority_display',
            'category', 'category_title', 'category_color',
            'requester', 'requester_name', 'requester_department',
            'assignee', 'assignee_name', 'assignees', 'departments',
            'due_at', 'is_overdue', 'first_response_overdue', 'first_response_at',
            'comment_count', 'rating', 'created_at', 'updated_at', 'last_activity_at',
        )

    def get_category_title(self, obj):
        return obj.category.title if obj.category_id else None

    def get_category_color(self, obj):
        return obj.category.color if obj.category_id else None

    def get_requester_name(self, obj):
        return obj.requester.name if obj.requester_id else None

    def get_requester_department(self, obj):
        return obj.requester_department.shortname or obj.requester_department.title if obj.requester_department_id else None

    def get_assignee_name(self, obj):
        rows = list(obj.assignee_links.all())
        if not rows:
            return None
        return rows[0].user.name + (f' +{len(rows) - 1}' if len(rows) > 1 else '')

    def get_assignees(self, obj):
        return [{'id': r.user_id, 'name': r.user.name, 'status': r.status, 'status_display': r.get_status_display()}
                for r in obj.assignee_links.all()]

    def get_departments(self, obj):
        return [
            {'id': l.department_id, 'title': l.department.shortname or l.department.title,
             'status': l.status, 'is_primary': l.is_primary}
            for l in obj.department_links.all()
        ]

    def get_comment_count(self, obj):
        request = self.context.get('request')
        agent = request and services.is_agent(obj, request.user)
        return sum(1 for c in obj.comments.all() if agent or not c.is_internal)


class TicketDetailSerializer(TicketListSerializer):
    description = serializers.CharField(read_only=True)
    department_links = TicketDepartmentSerializer(many=True, read_only=True)
    assignees = TicketAssigneeSerializer(source='assignee_links', many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    activities = serializers.SerializerMethodField()
    watchers = UserMiniSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()
    sla = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + (
            'description', 'tags', 'department_links', 'comments', 'attachments', 'activities',
            'watchers', 'permissions', 'sla', 'rating_comment', 'reopen_count',
            'resolved_at', 'closed_at', 'escalated_at', 'organization_name',
        )

    def _agent(self, obj):
        request = self.context.get('request')
        return bool(request and services.is_agent(obj, request.user))

    def get_organization_name(self, obj):
        return obj.organization.title if obj.organization_id else None

    def get_comments(self, obj):
        qs = obj.comments.select_related('author__department', 'ticket').prefetch_related('attachments')
        if not self._agent(obj):
            qs = qs.filter(is_internal=False)
        return CommentSerializer(qs, many=True, context=self.context).data

    def get_attachments(self, obj):
        qs = obj.attachments.select_related('uploaded_by')
        if not self._agent(obj):
            qs = qs.filter(is_internal=False)
        return AttachmentSerializer(qs, many=True, context=self.context).data

    def get_activities(self, obj):
        qs = obj.activities.select_related('actor')
        if not self._agent(obj):
            qs = qs.filter(is_internal=False).exclude(
                action__in=[TicketActivity.A_DEPT_STATUS, TicketActivity.A_ESCALATED])
        return ActivitySerializer(qs, many=True, context=self.context).data

    def get_sla(self, obj):
        return {
            'first_response_due_at': obj.first_response_due_at,
            'first_response_at': obj.first_response_at,
            'first_response_overdue': obj.first_response_overdue,
            'due_at': obj.due_at,
            'is_overdue': obj.is_overdue,
            'resolved_at': obj.resolved_at,
        }

    def get_permissions(self, obj):
        request = self.context.get('request')
        user = request.user
        agent = services.is_agent(obj, user)
        requester = services.is_requester(obj, user)
        active = obj.status not in Ticket.FINAL_STATUSES
        transitions = services.allowed_transitions(obj, user)
        my_row = next((r for r in obj.assignee_links.all() if r.user_id == user.id), None)
        labels = dict(Ticket.STATUS_CHOICES)
        return {
            'user_id': user.id,
            'is_agent': agent,
            'is_requester': requester,
            'is_admin': services.is_ticket_admin(user),
            'can_edit': active and (agent or (requester and obj.status == Ticket.STATUS_NEW)),
            'can_assign': active and services.can_assign(obj, user),
            'can_set_assignee': active and agent and obj.status != Ticket.STATUS_RESOLVED,
            'can_comment': active and (agent or requester or obj.watchers.filter(id=user.id).exists()),
            'can_comment_internal': active and agent,
            'can_take': active and services.can_take(obj, user),
            'can_release': active and my_row is not None and obj.status != Ticket.STATUS_RESOLVED,
            'my_assignee_status': my_row.status if my_row else None,
            'can_set_my_status': active and my_row is not None and obj.status != Ticket.STATUS_RESOLVED,
            'can_rate': requester and obj.status in (Ticket.STATUS_RESOLVED, Ticket.STATUS_CLOSED),
            'is_watching': obj.watchers.filter(id=user.id).exists(),
            'transitions': [{'value': t, 'label': labels[t]} for t in transitions],
        }


class TicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    ticket_type = serializers.ChoiceField(choices=Ticket.TYPE_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=Ticket.PRIORITY_CHOICES, required=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.filter(is_active=True), required=False, allow_null=True)
    departments = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    watchers = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=30), required=False, max_length=10)

    def validate_title(self, v):
        if len(v.strip()) < 5:
            raise serializers.ValidationError('Mövzu ən azı 5 simvol olmalıdır.')
        return v

    def validate_description(self, v):
        if len(v.strip()) < 10:
            raise serializers.ValidationError('Təsvir ən azı 10 simvol olmalıdır.')
        return v


class TicketUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False)
    ticket_type = serializers.ChoiceField(choices=Ticket.TYPE_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=Ticket.PRIORITY_CHOICES, required=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.filter(is_active=True), required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=30), required=False, max_length=10)


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Ticket.STATUS_CHOICES)
    comment = serializers.CharField(required=False, allow_blank=True, default='')


class DepartmentAssignSerializer(serializers.Serializer):
    department = serializers.IntegerField()
    assignee = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class SetDepartmentsSerializer(serializers.Serializer):
    departments = DepartmentAssignSerializer(many=True)


class DepartmentStatusSerializer(serializers.Serializer):
    department = serializers.IntegerField()
    status = serializers.ChoiceField(choices=TicketDepartment.STATUS_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')


class AssigneesAddSerializer(serializers.Serializer):
    users = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=20)


class ReleaseSerializer(serializers.Serializer):
    user = serializers.IntegerField(required=False, allow_null=True)


class AssigneeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TicketAssignee.STATUS_CHOICES)
    user = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default='', max_length=500)


class AssigneeSerializer(serializers.Serializer):
    assignee = serializers.IntegerField(allow_null=True)


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    is_internal = serializers.BooleanField(required=False, default=False)


class RatingSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')


class WatchersSerializer(serializers.Serializer):
    users = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
