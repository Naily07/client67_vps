from rest_framework.authentication import BasicAuthentication

class CsrfExemptBasicAuthentication(BasicAuthentication):
    def enforce_csrf(self, request):
        return