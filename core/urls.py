from django.urls import path

from core.views import ModuleListView

urlpatterns = [
    path("modules/", ModuleListView.as_view(), name="module-list"),
]
