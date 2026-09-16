from django.contrib import admin

from .models import BulletinCategory, Circular, NewsPost


@admin.register(BulletinCategory)
class BulletinCategoryAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "icon", "order", "is_active", "documents_count")
    list_editable = ("order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "key", "description")
    prepopulated_fields = {"key": ("label",)}

    def documents_count(self, obj):
        return obj.circulars.count()
    documents_count.short_description = "Sənəd sayı"


@admin.register(Circular)
class CircularAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "number", "document_date", "organization", "is_active")
    list_filter = ("category", "is_active", "organization")
    search_fields = ("title", "number")
    autocomplete_fields = ("organization",)


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "organization", "is_active")
    list_filter = ("is_active", "organization")
    search_fields = ("title", "summary", "body")
    autocomplete_fields = ("organization",)