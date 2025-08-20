
from rest_framework import serializers
from .models import CustomUser
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomUserSerialiser(serializers.ModelSerializer):
    username = serializers.CharField(max_length = 25)
    first_name = serializers.CharField(max_length = 25)
    password = serializers.CharField(write_only = True)
    email = serializers.EmailField()
    account_type = serializers.ChoiceField(
        [
            ("vendeur", "vendeur"),
            ("proprio", "proprio"),
            ("gestionnaire", "gestionnaire")
        ],
        allow_blank = True,
        required=False
    )

    class Meta():
        model = CustomUser
        fields = ['first_name', 'username', 'password',  "email", 'account_type']
    
    def create(self, validated_data):
        email = ''
        user = CustomUser() 
        if validated_data.get('email'):
            email = validated_data['email']
            user.email = email
        password = validated_data['password']
        user.account_type = validated_data['account_type']
        user.username = validated_data['username']
        user.first_name = validated_data['first_name']
        user.is_active = True
        user.set_password(password)
        user.save()
        return user