from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponseRedirect
import logging
from django.conf import settings
from django.conf.urls.static import static

logger = logging.getLogger(__name__)

def log_logout_redirect(request):
    logger.info("Redirecting /accounts/logout/ to /logout/")
    return HttpResponseRedirect('/logout/')

urlpatterns = [
    path('django-admin/', admin.site.urls),  # Move Django admin to /django-admin/
    path('', include('navigo.urls')),
    path('accounts/logout/', log_logout_redirect, name='accounts_logout_redirect'),
    path('accounts/profile/', RedirectView.as_view(url='/profile/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)