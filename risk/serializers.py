from rest_framework import serializers
from authentication.serializers import UserShortSerializer
from inventory.models import Inventory
from .models import Risk, RiskLog


class OrganizationShortSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class InventoryShortSerializer(serializers.ModelSerializer):
    owner_display = serializers.CharField(read_only=True)

    class Meta:
        model = Inventory
        fields = ("id", "inventory_number", "product_name", "owner_display")


class RiskSerializer(serializers.ModelSerializer):
    created_by = UserShortSerializer(read_only=True)
    updated_by = UserShortSerializer(read_only=True)
    organization = OrganizationShortSerializer(read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    treatment_option_display = serializers.CharField(source='get_treatment_option_display', read_only=True)

    inventory = InventoryShortSerializer(read_only=True)
    inventory_id = serializers.PrimaryKeyRelatedField(
        queryset=Inventory.objects.all(), source='inventory', write_only=True
    )

    class Meta:
        model = Risk
        fields = (
            "id",
            "designation",
            "legal_basis",
            "international_framework",
            "national_legal_reference",
            "asset_value",
            "probability",
            "impact",
            "risk_degree",
            "risk_level",
            "risk_level_display",
            "treatment_option",
            "treatment_option_display",
            "residual_risk",
            "update_frequency",
            "incident_notification_notes",
            "standard_references",
            "inventory",
            "inventory_id",
            "organization",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "risk_degree", "risk_level", "organization", "created_by", "updated_by", "created_at", "updated_at",
        )

    def _validate_scale(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("1 ilə 5 arasında olmalıdır")
        return value

    def validate_asset_value(self, value):
        return self._validate_scale(value)

    def validate_probability(self, value):
        return self._validate_scale(value)

    def validate_impact(self, value):
        return self._validate_scale(value)


class RiskLogSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    organization = OrganizationShortSerializer(read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)

    class Meta:
        model = RiskLog
        fields = (
            "id",
            "risk",
            "risk_id_ref",
            "risk_designation",
            "risk_snapshot",
            "organization",
            "user",
            "user_username_snapshot",
            "action_type",
            "action_type_display",
            "changes",
            "ip_address",
            "user_agent",
            "timestamp",
        )