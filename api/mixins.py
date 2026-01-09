
from .permissions import *
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser

class GestionnaireEditorMixin():
    permission_classes = [IsAuthenticated, IsGestionnaire]

class VendeurEditorMixin():
    permission_classes = [IsAuthenticated, IsVendeur]

class PropriosEditorMixin:
    permission_classes = [IsAuthenticated, IsProprio]


from datetime import timedelta
from django.utils import timezone
from rest_framework.generics import GenericAPIView
from stock.models import Product, Facture

class ProductQsField(GenericAPIView):
    # qs_expired = "expired"
    qs_field = "etat"
    def get_queryset(self):
        qs = super().get_queryset()
        try:
            etat = self.kwargs[self.qs_field]
            if etat == "expired":
                print("exp")
                today = timezone.now().date()
                three_months_from_now = today + timedelta(days=90)
                print(three_months_from_now)
                qs = Product.objects.filter(date_peremption__lte=three_months_from_now, date_peremption__gte = timezone.now())
                return qs
            elif etat == "rupture" :
                print("RUPTEE")
                qs = Product.objects.filter(qte_gros__lte = 50)
                return qs
        except Exception as e:
            print(e)
            return qs   

from django.utils.timezone import now, timedelta,  make_aware, datetime, get_current_timezone

class userFactureQs(GenericAPIView):
    
    def get_queryset(self):
        qs =  super().get_queryset()
        qs = qs.order_by("-date")
        user = self.request.user
        userType = user.groups.filter(name = 'vendeurs').exists()
        params = self.request.query_params

        # if userType:
        #     data = {"owner" : user}
        #     qs = qs.filter(**data)
        
        filtreDict = {}
        today = datetime.combine(now().date(), datetime.min.time())
        next_day = today + timedelta(days=1)

        tz = get_current_timezone()
        today = make_aware(today, timezone=tz)
        next_day = make_aware(next_day, timezone=tz)
        start_week = today - timedelta(days=today.weekday())  # lundi de la semaine
        start_month = today.replace(day=1)

        if 'today' in params:
            thisDay = params['today'].lower()
            if thisDay == 'true':
                qs = qs.filter(date__gte=today, date__lt=next_day)

        if 'week' in params:
            week = params['week'].lower()
            if week == 'true':
                qs = qs.filter(date__gte=start_week)

        if 'month' in params:
            month = params['month'].lower()
            if month == 'true':
                qs = qs.filter(date__gte=start_month)

        if 'date' in params:
            try:
                day = datetime.strptime(params['date'], '%Y-%m-%d')
                next_day = day + timedelta(days=1)
                qs = qs.filter(date__gte=day, date__lt=next_day)
            except ValueError:
                raise ValidationError("Format de date invalide. Utilisez AAAA-MM-JJ")
        
        if 'client' in params:
            qs = qs.filter(client__icontains = params['client'])

        if 'impayee' in params and 'payee' in params:
            raise ValidationError("Vous ne pouvez pas filtrer à la fois sur payée et impayée.")
        
        if 'impayee' in params:
            impayer_str = params['impayee'].lower()
            if impayer_str == 'true':
                filtreDict['prix_restant__gt'] = 0

        if 'payee' in params:
            payee_str = params['payee'].lower()
            if payee_str == 'true':
                # Factures payées => prix_restant = 0
                filtreDict['prix_restant'] = 0
        qs = qs.filter(**filtreDict)
        return qs

class ProprioQueryset(GenericAPIView):

    def get_queryset(self):
        qs =  super().get_queryset()
        user = self.request.user
        userType = user.groups.filter(name = 'proprios').exists()
        if userType :
            print("TYPE", userType)
            data = {"is_superuser" : False}
            print(data)
            return qs.filter(**data)
        return qs