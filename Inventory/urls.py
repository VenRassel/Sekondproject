from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/password_reset', RedirectView.as_view(pattern_name='forgot_password', permanent=False)),
    path('admin/password_reset/', RedirectView.as_view(pattern_name='forgot_password', permanent=False)),
    path('admin/password_reset/done/', RedirectView.as_view(pattern_name='forgot_password_done', permanent=False)),
    path('password-reset', RedirectView.as_view(pattern_name='forgot_password', permanent=False)),
    path('password-reset/', RedirectView.as_view(pattern_name='forgot_password', permanent=False)),
    path('admin/', admin.site.urls),
    path('', include('Base.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
