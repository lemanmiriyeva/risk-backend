from django.urls import path, include

urlpatterns = [
    path('authentication/', include('authentication.urls')),
    path('', include('core.urls')),
    path('risk/', include('risk.urls')),
    path('activity-logs/', include('activity_logs.urls')),
    path('inventory/', include('inventory.urls')),
    path('attendance-permissions/', include('attendance_permissions.urls')),
    path('notifications/', include('notifications.urls')),

    path('operations/', include('operations.urls')),

]
