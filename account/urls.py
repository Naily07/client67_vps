
from django.urls import path
from .views import *
urlpatterns = [
    path('register', CreateListAccount.as_view(), name='account-list'),
    path('list', ListAccount.as_view(), name='account-list'),
    path('login', Login.as_view(), name='login'),
    path('reset-password', PasswordResetRequestView.as_view(), name='reset'),
    path('update-password', UpdatePassword.as_view(), name='update'),
    path('update/<int:pk>', UpdateAccount.as_view(), name='update-account'),
    path('<int:pk>', GetAccount.as_view(), name='update-account'),
    path('change-password', ChangePasswordView.as_view(), name='update-account'),
]