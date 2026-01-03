"""
ASGI config for pharma project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# Définir la variable d'environnement pour les paramètres Django AVANT toute autre importation Django.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharma.settings")

# Initialiser l'application ASGI de Django pour s'assurer que le registre des applications
# est peuplé avant d'importer du code qui pourrait utiliser des modèles ORM.
django_asgi_app = get_asgi_application()

# Maintenant, nous pouvons importer en toute sécurité les composants de Channels et de votre application.
from channels.routing import ProtocolTypeRouter, URLRouter
from stock.routing import websocket_urlpatterns
from stock.middleware import JWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # HTTP normal
    "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
})
