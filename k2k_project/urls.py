"""
URL configuration for Project Khet2Kitchen (K2K).
"""
import os
import sys
from pathlib import Path
import django
from django.conf import settings

# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'k2k_project.settings')
if not settings.configured:
    django.setup()

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf.urls.static import static

urlpatterns = [
    # Interactive K2K Dashboard & Command Center UI (Root Web App)
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    
    # Django Admin Interface
    path('admin/', admin.site.urls),
    
    # K2K REST API Endpoints
    path('api/v1/', include('k2k_core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if __name__ == '__main__':
    print("[OK] K2K URL configuration verified successfully.")
    for p in urlpatterns:
        print(f"  -> {p.pattern}")
