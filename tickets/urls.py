from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, TicketMetaView, TicketUsersView, TicketViewSet

app_name = "tickets"

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='ticket-category')
router.register('', TicketViewSet, basename='ticket')

urlpatterns = [
    path('meta/', TicketMetaView.as_view(), name='meta'),
    path('users/', TicketUsersView.as_view(), name='users'),
] + router.urls
