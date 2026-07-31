from rest_framework import serializers
from authentication.serializers import UserShortSerializer
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)

    class Meta:
        model = ActivityLog
        fields = (
            "id",
            "user",
            "user_username_snapshot",
            "action_type",
            "action_type_display",
            "module_code",
            "module_title",
            "sub_module_title",
            "description",
            "object_repr",
            "changes",
            "request_method",
            "request_path",
            "status_code",
            "ip_address",
            "user_agent",
            "timestamp",
        )