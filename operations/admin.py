from django.contrib import admin

from .models import Operation, OperationApprovalStep


class OperationApprovalStepInline(admin.TabularInline):
    model = OperationApprovalStep
    extra = 0
    readonly_fields = (
        'step_number', 'role_label', 'approver', 'reviewed_by',
        'status', 'comment', 'reviewed_at',
    )
    can_delete = False


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'category_title', 'operation_type', 'action', 'status',
        'user_username_snapshot', 'object_repr', 'created_at',
    )
    list_filter = ('operation_type', 'action', 'status', 'category_code')
    search_fields = ('user_username_snapshot', 'description', 'object_repr', 'category_title')
    date_hierarchy = 'created_at'
    inlines = [OperationApprovalStepInline]
    readonly_fields = [f.name for f in Operation._meta.fields]

    def has_add_permission(self, request):
        # Əməliyyatlar yalnız sistem tərəfindən (siqnallar/servislər vasitəsilə) yaradılır
        return False