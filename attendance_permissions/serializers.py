from rest_framework import serializers

from .models import AttendancePermission


class AttendancePermissionSerializer(serializers.ModelSerializer):
    """Oxumaq üçün - siyahı və detay."""
    user_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    can_review = serializers.SerializerMethodField()

    class Meta:
        model = AttendancePermission
        fields = (
            "id", "user", "user_name",
            "department", "department_name", "organization", "organization_name",
            "date", "start_time", "end_time", "location", "reason",
            "status", "status_display",
            "reviewed_by", "reviewed_by_name", "reviewed_at", "review_comment",
            "can_review",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.name

    def get_department_name(self, obj):
        return obj.department.title if obj.department else None

    def get_organization_name(self, obj):
        return obj.organization.title if obj.organization else None

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.name if obj.reviewed_by else None

    def get_can_review(self, obj):
        """Frontend-in təsdiq/rədd düymələrini göstərib-göstərməməsi üçün."""
        request = self.context.get("request")
        if not request:
            return False
        from .permissions import can_review
        allowed, _ = can_review(request.user, obj)
        return allowed and obj.status == AttendancePermission.STATUS_PENDING


class AttendancePermissionCreateSerializer(serializers.ModelSerializer):
    """Yaratmaq üçün - user/department/organization/status view tərəfindən təyin olunur."""

    class Meta:
        model = AttendancePermission
        fields = ("date", "start_time", "end_time", "location", "reason")
        extra_kwargs = {
            "reason": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError(
                {"end_time": "Bitmə saatı başlanğıc saatından sonra olmalıdır."}
            )
        return attrs


class AttendancePermissionReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")