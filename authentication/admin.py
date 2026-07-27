from django import forms
from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils.html import format_html

from .models import User, Department, Role, PasswordReset,  SpecialPermission


RISK_APP_LABEL = 'risk'
RISK_VIEW_CODENAME = 'view_risk'
RISK_EDIT_CODENAMES = ['add_risk', 'change_risk', 'delete_risk']
RISK_LOG_CODENAME = 'view_risklog'


class UserAdminForm(forms.ModelForm):

    riske_baxis = forms.BooleanField(
        required=False, label="Riskə baxış",
        help_text="Yalnız 'Risk cədvəlinə baxış' moduluna (bütün sahələr, Excel ixrac) baxış icazəsi verir.",
    )
    risk_redakte = forms.BooleanField(
        required=False, label="Risk redaktə",
        help_text="'Risklərə baxış' moduluna tam giriş - risk yaratmaq, redaktə etmək və silmək icazəsi verir.",
    )
    loglara_baxis = forms.BooleanField(
        required=False, label="Loqlara baxış",
        help_text="Risk Reyestri loqlarına (tarixçəsinə) baxış icazəsi verir.",
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            perms = set(
                Permission.objects.filter(
                    content_type__app_label=RISK_APP_LABEL,
                ).filter(user=self.instance).values_list('codename', flat=True)
            )
            self.fields['riske_baxis'].initial = RISK_VIEW_CODENAME in perms
            self.fields['risk_redakte'].initial = all(c in perms for c in RISK_EDIT_CODENAMES)
            self.fields['loglara_baxis'].initial = RISK_LOG_CODENAME in perms

    def _apply_risk_permissions(self, user):
        risk_perms = Permission.objects.filter(content_type__app_label=RISK_APP_LABEL)

        def set_perm(codename, enabled):
            try:
                perm = risk_perms.get(codename=codename)
            except Permission.DoesNotExist:
                return
            if enabled:
                user.user_permissions.add(perm)
            else:
                user.user_permissions.remove(perm)

        set_perm(RISK_VIEW_CODENAME, self.cleaned_data.get('riske_baxis'))
        for codename in RISK_EDIT_CODENAMES:
            set_perm(codename, self.cleaned_data.get('risk_redakte'))
        # Redaktə icazəsi olan istifadəçi hər zaman görə də bilməlidir
        if self.cleaned_data.get('risk_redakte'):
            set_perm(RISK_VIEW_CODENAME, True)
        set_perm(RISK_LOG_CODENAME, self.cleaned_data.get('loglara_baxis'))

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self._apply_risk_permissions(user)
        else:
            original_save_m2m = self.save_m2m if hasattr(self, 'save_m2m') else None

            def save_m2m():
                if original_save_m2m:
                    original_save_m2m()
                self._apply_risk_permissions(user)

            self.save_m2m = save_m2m
        return user


@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    form = UserAdminForm
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
        (
            "Risk Reyestri Modulu İcazələri",
            {
                "description": (
                    "Bu icazələr Group (vəzifə) adından asılı deyil - Group adları "
                    "dəyişdirilsə belə etibarlı qalır. 'Riskə baxış' seçildikdə "
                    "istifadəçi yalnız 'Risk cədvəlinə baxış' moduluna keçid edə bilər."
                ),
                "fields": ("riske_baxis", "risk_redakte", "loglara_baxis"),
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
        (
            "Risk Reyestri Modulu İcazələri",
            {
                "description": (
                    "Bu icazələr Group (vəzifə) adından asılı deyil - Group adları "
                    "dəyişdirilsə belə etibarlı qalır. 'Riskə baxış' seçildikdə "
                    "istifadəçi yalnız 'Risk cədvəlinə baxış' moduluna keçid edə bilər."
                ),
                "fields": ("riske_baxis", "risk_redakte", "loglara_baxis"),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser or request.user.has_perm('authentication.view_permissions_section'):
            return fieldsets
        return tuple(fs for fs in fieldsets if fs[0] not in ("İcazələr", "Risk Reyestri Modulu İcazələri"))

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
                "riske_baxis",
                "risk_redakte",
                "loglara_baxis",
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