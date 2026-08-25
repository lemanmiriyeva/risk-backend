from django.urls import path

from .views import (
    AttendancePermissionListCreateView,
    AttendancePermissionDetailView,
    AttendancePermissionReviewView,
    AttendancePermissionConfigView,
    AttendancePermissionDepartmentConfigView,
    AttendancePermissionConfigUsersView,
)

app_name = "attendance_permissions"

urlpatterns = [
    path(
        "",
        AttendancePermissionListCreateView.as_view(),
        name="list-create",
    ),

    path(
        "<int:id>/",
        AttendancePermissionDetailView.as_view(),
        name="detail",
    ),

    path(
        "<int:id>/review/",
        AttendancePermissionReviewView.as_view(),
        name="review",
    ),

    path(
        "config/",
        AttendancePermissionConfigView.as_view(),
        name="config",
    ),

    path(
        "config/users/",
        AttendancePermissionConfigUsersView.as_view(),
        name="config-users",
    ),

    path(
        "config/departments/<int:department_id>/",
        AttendancePermissionDepartmentConfigView.as_view(),
        name="department-config",
    ),
]
