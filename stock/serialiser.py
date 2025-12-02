from rest_framework import serializers

from .models import *
from django.utils import timezone
from django.db import IntegrityError, Error
from rest_framework.response import Response
from rest_framework import status
from psycopg2.errors import UniqueViolation
from account.serialisers import CustomUserSerialiser
from django.db import transaction


# class FournisseurSerialiser(serializers.ModelSerializer):
#     nom = serializers.CharField(max_length=20, required = True)
#     adress = serializers.CharField(max_length=25)
#     contact = serializers.CharField(max_length=20)

#     class Meta:
#         model = Fournisseur
#         fields = ['nom', 'adress', 'contact']

class DetailSerialiser(serializers.ModelSerializer):
    designation = serializers.CharField(max_length=50, min_length=10, trim_whitespace=True, required = True)
    famille = serializers.CharField(max_length=25, min_length=10, trim_whitespace=True)
    classe = serializers.CharField(max_length=50, min_length=10, trim_whitespace=True)
    type_gros = serializers.CharField(max_length=25, min_length=10, trim_whitespace=True)

    class Meta():
        model = Detail
        fields = ['id', 'designation', 'famille', 'classe', 'type_gros']

    def create(self, validated_data):
        return super().create(validated_data)

from django.core.validators import MinValueValidator
class ProductSerialiser(serializers.ModelSerializer):
    prix_gros = serializers.DecimalField(max_digits=10, decimal_places=0)
    qte_gros = serializers.IntegerField(validators = [MinValueValidator(0)])
    date_peremption = serializers.DateField()
    date_ajout = serializers.DateTimeField(read_only = True) 
    
    detail = serializers.DictField(write_only = True)
    detail_product = serializers.SerializerMethodField()
    
    marque_product = serializers.SerializerMethodField()
    marque = serializers.CharField(write_only =True, required = False)
    
    # fournisseur_product = serializers.SerializerMethodField()
    # fournisseur = serializers.DictField(write_only = True)
    
    class Meta():
        model = Product
        fields = [
                'pk', 'prix_gros','qte_gros',
                'detail_product', 'detail',"marque_product", 'marque', 
                'date_peremption', 'date_ajout', "prix_gros_init"
                  ]

    
    def get_detail_product(self, obj):
        detail = obj.detail
        detailObj = Detail.objects.filter(designation__iexact = detail.designation).first()
        return DetailSerialiser(detailObj).data
    
    def get_marque_product(self, obj):
        if not obj.marque:
            return ""
        marque = obj.marque
        return marque.nom
    
    # def get_fournisseur_product(self, obj):
    #     fournisseur = obj.fournisseur
    #     return fournisseur.nom
    
    def create(self, validated_data):
        try:
            with transaction.atomic():
                print(validated_data)
                request = self.context['request']
                detail_data = validated_data.pop("detail")
                marque = validated_data.pop('marque', None)
                # fournisseur = validated_data.pop('fournisseur')
                print(validated_data)
                instance, createdD = Detail.objects.get_or_create(
                    designation=detail_data['designation'], 
                    famille=detail_data['famille'], 
                    classe=detail_data['classe'],
                    type_gros=detail_data['type_gros'],
                )
                marqueInstance = None
                if marque:
                    marqueInstance, createdM = Marque.objects.get_or_create(nom = marque)

                print(instance)
                product = Product.objects.create(detail = instance, marque = marqueInstance, **validated_data)
                user = request.user
                print("utilisateur", user)
                AjoutStock.objects.create(
                    # qte_unit_transaction=product.qte_unit,
                    qte_gros_transaction=product.qte_gros,
                    # qte_detail_transaction=product.qte_detail,
                    type_transaction="Ajout",
                    prix_gros = product.prix_gros,
                    # prix_unit = product.prix_unit,
                    # prix_detail = product.prix_detail,
                    prix_total = (int(product.prix_gros) * int(product.qte_gros)), 
                    product=product,  
                    gestionnaire=user
                )
                
                return product
        except UniqueViolation as e:
            raise serializers.ValidationError({"message": "Un produit avec cette combinaison de fournisseur, marque et détail existe déjà."})
        except IntegrityError as e:
            print("eXX", e)
            raise serializers.ValidationError({"message": f"Erreur d'intégrité des données."})
        except Exception as e:
            raise serializers.ValidationError({"message": f"Une erreur inattendue s'est produite: {str(e)}"})

