from django.contrib import admin
from .models import Risk, RiskLog
from . import services


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = ('designation', 'risk_degree', 'risk_level', 'treatment_option', 'created_by', 'updated_by', 'updated_at')
    list_filter = ('risk_level', 'treatment_option')
    search_fields = ('designation', 'legal_basis', 'standard_references')
    readonly_fields = ('risk_degree', 'risk_level', 'created_by', 'updated_by', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.updated_by = request.user
            super().save_model(request, obj, form, change)
            services.log_created(obj, request.user)
        else:
            old_values = {f: getattr(Risk.objects.get(pk=obj.pk), f) for f in services.TRACKED_FIELDS}
            obj.updated_by = request.user
            super().save_model(request, obj, form, change)
            from types import SimpleNamespace
            services.log_updated(SimpleNamespace(**old_values), obj, request.user)

    def delete_model(self, request, obj):
        services.log_deleted(obj, request.user)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            services.log_deleted(obj, request.user)
        super().delete_queryset(request, queryset)


@admin.register(RiskLog)
class RiskLogAdmin(admin.ModelAdmin):
    list_display = (
        'risk_id_ref', 'risk_designation', 'action_type',
        'user_username_snapshot', 'ip_address', 'timestamp'
    )
    list_filter = ('action_type', 'timestamp')
    search_fields = ('risk_designation', 'user_username_snapshot', 'risk_id_ref')
    readonly_fields = (
        'risk', 'risk_id_ref', 'risk_designation', 'user', 'user_username_snapshot',
        'action_type', 'changes', 'risk_snapshot', 'ip_address', 'user_agent', 'timestamp'
    )
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False  # loq qeydləri əl ilə yaradılmamalıdır

    def has_change_permission(self, request, obj=None):
        return False  # loq qeydləri dəyişdirilməməlidir (immutability)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # istəyə görə, silməyə icazə vermək/verməmək