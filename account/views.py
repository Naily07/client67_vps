from django.shortcuts import render
from rest_framework import generics
from .serialisers import CustomUserSerialiser
from django.contrib.auth.models import Group
from .models import CustomUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from api.serializers import MyTokenObtainPairSerializer, TokenSetPassword
from rest_framework import status
from api.mixins import PropriosEditorMixin, ProprioQueryset
from rest_framework.views import APIView
from decouple import config
from django.core.mail import send_mail
from rest_framework import status
from django.shortcuts import redirect
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
# Create your views here.


class PasswordResetRequestView(APIView):
    def post(self, request, *args, **kwargs):
        datas = request.data
        print("HOST", request.get_host())
        try:
            newpass = datas['new_password']
            email = datas['email']
            CustomUser.objects.get(email=email)
            backEndUrl = config("BACKEND_URL")
            token = TokenSetPassword.get_token(email=email, new_pass= newpass)
            activation_link = f"{backEndUrl}/api/account/update-password?token={token}"
            subject = "Valider le nouveau mot de passe"
            text_content = f"""
                Bonjour,

                Vous avez demandé à réinitialiser votre mot de passe. Cliquez sur le lien ci-dessous pour confirmer cette action :

                {activation_link}

                Si vous n'avez pas demandé cette action, veuillez ignorer cet email.

                Cordialement,
                Votre équipe.
            """
            html_message = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; margin: 0; padding: 20px;">
                <div style="max-width: 600px; margin: 20px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); padding: 20px;">
                    <div style="background: #045D5D; color: #fff; text-align: center; padding: 10px 0; border-radius: 8px 8px 0 0;">
                        <h2>Réinitialisation de votre mot de passe</h2>
                    </div>
                    <div style="text-align: center; margin: 20px 0;">
                        <p>Bonjour,</p>
                        <p>Vous avez demandé à réinitialiser votre mot de passe.</p>
                        <p>Cliquez sur le bouton ci-dessous pour confirmer cette action :</p>
                        <a href="{activation_link}" target="_blank" 
                        style="display: inline-block; padding: 10px 20px; font-size: 16px; color: #fff; background: #413864; text-decoration: none; border-radius: 5px; margin-top: 20px;">
                        Changer mon mot de passe
                        </a>
                        <p style="margin-top: 20px;">Si vous n'avez pas demandé cette action, veuillez ignorer cet email.</p>
                    </div>
                    <div style="text-align: center; font-size: 12px; color: #999;">
                        <p>© 2025 digievo.mg</p>
                    </div>
                </div>
            </body>
            </html>
            """
            emailHost = config('EMAIL_HOST_USER', default='email_host_user')
            from_email = emailHost
            message = f"cliquer ici {activation_link}"
            send_mail(subject = subject, message = text_content, from_email = from_email,html_message=html_message, recipient_list = [email])
            return Response({"message": f"Un e-mail d'activation a été envoyé avec succès."}, status=status.HTTP_201_CREATED)
        except CustomUser.DoesNotExist:
            return Response({"message":f"Utilisateur avec l'emaill {email} n'existe pas"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            raise ValidationError({"detail" : str(e)})

import jwt
class UpdatePassword(APIView):
    def get(self, request, *args, **kwargs):
        try:
            # print("ARR", self.args)
            print("KW", request.query_params.get('token'))
            token = request.query_params.get('token')
            secret_key = config('SECRET_KEY')
            datas = jwt.decode(token, secret_key, algorithms='HS256')
            user = CustomUser.objects.get(email=datas['email'])
            user.set_password(datas['new_pass'])
            user.save()
            print("Datas", user.password)
            redirect_url = config('FRONTEND_URL')
            # return Response(f"Password reset check {user.check_password('newP')}")
            return redirect(f"{redirect_url}?message=Email mis à jour")
        except Exception as e:
            raise e

class ListAccount(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerialiser
class CreateListAccount(generics.ListCreateAPIView, PropriosEditorMixin, ProprioQueryset):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerialiser

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError({"email": "Cet email est déjà utilisé."})
        except Exception as e:
            raise ValidationError({"detail": str(e)})
    
    def perform_create(self, serializer):
        account_type = serializer.validated_data.get('account_type')
        if not account_type:
            raise ValidationError({"account_type": "Le type de compte est requis."})

        group_name = f"{account_type}s"
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            raise ValidationError({"account_type": f"Groupe '{group_name}' introuvable."})

        user = serializer.save()
        user.groups.add(group)

from django.contrib.auth import authenticate
class Login(APIView):
    permission_classes = []
    def post(self, request):
        print(request.data)
        try :
            print(request)
            username = request.data.get('username')
            password = request.data.get('password')
        except Exception as e:
            raise e
        
        # user =  CustomUser.objects.filter(username__iexact = username, password__iexact = password).first() 
        user = authenticate(request, username = username, password =  password)
        # print("USER", user)
        try :
            if user is None :
                raise AuthenticationFailed("le compte n'existe pas")
            # print(user)
            access_token, refresh_token = MyTokenObtainPairSerializer.get_token(user)
            response = Response()
            response.data = {
                "access_token": f"{access_token}",
                "refresh_token": f"{refresh_token}"
            }
            
            # response.set_cookie('jwt_refresh', refresh)
            response.status_code = status.HTTP_200_OK
            return response  
        
        except Exception as e:
            raise AuthenticationFailed(f"Login error {e}")
