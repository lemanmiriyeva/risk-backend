from django.urls import path

from .views import UserView, UsersView, LogoutView, LoginView, DepartmentListView, DepartmentDetailAPIView, \
    UserDetailView, RequestPasswordResetView, ConfirmPasswordResetView, RoleListView, RequestTwoFAResetView
from rest_framework_simplejwt.views import TokenVerifyView, TokenRefreshView
from .views_2fa import TwoFASetupView, TwoFAVerifyView
from .views import OrgUsersView, OrgUserDetailView, OrganizationListView, OrganizationDetailView, \
    ResetOrgUserPasswordView

urlpatterns = [
    path('token/', LoginView.as_view(), name='token'),
    path('token/verify/', TokenVerifyView.as_view(), name='verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('user/', UserView.as_view(), name='user'),
    path('user/<int:id>/', UserDetailView.as_view(), name='user_detail'),
    path('user/list/', UsersView.as_view(), name='authentication'),
    path('user/logout/', LogoutView.as_view(), name='logout'),
    path('user/request-password-reset/', RequestPasswordResetView.as_view(), name='request-password-reset'),
    path('user/password-reset/', ConfirmPasswordResetView.as_view(), name='password-reset-confirm'),
    path("departments/", DepartmentListView.as_view(), name="department-list"),
    path('departments/<int:id>/', DepartmentDetailAPIView.as_view(), name='department-detail'),
    path('2fa/setup/', TwoFASetupView.as_view(), name='2fa-setup'),
    path('2fa/verify/', TwoFAVerifyView.as_view(), name='2fa-verify'),
    path('2fa/request-reset/', RequestTwoFAResetView.as_view(), name='2fa-request-reset'),
    path('organizations/', OrganizationListView.as_view(), name='organizations-list'),
    path('organizations/<int:id>/', OrganizationDetailView.as_view(), name='organization-detail'),
    path('organization/users/', OrgUsersView.as_view(), name='org-users-list'),
    path('organization/users/<int:id>/', OrgUserDetailView.as_view(), name='org-user-detail'),
    path('organization/users/<int:id>/reset-password/', ResetOrgUserPasswordView.as_view(),
         name='org-user-reset-password'),
    path('roles/', RoleListView.as_view(), name='role-list'),
]