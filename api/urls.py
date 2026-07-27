from django.urls import path, include


urlpatterns = [
    path('authentication/', include('authentication.urls')),
    path('', include('core.urls')),
    path('risk/', include('risk.urls')),

]
