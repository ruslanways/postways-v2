"""
ASGI config for postways project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Initialize Django application first to avoid circular imports
django_app = get_asgi_application()

# Import routing after Django is initialized
# noqa: E402 - Import must come after get_asgi_application() to avoid circular imports
import apps.diary.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(apps.diary.routing.websocket_urlpatterns))
        ),
    }
)
