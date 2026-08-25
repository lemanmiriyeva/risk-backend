from datetime import time

from django.utils import timezone
from rest_framework import serializers

from .models import AttendancePermission

from authentication.models import User, Department

from .models import (
    AttendancePermissionOrganizationConfig,
    AttendancePermissionDepartmentConfig,
)

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

class AttendancePermissionUserShortSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    department_name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "name",
            "firstname",
            "lastname",
            "department",
            "department_name",
            "role_name",
            "is_active",
        )

    def get_department_name(self, obj):
        return obj.department.title if obj.department else None

    def get_role_name(self, obj):
        return obj.role.title if obj.role else None


class AttendancePermissionOrganizationConfigSerializer(serializers.ModelSerializer):
    apparatus_head_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendancePermissionOrganizationConfig
        fields = (
            "id",
            "organization",
            "apparatus_head_enabled",
            "apparatus_head",
            "apparatus_head_name",
        )
        read_only_fields = (
            "id",
            "organization",
            "apparatus_head_name",
        )

    def get_apparatus_head_name(self, obj):
        return obj.apparatus_head.name if obj.apparatus_head else None

    def validate_apparatus_head(self, value):
        request = self.context.get("request")

        if not value:
            return value

        if request and value.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                "Aparat rəhbəri sizin qurumunuza aid olmalıdır."
            )

        if not value.is_active:
            raise serializers.ValidationError(
                "Seçilən Aparat rəhbəri aktiv istifadəçi deyil."
            )

        return value

    def validate(self, attrs):
        enabled = attrs.get(
            "apparatus_head_enabled",
            getattr(self.instance, "apparatus_head_enabled", True),
        )

        apparatus_head = attrs.get(
            "apparatus_head",
            getattr(self.instance, "apparatus_head", None),
        )

        if enabled and not apparatus_head:
            raise serializers.ValidationError({
                "apparatus_head": "Aparat rəhbəri aktivdirsə, şəxs seçilməlidir."
            })

        return attrs


class AttendancePermissionDepartmentConfigSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(
        source="department.title",
        read_only=True,
    )

    manager_name = serializers.SerializerMethodField()
    replacement_user_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendancePermissionDepartmentConfig
        fields = (
            "id",
            "organization",
            "department",
            "department_name",
            "manager_enabled",
            "manager_name",
            "replacement_user",
            "replacement_user_name",
        )
        read_only_fields = (
            "id",
            "organization",
            "department_name",
            "manager_name",
            "replacement_user_name",
        )

    def get_manager_name(self, obj):
        return obj.department.manager.name if obj.department.manager else None

    def get_replacement_user_name(self, obj):
        return (
            obj.replacement_user.name
            if obj.replacement_user
            else None
        )

    def validate_replacement_user(self, value):
        if not value:
            return value

        request = self.context.get("request")

        if request:
            if value.organization_id != request.user.organization_id:
                raise serializers.ValidationError(
                    "Əvəzləyici şəxs sizin qurumunuza aid olmalıdır."
                )

        if not value.is_active:
            raise serializers.ValidationError(
                "Əvəzləyici şəxs aktiv istifadəçi deyil."
            )

        return value

    def validate(self, attrs):
        manager_enabled = attrs.get(
            "manager_enabled",
            getattr(self.instance, "manager_enabled", True),
        )

        replacement_user = attrs.get(
            "replacement_user",
            getattr(self.instance, "replacement_user", None),
        )

        if not manager_enabled and not replacement_user:
            raise serializers.ValidationError({
                "replacement_user": (
                    "Şöbə müdiri deaktivdirsə, əvəzləyici şəxs seçilməlidir."
                )
            })

        return attrs