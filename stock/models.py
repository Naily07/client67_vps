from typing import Iterable
from django.db import models
from django.utils.timezone import localtime
import pytz
from django.db import transaction
from account.models import CustomUser
# Create your models here.
        

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
class Reglement(models.Model):
    # Référence générique
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    cible = GenericForeignKey('content_type', 'object_id')  # Peut pointer vers une Facture ou une Trosa
    
    remarque = models.TextField(blank=True, null=True)
    date_paiement = models.DateTimeField(auto_now_add=True)
    montant = models.DecimalField(max_digits=10, decimal_places=0)
    moyen_paiement = models.CharField(max_length=50, blank=True, default="Espèces")
    type_r = models.CharField(max_length=50, blank=True, default="paiement")# note = models.TextField(blank=True, null=True)python

    def __str__(self):
        return f"Règlement de {self.montant} pour {self.cible}"
    
    @property
    def formated_date(self):
        timezone = pytz.timezone('Etc/GMT-3')
        date =  localtime(self.date_paiement, timezone) # localtime change the timezone ou la fuseau horaire avec pytz
        formated = date.strftime("%d/%m/%Y, %H:%M") # Formate la date en string et format
        return formated

class Customer(models.Model):
    nom = models.TextField(max_length=50)
    avance = models.DecimalField(max_digits=10, decimal_places=0, default=0)  
    reglements = GenericRelation(Reglement)  
    trosa = models.DecimalField(max_digits=10, decimal_places=0, default=0)  

class Trosa(models.Model):
    owner = models.CharField(max_length=25)
    date = models.DateField(auto_now_add = True)
    adress = models.TextField(blank=True)
    contact = models.CharField(max_length=20, blank=True)
    montant = models.DecimalField(max_digits=10, decimal_places=0)
    montant_restant = models.DecimalField(max_digits=10, decimal_places=0)
    reglements = GenericRelation(Reglement)

class Facture(models.Model):
    date = models.DateTimeField(auto_now_add=True, null = True)
    prix_total = models.DecimalField(max_digits=10, decimal_places=0)
    prix_restant = models.DecimalField(max_digits=10, decimal_places=0)
    client = models.CharField(max_length=20, default="", blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, related_name="%(class)s_related", null=True)    
    num = models.CharField(max_length=6, unique=True, blank=True)
    owner = models.ForeignKey(CustomUser, default=1, on_delete=models.CASCADE, related_name="%(class)s_related")
    reglements = GenericRelation(Reglement)

    def __str__(self) -> str:
        return str(self.id)
    
    def save(self, *args, **kwargs):
        if not self.pk:  # Si l'objet n'a pas encore été enregistré (création)
            self.num = self.generate_num_unique()
        super(Facture, self).save(*args, **kwargs)
        
    @property
    def formated_date(self):
        timezone = pytz.timezone('Etc/GMT-3')
        date =  localtime(self.date, timezone) # localtime change the timezone ou la fuseau horaire avec pytz
        formated = date.strftime("%d/%m/%Y, %H:%M") # Formate la date en string et format
        return formated

    def generate_num_unique(self):
        with transaction.atomic():
            # Verrouille la dernière facture créée pour éviter les courses (best-effort)
            last = Facture.objects.select_for_update().order_by('-id').first()
            if last and last.num and last.num.isdigit():
                next_int = int(last.num) + 1
            else:
                next_int = 1
            return f"{next_int:06d}"

class Marque(models.Model):
    nom = models.CharField(max_length=50, blank=True)
    provenance = models.CharField(max_length=50)

    def __str__(self) -> str:
        if not self.nom:
            return ""
        return self.nom
class Detail(models.Model):
    designation = models.CharField(max_length=255)
    famille = models.CharField(max_length=24)
    classe = models.CharField(max_length=24)
    type_gros = models.CharField(max_length=25)

    def __str__(self) -> str:
        return f"{self.designation}"

