from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ModulesRetrieveView,
    CheckModuleAccessView,
    CheckSubModuleAccessView,
    StatusViewSet,
)
from .views import OrgModuleAccessView

app_name = "core"

router = DefaultRouter()
router.register(r"statuses", StatusViewSet, basename="status")

urlpatterns = [
    path("modules/", ModulesRetrieveView.as_view(), name="modules-list"),
    path("modules/check-access/", CheckModuleAccessView.as_view(), name="module-check-access"),
    path("modules/check-sub-access/", CheckSubModuleAccessView.as_view(), name="submodule-check-access"),
    path("organization/module-access/", OrgModuleAccessView.as_view(), name="organization-module-access"),
] + router.urls