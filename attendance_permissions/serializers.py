from datetime import time

from django.utils import timezone
from rest_framework import serializers

from .models import AttendancePermission


class AttendancePermissionSerializer(serializers.ModelSerializer):
    """Oxumaq üçün - siyahı və detay."""
    user_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    department_reviewed_by_name = serializers.SerializerMethodField()
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
            "department_reviewed_by", "department_reviewed_by_name",
            "department_reviewed_at", "department_review_comment",
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

    def get_department_reviewed_by_name(self, obj):
        return obj.department_reviewed_by.name if obj.department_reviewed_by else None

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.name if obj.reviewed_by else None

    def get_can_review(self, obj):
        """Frontend-in təsdiq/rədd düymələrini göstərib-göstərməməsi üçün."""
        request = self.context.get("request")
        if not request:
            return False
        from .permissions import can_review
        allowed, _ = can_review(request.user, obj)
        return allowed


class AttendancePermissionCreateSerializer(serializers.ModelSerializer):
    """Yaratmaq üçün - user/department/organization/status view tərəfindən təyin olunur."""

    WORK_START = time(9, 0)
    WORK_END = time(18, 0)

    class Meta:
        model = AttendancePermission
        fields = ("date", "start_time", "end_time", "location", "reason")
        extra_kwargs = {
            "reason": {"required": False, "allow_blank": True},
            "location": {"required": False, "allow_blank": True},
        }

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Keçmiş tarix üçün icazə sorğusu yaradıla bilməz.")
        return value

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if start_time and (start_time < self.WORK_START or start_time > self.WORK_END):
            raise serializers.ValidationError(
                {"start_time": "Başlanğıc saatı 09:00 - 18:00 aralığında olmalıdır."}
            )
        if end_time and (end_time < self.WORK_START or end_time > self.WORK_END):
            raise serializers.ValidationError(
                {"end_time": "Bitmə saatı 09:00 - 18:00 aralığında olmalıdır."}
            )
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "Bitmə saatı başlanğıc saatından sonra olmalıdır."}
            )
        return attrs


class AttendancePermissionReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")