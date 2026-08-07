from django.contrib import admin

from .models import AttendancePermission


@admin.register(AttendancePermission)
class AttendancePermissionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "date", "start_time", "end_time", "location",
        "department", "organization", "status", "reviewed_by", "reviewed_at",
    )
    list_filter = ("status", "organization", "department", "date")
    search_fields = ("user__username", "user__firstname", "user__lastname", "location")
    autocomplete_fields = ("user", "department", "organization", "reviewed_by")
    readonly_fields = ("created_at", "updated_at")