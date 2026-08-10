from rest_framework import serializers

from .models import Operation, OperationApprovalStep


class OperationApprovalStepSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    approver_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = OperationApprovalStep
        fields = (
            "id", "step_number", "role_label",
            "approver", "approver_name",
            "status", "status_display",
            "reviewed_by", "reviewed_by_name", "comment", "reviewed_at",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_approver_name(self, obj):
        return obj.approver.name if obj.approver else None

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.name if obj.reviewed_by else None


class OperationSerializer(serializers.ModelSerializer):
    """Əməliyyatlar siyahısı və detay üçün - oxumaq məqsədlidir."""

    operation_type_display = serializers.CharField(source="get_operation_type_display", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    user_name = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    content_type_name = serializers.SerializerMethodField()
    approval_steps = OperationApprovalStepSerializer(many=True, read_only=True)
    can_review = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = (
            "id",
            "operation_type", "operation_type_display",
            "action", "action_display",
            "status", "status_display",
            "module", "category_code", "category_title",
            "user", "user_name", "user_username_snapshot",
            "organization", "organization_name",
            "content_type", "content_type_name", "object_id", "object_repr",
            "description", "changes",
            "total_steps", "current_step",
            "approval_steps", "can_review",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.name if obj.user else obj.user_username_snapshot

    def get_organization_name(self, obj):
        return obj.organization.title if obj.organization else None

    def get_content_type_name(self, obj):
        return obj.content_type.model if obj.content_type else None

    def get_can_review(self, obj):
        """Frontend-in təsdiq/rədd düymələrini göstərib-göstərməməsi üçün."""
        if obj.operation_type != Operation.TYPE_APPROVAL:
            return False
        if obj.status not in (Operation.STATUS_PENDING, Operation.STATUS_IN_PROGRESS):
            return False
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        step = obj.approval_steps.filter(step_number=obj.current_step).first()
        if not step:
            return False
        user = request.user
        if user.is_superuser:
            return True
        return step.approver_id == user.id


class OperationReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")