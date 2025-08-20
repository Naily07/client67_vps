from rest_framework.permissions import BasePermission

class IsGestionnaire(BasePermission):

    def has_permission(self, request, view):
        user = request.user
        print(user.groups.all())
        if not (user.groups.filter(name='gestionnaires').exists() | user.is_superuser):
            print("Ok gestionnaire")
            return False
        else:
            return True
    
    perms_map = {
        'GET': ['%(app_label)s.add_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

class IsVendeur(BasePermission):

    def has_permission(self, request, view):
        user = request.user
        if not (user.groups.filter(name='vendeurs').exists() | user.is_superuser):
            return False
        else:
            return super().has_permission(request, view)
    
    perms_map = {
        'GET': ['%(app_label)s.add_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': [],
    }

class IsProprio(BasePermission):
    def has_permission(self, request, view):
        print("Proppp")
        user = request.user
        if not (user.groups.filter(name='proprios').exists() | user.is_superuser):
            return False
        else:
            return super().has_permission(request, view)
    
    perms_map = {
        'GET': ['%(app_label)s.add_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': [],
    }
