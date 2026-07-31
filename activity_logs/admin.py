from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp', 'user_username_snapshot', 'action_type',
        'module_title', 'description', 'ip_address',
    )
    list_filter = ('action_type', 'module_code', 'timestamp')
    search_fields = ('user_username_snapshot', 'description', 'request_path', 'module_title')
    readonly_fields = (
        'user', 'user_username_snapshot', 'action_type', 'module_code', 'module_title',
        'sub_module_title', 'description', 'object_repr', 'changes', 'request_method',
        'request_path', 'status_code', 'ip_address', 'user_agent', 'timestamp',
    )
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False  # loq qeydləri əl ilə yaradılmamalıdır

    def has_change_permission(self, request, obj=None):
        return False  # loq qeydləri dəyişdirilməməlidir (immutability)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser