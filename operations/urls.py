from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import OperationReviewView, OperationViewSet

app_name = "operations"

router = DefaultRouter()
router.register('', OperationViewSet, basename='operation')

urlpatterns = [
    path('<int:id>/review/', OperationReviewView.as_view(), name='review'),
] + router.urls