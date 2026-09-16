from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BirthdaysView,
    BulletinCategoryViewSet,
    BulletinDashboardView,
    BulletinPermissionsView,
    CircularViewSet,
    NewsPostViewSet,
)

app_name = "bulletin"

router = DefaultRouter()
router.register("circulars", CircularViewSet, basename="circular")
router.register("news", NewsPostViewSet, basename="news")
router.register("categories", BulletinCategoryViewSet, basename="bulletin-category")

urlpatterns = [
    path("dashboard/", BulletinDashboardView.as_view(), name="dashboard"),
    path("birthdays/", BirthdaysView.as_view(), name="birthdays"),
    path("permissions/", BulletinPermissionsView.as_view(), name="permissions"),
] + router.urls