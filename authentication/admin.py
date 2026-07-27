from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils.html import format_html

from .models import User, Department, Role, PasswordReset,  SpecialPermission


@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    search_fields = [ 'username', 'firstname', 'lastname', 'email']
    list_display = ['firstname', 'lastname', 'username', 'phone_number', 'email', 'update_date']
    list_display_links = ['username', 'email', 'phone_number']
    list_filter = ("role", "department", "is_active", "is_superuser", "is_staff")
    readonly_fields = ('image_tag',)

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "-"
    image_tag.short_description = 'Şəkil'

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),

        ("Şəxsi məlumatlar", {"fields": ("firstname", "lastname", "phone_number","gender","birth_date", "image", "image_tag")}),
        (
            "İcazələr",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "department",
                    "role",
                    "groups",
                    "user_permissions",
                    "special_permissions",
                ),
            },
        ),

    )

    add_fieldsets = (
        ("Əsas", {"fields": ("username", "email", "password1", "password2", "department", "role")}),
        ("Şəxsi məlumatlar", {"fields": ("firstname", "lastname", "phone_number","birth_date")}),
        (
            "İcazələr",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                    "special_permissions",
                ),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser or request.user.has_perm('authentication.view_permissions_section'):
            return fieldsets
        return tuple(fs for fs in fieldsets if fs[0] != "İcazələr")

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not (request.user.is_superuser or request.user.has_perm('authentication.view_permissions_section')):
            readonly += [
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
                "special_permissions",
            ]
        return readonly

@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ("title","order",)
    fieldsets = [
        (None, {
            'fields': (
                "title",
                "order",
            ),
        }),
    ]


@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ("name", "codename", "content_type",)
    search_fields = ("codename", "content_type__app_label")


@admin.register(PasswordReset)
class PasswordResetAdmin(ModelAdmin):
    list_display = ('email', 'token', 'created_at', 'active',)
    search_fields = ('token', 'email',)
    list_filter = ('email', 'active',)


# admin.site.register(Department)
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'shortname', 'parent', 'manager']
    list_filter = ['parent']
    search_fields = ['title', 'shortname']
    autocomplete_fields = ['parent', 'manager']
admin.site.register(SpecialPermission)
# admin.site.unregister(Group)

