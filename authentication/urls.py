from django.urls import path

from .views import UserView, UsersView, LogoutView, LoginView, DepartmentListView, DepartmentDetailAPIView, \
    UserDetailView
from rest_framework_simplejwt.views import TokenVerifyView, TokenRefreshView
from .views_2fa import TwoFASetupView, TwoFAVerifyView

urlpatterns = [
    path('token/', LoginView.as_view(), name='token'),
    path('token/verify/', TokenVerifyView.as_view(), name='verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('user/', UserView.as_view(), name='user'),
    path('user/<int:id>/', UserDetailView.as_view(), name='user_detail'),
    path('user/list/', UsersView.as_view(), name='authentication'),
    path('user/logout/', LogoutView.as_view(), name='logout'),
    path("departments/", DepartmentListView.as_view(), name="department-list"),
    path('departments/<int:id>/', DepartmentDetailAPIView.as_view(), name='department-detail'),
    path('2fa/setup/', TwoFASetupView.as_view(), name='2fa-setup'),
    path('2fa/verify/', TwoFAVerifyView.as_view(), name='2fa-verify'),
]
