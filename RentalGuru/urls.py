from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static

from notification.views import firebase_messaging_sw

urlpatterns = [
    path('jet/', include('jet.urls', 'jet')),
    path('admin/', admin.site.urls),
    path('app/', include('app.urls')),
    path('vehicle/', include('vehicle.urls')),
    path('chat/', include('chat.urls')),
    path('notification/', include('notification.urls')),
    path('franchise/', include('franchise.urls')),
    path('manager/', include('manager.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('influencer/', include('influencer.urls')),
    path('journal/', include('journal.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('', SpectacularSwaggerView.as_view(url_name='schema')),
    path('firebase-messaging-sw.js', firebase_messaging_sw, name='firebase_messaging_sw'),
    path('payment/', include('payment.urls')),
    path('complaint/', include('complaint.urls')),
    path('feedback/', include('feedback.urls')),
    path('report/', include('report.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
