from rest_framework import serializers
from .models import Inventory, InventoryOwnerPerson, InventoryOwnerDepartment


class InventoryOwnerPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryOwnerPerson
        fields = ('id', 'full_name')


class InventoryOwnerDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryOwnerDepartment
        fields = ('id', 'name')


class InventorySerializer(serializers.ModelSerializer):
    owner_display = serializers.CharField(read_only=True)
    owner_type_display = serializers.CharField(source='get_owner_type_display', read_only=True)

    owner_person = InventoryOwnerPersonSerializer(read_only=True)
    owner_department = InventoryOwnerDepartmentSerializer(read_only=True)

    # Yazı zamanı: frontend sadəcə mətn göndərir, biz get_or_create edirik
    owner_person_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    owner_department_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    created_by_name = serializers.CharField(source='created_by.name', read_only=True, default='')
    updated_by_name = serializers.CharField(source='updated_by.name', read_only=True, default='')

    class Meta:
        model = Inventory
        fields = (
            'id', 'product_name', 'inventory_number',
            'owner_type', 'owner_type_display', 'owner_display',
            'owner_person', 'owner_department',
            'owner_person_name', 'owner_department_name',
            'created_by', 'created_by_name',
            'updated_by', 'updated_by_name',
            'created_at', 'updated_at',
        )
        read_only_fields = ('inventory_number', 'created_by', 'updated_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        owner_type = attrs.get('owner_type', getattr(self.instance, 'owner_type', None))

        if owner_type == Inventory.OWNER_PERSON:
            has_existing = self.instance and self.instance.owner_person_id
            if not attrs.get('owner_person_name') and not has_existing:
                raise serializers.ValidationError({'owner_person_name': 'Şəxs seçilməlidir.'})
        elif owner_type == Inventory.OWNER_DEPARTMENT:
            has_existing = self.instance and self.instance.owner_department_id
            if not attrs.get('owner_department_name') and not has_existing:
                raise serializers.ValidationError({'owner_department_name': 'Departament seçilməlidir.'})
        # OWNER_APPARATUS üçün əlavə seçim tələb olunmur

        return attrs

    def _resolve_owner(self, validated_data):
        owner_type = validated_data.get('owner_type', getattr(self.instance, 'owner_type', None))
        person_name = validated_data.pop('owner_person_name', None)
        department_name = validated_data.pop('owner_department_name', None)

        if owner_type == Inventory.OWNER_PERSON:
            validated_data['owner_department'] = None
            if person_name:
                person, _ = InventoryOwnerPerson.objects.get_or_create(full_name=person_name.strip())
                validated_data['owner_person'] = person
        elif owner_type == Inventory.OWNER_DEPARTMENT:
            validated_data['owner_person'] = None
            if department_name:
                department, _ = InventoryOwnerDepartment.objects.get_or_create(name=department_name.strip())
                validated_data['owner_department'] = department
        else:  # aparat
            validated_data['owner_person'] = None
            validated_data['owner_department'] = None

        return validated_data

    def create(self, validated_data):
        validated_data = self._resolve_owner(validated_data)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        validated_data['created_by'] = user
        validated_data['updated_by'] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._resolve_owner(validated_data)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        validated_data['updated_by'] = user
        return super().update(instance, validated_data)