from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source="get_notification_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id", "notification_type", "notification_type_display",
            "title", "body", "link",
            "related_app", "related_object_id",
            "is_read", "read_at", "created_at",
        )
        read_only_fields = fields