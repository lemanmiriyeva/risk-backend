from django.contrib import admin

from .models import (
    Ticket, TicketActivity, TicketAttachment, TicketCategory, TicketComment, TicketDepartment,
)


class TicketDepartmentInline(admin.TabularInline):
    model = TicketDepartment
    extra = 0


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'title', 'status', 'priority', 'requester', 'assignee', 'due_at', 'created_at')
    list_filter = ('status', 'priority', 'ticket_type', 'category')
    search_fields = ('title', 'description', 'requester__username')
    date_hierarchy = 'created_at'
    inlines = [TicketDepartmentInline, TicketCommentInline]
    raw_id_fields = ('requester', 'assignee', 'requester_department', 'organization')


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'code', 'default_department', 'default_priority', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    prepopulated_fields = {'code': ('title',)}


admin.site.register(TicketAttachment)
admin.site.register(TicketActivity)
