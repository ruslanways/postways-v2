"""postways URL Configuration"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.diary.urls")),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# ------------------------------------------------------------------------------
# Custom error handlers
# ------------------------------------------------------------------------------
handler400 = "apps.diary.views.error_400"
handler403 = "apps.diary.views.error_403"
handler404 = "apps.diary.views.error_404"
# Note: handler500 is handled by UncaughtExceptionMiddleware for logging + API support
