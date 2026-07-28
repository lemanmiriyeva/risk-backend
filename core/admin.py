from django.contrib import admin
from .models import Module, SubModule, Status


class SubModuleInline(admin.TabularInline):
    model = SubModule
    extra = 0
    fields = ("title", "url_endpoint", "permitted_users")
    filter_horizontal = ("permitted_users",)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "url_endpoint",)
    list_filter = ("permitted_users",)
    search_fields = ("title",)
    filter_horizontal = ("permitted_users",)
    inlines = (SubModuleInline,)


@admin.register(SubModule)
class SubModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "url_endpoint",)
    list_filter = ("module", "permitted_users",)
    search_fields = ("title", "module__title",)
    filter_horizontal = ("permitted_users",)


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("title", "code",)
    search_fields = ("title", "code",)