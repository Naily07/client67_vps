"""
WSGI config for pharma project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

#Decommenter en server live
# import sys

# # Forcer l'encodage de la sortie standard et de l'erreur standard en UTF-8
# sys.stdout = sys.stdout.detach()
# sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8')

# sys.stderr = sys.stderr.detach()
# sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8')
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharma.settings')

application = get_wsgi_application()
