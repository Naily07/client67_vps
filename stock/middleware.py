from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from rest_framework_simplejwt.tokens import UntypedToken
from django.contrib.auth import get_user_model
from jwt import decode as jwt_decode
from django.conf import settings


User = get_user_model()


@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope["query_string"].decode())
        token = query.get("token", [None])[0]

        if token:
            try:
                UntypedToken(token)
                decoded = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                scope["user"] = await get_user(decoded["user_id"])
            except Exception:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
