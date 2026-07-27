from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.staticfiles.urls import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
import logging
from django.urls import path


logger = logging.getLogger('colored')

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path('api/', include('api.urls')),
]

urlpatterns += staticfiles_urlpatterns()
# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'Müdafiə Sənayesi Nazirliyi'
admin.site.site_title = 'Risk Reyestr Sistemi'
admin.site.index_title = "Risk Reyestr Sistemi"
