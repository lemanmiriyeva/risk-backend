from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import RiskViewSet, RiskLogViewSet, ExportLogView

router = DefaultRouter()
router.register('logs', RiskLogViewSet, basename='risk-log')  
router.register('', RiskViewSet, basename='risk')

urlpatterns = [
    path('export-log/', ExportLogView.as_view(), name='export-log'),
] + router.urls