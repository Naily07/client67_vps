
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView


urlpatterns = [
    path('', TokenObtainPairView.as_view(), name='get-token'),
    path('verify', TokenVerifyView.as_view(), name='verify-token'),
    path('refresh', TokenRefreshView.as_view(), name='refresh-token'),
]