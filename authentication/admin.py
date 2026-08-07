from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Organization,
    Department,
    Role,
    SpecialPermission,
    PasswordReset,
    LoginAttempt,
)


class UserInline(admin.TabularInline):
    model = User
    fk_name = "organization"
    extra = 0
    fields = ("username", "name_display", "email", "department", "role", "is_active", "is_org_admin","is_apparatus_head", "is_approved")
    readonly_fields = ("name_display",)
    show_change_link = True
    can_delete = False

    def name_display(self, obj):
        return obj.name
    name_display.short_description = "Ad Soyad"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("title", "short_name", "is_active", "user_count")
    search_fields = ("title", "short_name")
    list_filter = ("is_active",)
    inlines = (UserInline,)

    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = "İstifadəçi sayı"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("title", "shortname", "parent", "manager", "order")
    search_fields = ("title", "shortname", "unique_code")
    list_filter = ("parent",)
    autocomplete_fields = ("parent", "manager")
    ordering = ("order",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("title", "parent", "order")
    search_fields = ("title",)
    list_filter = ("parent",)


@admin.register(SpecialPermission)
class SpecialPermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "codename")
    search_fields = ("name", "codename")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = (
        "username", "name", "email", "organization", "department",
        "role", "is_active", "is_org_admin", "two_fa_confirmed", "is_approved", "is_apparatus_head","is_staff",
    )
    list_filter = ("organization", "department", "role", "is_active", "is_org_admin", "is_approved", "is_apparatus_head","two_fa_confirmed")
    search_fields = ("username", "email", "firstname", "lastname", "phone_number")
    ordering = ("id",)
    autocomplete_fields = ("organization", "department", "role")
    filter_horizontal = ("special_permissions", "groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Şəxsi məlumat", {
            "fields": (
                "firstname", "lastname", "email", "phone_number",
                "birth_date", "gender", "image",
            )
        }),
        ("Qurum və vəzifə", {
            "fields": ("organization", "department", "role", "is_org_admin", "is_apparatus_head"),
        }),
        ("İcazələr", {
            "fields": (
                "is_active", "is_staff", "is_superuser", "is_approved",
                "special_permissions", "groups", "user_permissions",
            )
        }),
        ("2FA", {
            "fields": ("two_fa_confirmed", "two_fa_secret"),
        }),
        ("Tarixlər", {
            "fields": ("join_date", "update_date", "last_login"),
        }),
    )
    readonly_fields = ("join_date", "update_date", "last_login")

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email", "firstname", "lastname",
                "password1", "password2", "organization", "department",
            ),
        }),
    )


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ("email", "token", "created_at", "active")
    search_fields = ("email",)
    list_filter = ("active",)
    readonly_fields = ("created_at",)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username", "ip", "timestamp", "last_login", "fails", "locked")
    search_fields = ("username", "ip")
    list_filter = ("locked",)
    readonly_fields = ("timestamp", "last_login")