from rest_framework.serializers import ModelSerializer, SerializerMethodField
from authentication.models import User, Role, Department, Organization
from core.permissions import get_module_permissions


class RoleSerializer(ModelSerializer):

    class Meta:
        model = Role
        depth = 2
        fields = ("id", "title", "order")


class UserShortSerializer(ModelSerializer):
    department_name = SerializerMethodField()
    role_name = SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "name", "email", "department_name", "role_name")

    def get_department_name(self, obj):
        return obj.department.shortname if obj.department else None

    def get_role_name(self, obj):
        return obj.role.title if obj.role else None


class DepartmentBaseSerializer(ModelSerializer):
    manager = UserShortSerializer(read_only=True)

    class Meta:
        model = Department
        fields = ("id", "title", "manager")


class MainDepartmentSerializer(DepartmentBaseSerializer):
    curator = UserShortSerializer(read_only=True)

    class Meta(DepartmentBaseSerializer.Meta):
        fields = DepartmentBaseSerializer.Meta.fields + ("shortname",)


class DepartmentSimpleSerializer(DepartmentBaseSerializer):
    pass


from rest_framework import serializers


class DepartmentListSerializer(DepartmentBaseSerializer):
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta(DepartmentBaseSerializer.Meta):
        fields = DepartmentBaseSerializer.Meta.fields + ("order", "parent", "children", "shortname",)

    def get_parent(self, obj):
        if obj.parent is not None:
            return {
                "id": obj.parent.id,
                "title": obj.parent.title,
            }
        return None

    def get_children(self, obj):
        children = obj.children.all()
        return DepartmentSimpleSerializer(children, many=True).data


class UserSerializer(ModelSerializer):
    main_department = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()

    class Meta:
        model = User
        depth = 2
        fields = (
          "id", "username", "email", "firstname", "lastname", "is_active", "phone_number", "birth_date", "image",
          "role", "department", "main_department", "name",
          "special_permissions", 'permissions',
          "two_fa_confirmed", "is_approved",
          "organization", "is_org_admin", "is_superuser",
        )

    def get_main_department(self, obj):
        if not obj.department:
            return None
        main_dep = obj.department if obj.department.parent is None else obj.department.parent
        return MainDepartmentSerializer(main_dep).data

    def get_permissions(self, obj):
        return get_module_permissions(obj)

    def get_organization(self, obj):
        if not obj.organization:
            return None
        return {"id": obj.organization.id, "title": obj.organization.title}

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if rep.get("department") and rep.get("main_department"):
            if rep["department"]["id"] == rep["main_department"]["id"]:
                rep.pop("department")
        return rep


class OrganizationSerializer(ModelSerializer):
    employee_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id", "title", "short_name", "is_active",
            "authorized_person_name", "authorized_person_position",
            "employee_count",
        )
        extra_kwargs = {
            "authorized_person_name": {"required": True, "allow_blank": False},
        }

    def get_employee_count(self, obj):
        return obj.users.count()


class OrganizationDetailSerializer(OrganizationSerializer):
    employees = serializers.SerializerMethodField()

    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + ("employees",)

    def get_employees(self, obj):
        return UserShortSerializer(obj.users.all(), many=True).data


class PasswordResetRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=128)


class OrgUserSerializer(ModelSerializer):
    organization = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "firstname", "lastname", "name",
            "phone_number", "birth_date", "is_active", "role", "role_name",
            "department", "department_name", "fin_kod", "is_org_admin", "organization",
            "two_fa_confirmed", "is_approved",
        )
        read_only_fields = ("two_fa_confirmed", "is_approved")

    def get_organization(self, obj):
        if not obj.organization:
            return None
        return {"id": obj.organization.id, "title": obj.organization.title}

    def get_role_name(self, obj):
        return obj.role.title if obj.role else None

    def get_department_name(self, obj):
        return obj.department.title if obj.department else None