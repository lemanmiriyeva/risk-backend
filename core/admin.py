from django import forms
from django.contrib import admin
from .models import Module, SubModule, Status


class _EligibleUsersFormMixin(forms.ModelForm):
    """
    permitted_organizations dolu olduqda, permitted_users seçimini (admin formunda)
    yalnız o qurum(lar)ın işçiləri ilə məhdudlaşdırır və düzgün (anlaşılan) xəta göstərir.
    Real qorunma core/signals.py-dakı m2m_changed handler-idir; bu, sadəcə admin UX-i yaxşılaşdırır.
    """
    def clean(self):
        cleaned = super().clean()
        orgs = cleaned.get("permitted_organizations")
        users = cleaned.get("permitted_users")
        if orgs is not None and users is not None and orgs.exists():
            org_ids = set(orgs.values_list("id", flat=True))
            ineligible = [u for u in users if u.organization_id not in org_ids]
            if ineligible:
                names = ", ".join(u.username for u in ineligible)
                raise forms.ValidationError(
                    f"Bu istifadəçi(lər) seçilmiş qurumlara aid deyil: {names}. "
                    f"Əvvəlcə 'Əlaqəli qurumlar' siyahısına onların qurumunu əlavə edin."
                )
        return cleaned


class ModuleAdminForm(_EligibleUsersFormMixin):
    class Meta:
        model = Module
        fields = "__all__"


class SubModuleAdminForm(_EligibleUsersFormMixin):
    class Meta:
        model = SubModule
        fields = "__all__"


class SubModuleInline(admin.TabularInline):
    model = SubModule
    extra = 0
    fields = ("title", "url_endpoint", "permitted_organizations", "permitted_users")
    filter_horizontal = ("permitted_organizations", "permitted_users")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    form = ModuleAdminForm
    list_display = ("title", "url_endpoint", "permitted_organizations_display")
    list_filter = ("permitted_organizations", "permitted_users")
    search_fields = ("title",)
    filter_horizontal = ("permitted_organizations", "permitted_users")
    inlines = (SubModuleInline,)

    @admin.display(description="Əlaqəli qurumlar")
    def permitted_organizations_display(self, obj):
        return ", ".join(obj.permitted_organizations.values_list("title", flat=True)) or "—"


@admin.register(SubModule)
class SubModuleAdmin(admin.ModelAdmin):
    form = SubModuleAdminForm
    list_display = ("title", "module", "url_endpoint",)
    list_filter = ("module", "permitted_organizations", "permitted_users")
    search_fields = ("title", "module__title",)
    filter_horizontal = ("permitted_organizations", "permitted_users")


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("title", "code",)
    search_fields = ("title", "code",)