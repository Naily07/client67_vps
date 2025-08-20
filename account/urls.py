
from django.urls import path
from .views import *
urlpatterns = [
    path('register', CreateListAccount.as_view(), name='account-list'),
    path('list', ListAccount.as_view(), name='account-list'),
    path('login', Login.as_view(), name='login'),
    path('reset-password', PasswordResetRequestView.as_view(), name='reset'),
    path('update-password', UpdatePassword.as_view(), name='update'),
]