from django.contrib import admin
from .models import Module


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "path", "permission", "order", "is_active")
    list_editable = ("order", "is_active")
    ordering = ("order",)
    search_fields = ("title", "permission")