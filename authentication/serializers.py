from rest_framework.serializers import ModelSerializer, SerializerMethodField
from authentication.models import User, Role, Department, Organization
from core.permissions import get_module_permissions


class RoleSerializer(ModelSerializer):
    class Meta:
        model = Role
        depth = 2
        fields = ("id", "title", "order", "is_manager_role")


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
    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        depth = 2
        fields = (
          "id", "username", "email", "firstname", "lastname", "is_active", "phone_number", "birth_date", "image",
          "fin_kod", "gender",
          "role", "department", "main_department", "name",
          "special_permissions", 'permissions',
          "two_fa_confirmed", "is_approved",
          "organization", "is_org_admin", "is_superuser",
        )

    def get_image(self, obj):
        """
        request.build_absolute_uri() Apache/proxy Host başlığını düzgün ötürmədiyi hallarda
        server-in daxili ünvanını (məs. 127.0.0.1:8000) qaytara bilir. Ona görə mümkün olsa
        settings.BACKEND_BASE_URL (env-dən) istifadə edirik - bu, proxy konfiqurasiyasından asılı olmayan
        sabit/etibarlı mənbədir. Təyin olunmayıbsa, əvvəlki davranışa (request host) geri qayıdırıq.
        """
        if not obj.image:
            return None
        from django.conf import settings
        if getattr(settings, "BACKEND_BASE_URL", ""):
            return f"{settings.BACKEND_BASE_URL}{obj.image.url}"
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

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


class UserProfileUpdateSerializer(ModelSerializer):
    """
    "Şəxsi kabinet" səhifəsində istifadəçinin ÖZÜ öz məlumatlarını yeniləməsi üçün.
    Qəsdən çox məhdud sahə siyahısı: username, email, fin_kod və qurumla bağlı heç bir
    sahə (organization, department, role, is_org_admin və s.) BURAYA DAXIL EDİLMİR - onlar
    yalnız admin panelindən dəyişdirilə bilər. Yalnız şəxsi/əlaqə məlumatları redaktə olunur.
    """

    class Meta:
        model = User
        fields = ("firstname", "lastname", "phone_number", "birth_date", "gender", "image")
        extra_kwargs = {
            "firstname": {"required": False, "allow_blank": True},
            "lastname": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_null": True},
            "birth_date": {"required": False, "allow_null": True},
            "gender": {"required": False, "allow_null": True},
            "image": {"required": False, "allow_null": True},
        }


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


class TwoFAResetRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=128)
    password = serializers.CharField(max_length=128)


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


# ---------------------------------------------------------------------------
# İnzibatçı paneli: Departament və Vəzifə (Role) idarəetməsi.
# Departament və vəzifə quruma bağlıdır - hər qurumun öz "ana" (parent=None)
# departament(lər)i, onların child departamentləri, və hər departamentin öz
# vəzifələri (Role.department) olur.
# ---------------------------------------------------------------------------

class RoleAdminSerializer(ModelSerializer):
    """Vəzifələr (Role) - departamentə bağlı, oxuma üçün."""
    department_title = SerializerMethodField()
    organization = SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id", "title", "order", "is_manager_role", "parent",
            "department", "department_title", "organization",
        )

    def get_department_title(self, obj):
        return obj.department.title if obj.department else None

    def get_organization(self, obj):
        org = obj.department.organization if obj.department else None
        if not org:
            return None
        return {"id": org.id, "title": org.title}


class RoleWriteSerializer(ModelSerializer):
    """Vəzifə yaratmaq/redaktə etmək üçün. `department` mütləqdir."""

    class Meta:
        model = Role
        fields = ("id", "title", "department", "is_manager_role", "parent", "order")
        extra_kwargs = {
            "department": {"required": True, "allow_null": False},
            "title": {"required": True, "allow_blank": False},
        }

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        department = attrs.get("department", getattr(self.instance, "department", None))
        if parent and department and parent.department_id and parent.department_id != department.id:
            raise serializers.ValidationError(
                {"parent": "Valideyn vəzifə fərqli departamentə aiddir."}
            )
        return attrs


class DepartmentAdminSerializer(ModelSerializer):
    """Departamentlərin siyahısı/detalı üçün - qurum, valideyn, child-lar və vəzifələr daxil olmaqla."""
    organization_title = SerializerMethodField()
    parent_title = SerializerMethodField()
    manager_name = SerializerMethodField()
    roles = RoleAdminSerializer(many=True, read_only=True)
    children = SerializerMethodField()
    employee_count = SerializerMethodField()

    class Meta:
        model = Department
        fields = (
            "id", "title", "shortname", "organization", "organization_title",
            "parent", "parent_title", "manager", "manager_name", "order",
            "unique_code", "roles", "children", "employee_count",
        )

    def get_organization_title(self, obj):
        return obj.organization.title if obj.organization else None

    def get_parent_title(self, obj):
        return obj.parent.title if obj.parent else None

    def get_manager_name(self, obj):
        return obj.manager.name if obj.manager else None

    def get_children(self, obj):
        children = obj.children.all().order_by("order", "title")
        return DepartmentAdminSerializer(children, many=True).data

    def get_employee_count(self, obj):
        return obj.user_set.count()


class DepartmentWriteSerializer(ModelSerializer):
    """Departament yaratmaq/redaktə etmək üçün."""

    class Meta:
        model = Department
        fields = ("id", "title", "shortname", "organization", "parent", "manager", "order", "unique_code")
        extra_kwargs = {
            "title": {"required": True, "allow_blank": False},
        }

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        organization = attrs.get("organization", getattr(self.instance, "organization", None))

        if parent:
            if not organization:
                organization = parent.organization
                attrs["organization"] = organization
            elif parent.organization_id and organization and parent.organization_id != organization.id:
                raise serializers.ValidationError(
                    {"parent": "Valideyn departament fərqli quruma aiddir."}
                )
            if self.instance and parent_id_equals_self(self.instance, parent):
                raise serializers.ValidationError({"parent": "Departament öz-özünün valideyni ola bilməz."})
        elif not organization:
            raise serializers.ValidationError({"organization": "Qurum seçilməlidir."})

        return attrs


def parent_id_equals_self(instance, parent):
    node = parent
    seen = set()
    while node is not None:
        if node.id == instance.id:
            return True
        if node.id in seen:
            break
        seen.add(node.id)
        node = node.parent
    return False