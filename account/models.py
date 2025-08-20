from typing import Any
from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import UserManager, AbstractUser, PermissionsMixin

class CustomUserManager(UserManager):
    def create_user(self, username: str, email , password, **extra_fields):
        if not email:
            raise ValueError("You have enter an invalide email")
        email = self.normalize_email(email)
        user = self.model(email=email, username = username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        user.save()
        return user
    
    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)
    
    def create_superuser(self, username: str, email: str | None, password: str | None, **extra_fields: Any):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(username, email, password, **extra_fields)


from django.utils import timezone 
class CustomUser(AbstractUser, PermissionsMixin):
    # first_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(null=True, default=None, unique=True)
    is_active = models.BooleanField(default = False)
    is_staff = models.BooleanField(default = False)
    is_superuser = models.BooleanField(default = False)
    username = models.CharField(max_length = 255, unique = True)

    date_joined = models.DateTimeField(default = timezone.datetime.now)
    last_login = models.DateTimeField(null = True, blank = True)

    account_type = models.CharField(max_length=25, default=None, null = True)

    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'

    REQUIRED_FIELDS = ['email']

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def get_username(self) -> str:
        return self.username
    
    def __str__(self) -> str:
        return self.username