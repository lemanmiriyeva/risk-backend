from rest_framework.routers import DefaultRouter
from .views import InventoryViewSet

router = DefaultRouter()
router.register('', InventoryViewSet, basename='inventory')

urlpatterns = router.urls