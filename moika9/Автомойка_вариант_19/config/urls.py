from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve # Импортируем встроенный обработчик файлов
import os

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Этот маршрут для статики ДОЛЖЕН стоять выше, чем include("center.urls")
    path("static/<path:path>", serve, {"document_root": os.path.join(settings.BASE_DIR, "static")}),
    
    # Главное приложение
    path("", include("garage.urls")),
]

# Для медиа-файлов оставляем внизу
if settings.DEBUG:
    urlpatterns += [
        path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
