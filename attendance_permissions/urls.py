from django.urls import path

from .views import (
    AttendancePermissionListCreateView,
    AttendancePermissionDetailView,
    AttendancePermissionReviewView,
)

app_name = "attendance_permissions"

urlpatterns = [
    path("", AttendancePermissionListCreateView.as_view(), name="list-create"),
    path("<int:id>/", AttendancePermissionDetailView.as_view(), name="detail"),
    path("<int:id>/review/", AttendancePermissionReviewView.as_view(), name="review"),
]