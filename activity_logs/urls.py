from rest_framework.routers import DefaultRouter
from .views import ActivityLogViewSet

router = DefaultRouter()
router.register('', ActivityLogViewSet, basename='activity-log')

urlpatterns = router.urls