from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BirthdaysView, BulletinDashboardView, CircularViewSet, NewsPostViewSet

app_name = "bulletin"

router = DefaultRouter()
router.register("circulars", CircularViewSet, basename="circular")
router.register("news", NewsPostViewSet, basename="news")

urlpatterns = [
    path("dashboard/", BulletinDashboardView.as_view(), name="dashboard"),
    path("birthdays/", BirthdaysView.as_view(), name="birthdays"),
] + router.urls