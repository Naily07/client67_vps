
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

# Create your views here.
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        # print(user.groups.all().first())
        token['account_type'] = user.groups.all().first().name
        access_token = token.access_token
        refresh_token = token
        print(access_token)
        return access_token, refresh_token

import datetime 
from decouple import config
import jwt
class TokenSetPassword:
    @classmethod
    def get_token(cls, email, new_pass):
        secret_key = config('SECRET_KEY')
        # Définir les données à inclure dans le token
        payload = {
            'email': email,
            'new_pass': new_pass,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)  # Expiration du token
        }
        # Générer le token JWT
        token = jwt.encode(payload, secret_key, algorithm='HS256')
        
        print(token)  # Pour déboguer et afficher le token généré
        
        return token