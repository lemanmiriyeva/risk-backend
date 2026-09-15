from django.contrib import admin

from .models import Circular, NewsPost


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