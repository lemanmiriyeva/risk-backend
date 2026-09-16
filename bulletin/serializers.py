from rest_framework import serializers

from authentication.models import User
from .models import BulletinCategory, Circular, NewsPost


class BulletinCategorySerializer(serializers.ModelSerializer):
    documents_count = serializers.IntegerField(source="circulars.count", read_only=True)

    class Meta:
        model = BulletinCategory
        fields = (
            "id",
            "key",
            "label",
            "plural_label",
            "description",
            "icon",
            "order",
            "is_active",
            "documents_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "documents_count", "created_at", "updated_at")

    def validate_key(self, value):
        return value.strip().lower().replace(" ", "_")


class CircularSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=BulletinCategory.objects.all())
    category_key = serializers.CharField(source="category.key", read_only=True)
    category_label = serializers.CharField(source="category.label", read_only=True)
    category_icon = serializers.CharField(source="category.icon", read_only=True)
    organization_name = serializers.CharField(source="organization.title", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True, default=None)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Circular
        fields = (
            "id",
            "category",
            "category_key",
            "category_label",
            "category_icon",
            "title",
            "number",
            "document_date",
            "file",
            "file_url",
            "organization",
            "organization_name",
            "is_active",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"file": {"write_only": True, "required": False}}

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class NewsPostSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.title", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = NewsPost
        fields = (
            "id",
            "title",
            "summary",
            "body",
            "image",
            "image_url",
            "published_at",
            "organization",
            "organization_name",
            "is_active",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"image": {"write_only": True, "required": False}}

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class BirthdayUserSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    # Cari ilə uyğunlaşdırılmış doğum günü (yalnız gün/ay əhəmiyyətlidir,
    # frontend-də sıralama və "bu gün" bildirişi üçün istifadə olunur).
    is_today = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "name", "birth_date", "department_name", "role_name",
            "image_url", "is_today",
        )

    def get_department_name(self, obj):
        return obj.department.title if obj.department else None

    def get_role_name(self, obj):
        return obj.role.title if obj.role else None

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def get_is_today(self, obj):
        today = self.context.get("today")
        return bool(
            today and obj.birth_date
            and obj.birth_date.month == today.month
            and obj.birth_date.day == today.day
        )