from django.db.models.constraints import UniqueConstraint
class Product(models.Model):
    prix_gros = models.DecimalField(max_digits=10, decimal_places=0)
    prix_gros_init = models.DecimalField(max_digits=10, decimal_places=0, default=0, blank = True)
    qte_gros = models.IntegerField(default=0, null=True)
    date_peremption = models.DateField(blank=True, default=None)
    date_ajout = models.DateTimeField(auto_now_add=True) 
    detail = models.ForeignKey(Detail, on_delete=models.CASCADE, default=None, related_name="%(class)s_related")
    marque = models.ForeignKey(Marque, on_delete=models.CASCADE, related_name="%(class)s_related", null=True) 
        
    def __str__(self) -> str:
        return f"{self.detail.designation} + {self.qte_gros}"

class Transaction(models.Model):
    TYPE_CHOICES = [
        ("ajout", "Ajout de stock"),
        ("maj", "Mise à jour manuelle"),
        ("vente", "Vente"),
    ]
    qte_avant = models.IntegerField(default=0, null=True, blank=True)
    qte_apres = models.IntegerField(default=0, null=True, blank=True)
    qte_gros_transaction = models.IntegerField(default=0, null=True)
    type_transaction = models.TextField(max_length=25)
    prix_total = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    date = models.DateTimeField(auto_now=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="%(class)s_related")

    def __str__(self) -> str:
        return self.type_transaction

    class Meta():
        abstract = True
        
class AjoutStock(Transaction):
    # Vue que ray iany gestionnares ts mila nasina ForegnKey AjoutStock
    prix_gros = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    gestionnaire = models.ForeignKey(CustomUser, default=1, on_delete=models.CASCADE, related_name="%(class)s_related")

class FilAttenteProduct(models.Model):
    date = models.DateTimeField(auto_now_add=True, null = True)
    prix_total = models.DecimalField(max_digits=10, decimal_places=0)
    prix_restant = models.DecimalField(max_digits=10, decimal_places=0)
    client = models.CharField(max_length=20, default="", blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, related_name="%(class)s_related", null=True)    
    owner = models.ForeignKey(CustomUser, default=1, on_delete=models.CASCADE, related_name="%(class)s_related")

    def __str__(self) -> str:
        return str(self.id)
    
    @property
    def formated_date(self):
        timezone = pytz.timezone('Etc/GMT-3')
        date =  localtime(self.date, timezone) # localtime change the timezone ou la fuseau horaire avec pytz
        formated = date.strftime("%d/%m/%Y, %H:%M") # Formate la date en string et format
        return formated
    
    @transaction.atomic
    def finaliser(self, id):
        if(id):
            filAttente = FilAttenteProduct.objects.get(id=id)
            allVenteProduct = filAttente.venteproduct_related.all()
            fil_attente_ct = ContentType.objects.get_for_model(FilAttenteProduct)
            regelements = Reglement.objects.filter(object_id = id, content_type=fil_attente_ct,)

            facture = Facture(
                prix_total = filAttente.prix_total,
                prix_restant = filAttente.prix_restant,
                client = filAttente.client,
                owner = filAttente.owner
            )
            facture.save()
            for reglement in regelements:
                Reglement.objects.create(
                    content_type=ContentType.objects.get_for_model(facture),
                    object_id=facture.id,
                    montant=reglement.montant
                )
                reglement.delete()
            for vente in allVenteProduct:
                vente.fil_attente = None
                vente.facture = facture
                vente.type_transaction = "vente"
                vente.save()
            filAttente.delete()
            return allVenteProduct
        else:
            raise ValueError("Fil d'attente inexistant")

class VenteProduct(Transaction):
    prix_vente = models.DecimalField(max_digits=10, decimal_places=0, blank=True, default=0)
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="%(class)s_related", null=True)
    fil_attente = models.ForeignKey(FilAttenteProduct, on_delete=models.SET_NULL, related_name="%(class)s_related", null=True)
    
    def save(self, *args, **kwargs):
        if not self.prix_vente and self.product:
            self.prix_vente = self.product.prix_gros
        return super().save(*args, **kwargs)