class AjoutStockSerialiser(serializers.ModelSerializer):
    qte_gros_transaction = serializers.IntegerField()
    type_transaction = serializers.CharField(max_length=25)
    prix_gros = serializers.DecimalField(max_digits=10, decimal_places=0)
    # prix_unit = serializers.DecimalField(max_digits=10, decimal_places=0)
    # prix_detail = serializers.DecimalField(max_digits=10, decimal_places=0)
    prix_total = serializers.DecimalField(max_digits=10, decimal_places=0)
    date = serializers.DateTimeField(read_only = True)

    class Meta():
        model = AjoutStock
        fields = '__all__'  
        
class VenteProductSerializer(serializers.ModelSerializer):
    # qte_detail_transaction = serializers.IntegerField(min_value = 0)
    qte_gros_transaction = serializers.IntegerField(min_value = 0)
    type_transaction = serializers.ChoiceField([
        ('Vente' , 'Vente'),
        ('Ajout', 'Ajout'),
        ('Maj', 'Maj')
    ])
    product_id = serializers.IntegerField(min_value = 0, write_only = True)
    prix_total = serializers.DecimalField(max_digits=10, decimal_places=0)
    product = serializers.SerializerMethodField(read_only = True)
    marque = serializers.SerializerMethodField(read_only = True)
    # vendeur = serializers.SerializerMethodField(read_only = True)

    class Meta():
        model = VenteProduct
        fields = "__all__"
            

    def get_product(self, obj):
        venteStock = obj
        produit : Product = venteStock.product
        # print(produit.detail)
        return ProductSerialiser(produit).data
    
    def get_marque(self, obj):
        venteStock = obj
        produit : Product = venteStock.product
        if produit.marque:
            return produit.marque.nom
        return ""
    

class ReglementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reglement
        fields = ['id', 'date_paiement', 'montant', 'moyen_paiement']

class FactureSerialiser(serializers.ModelSerializer):
    prix_total = serializers.DecimalField(max_digits=10, decimal_places=0)
    prix_restant = serializers.DecimalField(max_digits=10, decimal_places=0)
    ventes = serializers.SerializerMethodField(read_only = True)
    client = serializers.CharField()
    date = serializers.SerializerMethodField(read_only = True)
    owner = serializers.SerializerMethodField(read_only = True)
    reglements = serializers.SerializerMethodField(read_only = True)
    class Meta:
        model = Facture
        fields = ['pk', 'prix_total', 'prix_restant', 'ventes', 'client', 'date', 'owner', 'reglements']

    def get_ventes(self, obj):
        facture = obj
        vente = facture.venteproduct_related.all()
        return VenteProductSerializer(vente, many = True).data 
    
    def get_owner(self, obj):
        owner = CustomUserSerialiser(obj.owner).data
        print(owner)
        return owner['username']
    
    def get_date(self, obj):
        # print("Formate", obj.formated_date)
        return obj.formated_date
    
    def get_reglements(self, obj):
        facture = obj
        reglements = facture.reglements.all()
        return ReglementSerializer(reglements, many=True).data
    
class FilAttenteSerialiser(serializers.ModelSerializer):
    ventes = serializers.SerializerMethodField(read_only = True)
    client = serializers.CharField()
    date = serializers.SerializerMethodField(read_only = True)
    owner = serializers.SerializerMethodField(read_only = True)
    class Meta:
        model = FilAttenteProduct
        fields = "__all__"

    def get_ventes(self, obj):
        fil = obj
        ventes = fil.venteproduct_related.all()
        # print("VenteProduct", ventes)
        # for v in ventes:
        #     print("ID Vente:", v.id)
        
        return VenteProductSerializer(ventes, many = True).data 
    
    def get_owner(self, obj):
        owner = CustomUserSerialiser(obj.owner).data
        # print(owner)
        return owner['username']
    
    def get_date(self, obj):
        # print("Formate", obj.formated_date)
        return obj.formated_date  
    
class TrosaSerialiser(serializers.ModelSerializer):
    owner = serializers.CharField(required = True)
    date = serializers.DateField(read_only = True)
    montant = serializers.DecimalField(max_digits=10, decimal_places=0, read_only = True)
    montant_restant = serializers.DecimalField(max_digits=10, decimal_places=0)
    contact = serializers.CharField(allow_blank = True)
    adress = serializers.CharField(allow_blank = True)
    reglements = serializers.SerializerMethodField(read_only = True)

    class Meta:
        model = Trosa
        fields = ["pk", 'owner', 'date', 'montant', 'montant_restant', 'adress', 'contact', "reglements"]
    
    def create(self, validated_data):
        trosa = Trosa.objects.create(montant = validated_data.get('montant_restant'), **validated_data)
        return trosa
    
    def get_reglements(self, obj):
        facture = obj
        reglements = facture.reglements.all()
        return ReglementSerializer(reglements, many=True).data