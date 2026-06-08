from django.shortcuts import render
from rest_framework import generics
from rest_framework.views import APIView
#Test deploy 
from api.paginations import StandardResultPageination
from api.mixins import GestionnaireEditorMixin, VendeurEditorMixin
from api.mixins import ProductQsField
from .models import *
from .serialiser import *
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from api.permissions import IsGestionnaire
from rest_framework.permissions import IsAuthenticated
from api.mixins import userFactureQs
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from rest_framework.pagination import PageNumberPagination
from django.db.models import Prefetch
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from decimal import Decimal, InvalidOperation

# Create your views here.
class CreateDetail(generics.ListCreateAPIView): 
    queryset = Detail.objects.all()
    serializer_class = DetailSerialiser
    
class ListProduct(generics.ListAPIView, ProductQsField):
    queryset = Product.objects.all()
    serializer_class = ProductSerialiser
    # qs_field_expired = "expired"
    # qs_rupture = "rupture"
    permission_classes = [IsAuthenticated, ]

class CreateProduct(GestionnaireEditorMixin, generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerialiser

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "stock_updates",
                 {
                    "type": "stock_update",
                    "message": {
                        "event": "product_created",
                        "data": response.data
                    }
                }
            )
        return response

class CreateBulkStock(GestionnaireEditorMixin, APIView):
    # permission_classes = [IsAuthenticated, IsGestionnaire]
    def post(self, request):
        productsToCreate = []
        productsToUpdate = []
        productList = request.data
        user = request.user
        addStockListInstance = []

        try:
            with transaction.atomic():
                for newProduct in productList:
                    if newProduct:
                        detail = newProduct.pop('detail')
                        marque = newProduct.pop('marque', None)
                        print("Marque", marque)

                        detailInstance, createdD = Detail.objects.get_or_create(
                            designation=detail['designation'], 
                            famille=detail['famille'], 
                            classe=detail['classe'], 
                            type_gros=detail['type_gros'],
                        )
                        marqueInstance = None
                        if marque:
                            marqueInstance, createdM = Marque.objects.get_or_create(nom=marque)
                        productExist = Product.objects.filter(
                            detail=detailInstance, marque=marqueInstance
                        ).first()

                        new_qte_gros = newProduct['qte_gros']
                        newProduct['qte_gros'] = new_qte_gros

                        if productExist: 
                            if int(newProduct['prix_gros']) and int(newProduct['prix_gros']) > 0:
                                productExist.prix_gros = int(newProduct['prix_gros'])
                            productExist.qte_gros += new_qte_gros

                            productsToUpdate.append(productExist)

                            addStockInstance = AjoutStock(
                                # qte_unit_transaction = newProduct['qte_unit'],
                                qte_gros_transaction = newProduct['qte_gros'],
                                # qte_detail_transaction = newProduct['qte_detail'],
                                type_transaction="Maj",
                                prix_gros = productExist.prix_gros,
                                # prix_unit = productExist.prix_unit,
                                # prix_detail = productExist.prix_detail,
                                prix_total = (int(productExist.prix_gros) * int( newProduct['qte_gros'])),
                                product=productExist,
                                gestionnaire=user
                            )
                            addStockListInstance.append(addStockInstance)
                        else:
                            if marque:
                                productsToCreate.append(Product(**newProduct, detail=detailInstance, marque=marqueInstance)) 
                            else :
                                productsToCreate.append(Product(**newProduct, detail=detailInstance)) 
                        

                if len(productsToUpdate) > 0:
                    Product.objects.bulk_update(productsToUpdate, fields=['prix_gros', 'qte_gros'])
                if len(productsToCreate) > 0:
                    for product in productsToCreate:
                        product.save()

                        addStockListInstance.append(
                            AjoutStock(
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
                        )

                AjoutStock.objects.bulk_create(addStockListInstance)

                channel_layer = get_channel_layer()
                try:
                    async_to_sync(channel_layer.group_send)(
                        "stock_updates",
                        {
                            "type": "stock_update",
                            "message": {
                                "event": "product_bulk_updated",
                                "data": ProductSerialiser(productsToUpdate + productsToCreate, many=True).data
                            }
                        }
                    )
                except Exception as e:
                    print(f"Erreur WebSocket (Redis): {e}")

                return Response("Success", status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(f'Error {e}', status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateProduct(generics.RetrieveUpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerialiser
    lookup_field = 'pk'

    def patch(self, request, *args, **kwargs):
        datas = request.data.copy()
        user = request.user

        with transaction.atomic():
            product = self.get_object()            
            designation = datas.get('designation', '')
            qte_gros = int(datas['qte_gros'])
            if int(qte_gros)<0:
                return Response({"message" : "Les valeurs ne peuvent pas être negatif"}, status=status.HTTP_400_BAD_REQUEST)
            if  int(qte_gros)>0:
                # qte_gros += product.qte_gros
                # qte_detail += product.qte_detail
                datas['qte_gros'] = qte_gros
            else :
                datas.pop("qte_gros", None)
            if designation :
                productDetail = product.detail
                productDetail.designation = designation
                productDetail.save()
            
            prix_gros = datas.get('prix_gros', product.prix_gros)
            AjoutStock.objects.create(
                # qte_unit_transaction=qte_unit,
                qte_gros_transaction= qte_gros,
                # qte_detail_transaction=qte_detail,
                type_transaction="Maj",
                prix_gros = prix_gros,
                # prix_unit = prix_unit,
                # prix_detail = prix_detail,
                prix_total = (int(prix_gros) * int( qte_gros)),
                product=product,
                gestionnaire=user   
            )
        request._full_data = datas
        response =  super().patch(request, *args, **kwargs)
        if(response):
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "stock_updates",
                 {
                    "type": "stock_update",
                    "message": {
                        "event": "product_updated",
                        "data": response.data
                    }
                }
            )
        return response
    
class DeleteProduct(generics.DestroyAPIView, generics.ListAPIView, GestionnaireEditorMixin):
    queryset = Product.objects.all()
    serializer_class = ProductSerialiser

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        data_id = instance.id
        response = super().destroy(request, *args, **kwargs)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "stock_updates",
                {
                "type": "stock_update",
                "message": {
                    "event": "product_deleted",
                    "data": {"id": data_id}
                }
            }
        )
        return response

class SellProduct(VendeurEditorMixin, generics.ListCreateAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        try:
            user = self.request.user
            prix_gros = 0
            produit = Product.objects.filter(id=serializer.validated_data.get('product_id')).first()
            qte_gros = serializer.validated_data.get('qte_gros_transaction')
            if qte_gros > 0 :
                produit.qte_gros -= qte_gros
                prix_gros = qte_gros * produit.qte_gros
            produit.save()
            facture = Facture.objects.create(
                prix_total = prix_gros ,
                prix_restant = 0,
                owner = user
            )

            serializer.save(facture = facture)
            instanceP = serializer.instance

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "stock_updates",
                 {
                    "type": "stock_update",
                    "message": {
                        "event": "product_updated",
                        "data": ProductSerialiser(produit).data
                    }
                }
            )
            async_to_sync(channel_layer.group_send)(
                "transaction_updates",
                 {
                    "type": "transaction_update",
                    "message": {
                        "event": "vente_created",
                        "data": serializer.data
                    }
                }
            )
        #Capture l'erreur de validation
        except ValidationError as e:
            raise e
        except Exception as e:
            raise BaseException()

class SellBulkProduct(VendeurEditorMixin, generics.ListCreateAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer
    
    def post(self, request):
        datas = request.data
        user = request.user
            
        customer = datas.get('customer')
        prixRestant = datas.get('prix_restant', 0)
                    
        venteList = datas.get("ventes", [])
        venteInstancList = []
        factureDatas = None
        try:
            with transaction.atomic():
                customer_object, created = Customer.objects.get_or_create(nom=customer)
                facture = Facture(
                    prix_total=0,
                    prix_restant=0,
                    owner=user,
                    customer=customer_object
                )
                prix_gros = 0
                modified_products = []
                
                for vente in venteList:
                    product_id = vente.get('product_id', None)
                    new_prix_vente = vente.get('new_prix_vente', None)
                    try:
                        produit = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)

                    qteGrosVente = vente['qte_gros_transaction']
                    
                    if qteGrosVente < 0:
                        return Response({"message": "Erreur de quantité de vente"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    qteGrosStock = produit.qte_gros
                    qteGrosStockAvant = qteGrosStock

                    if qteGrosStock >= qteGrosVente:
                        qteGrosStock -= qteGrosVente
                    else:
                        return Response({"message": 'La quantité est invalide ou dépasse le stock'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    produit.qte_gros = qteGrosStock
                    
                    venteInstance = VenteProduct(
                        product=produit,
                        qte_gros_transaction=qteGrosVente,
                        qte_avant=qteGrosStockAvant,
                        qte_apres=qteGrosStock,
                        prix_vente=new_prix_vente if new_prix_vente else produit.prix_gros,
                        type_transaction="Vente",
                        prix_total=(int(qteGrosVente * new_prix_vente) if new_prix_vente
                                    else int(qteGrosVente * produit.prix_gros)),
                        facture=facture,
                    )
                    
                    produit.save()
                    modified_products.append(produit)
                    prix_gros += int(qteGrosVente * new_prix_vente) if new_prix_vente else int(qteGrosVente * produit.prix_gros)
                    
                    venteInstancList.append(venteInstance)

                facture.save()
                facture.prix_total = prix_gros

                prixRestant = Decimal(str(prixRestant))
                customer_avance = Decimal(str(customer_object.avance or 0))

                # Utilisation de l'avance du customer
                if customer_avance > 0 and prixRestant > 0:
                    used = min(customer_avance, prixRestant)
                    prixRestant -= used
                    customer_object.avance = customer_avance - used
                    Reglement.objects.create(
                        content_type=ContentType.objects.get_for_model(facture),
                        object_id=facture.id,
                        montant=used,
                        type_r="payement_avance",
                    )
                    Reglement.objects.create(
                        content_type=ContentType.objects.get_for_model(Customer),
                        object_id=customer_object.id,
                        montant=used,
                        type_r="payement_avance",
                        remarque=f"Utilisation avance facture n°{facture.num}"
                    )

                # Si reste à payer, enregistrer et ajuster la trosa
                if prixRestant > 0:
                    Reglement.objects.create(
                        content_type=ContentType.objects.get_for_model(Customer),
                        object_id=customer_object.id,
                        montant=prixRestant,
                        type_r="ajout",
                        remarque=f"facture n°{facture.num}"
                    )
                    customer_object.trosa = (customer_object.trosa or 0) + prixRestant

                facture.prix_restant = prixRestant
                facture.save()
                customer_object.save()

                if len(venteInstancList) > 0:
                    VenteProduct.objects.bulk_create(venteInstancList)

                    channel_layer = get_channel_layer()
                    try:
                        async_to_sync(channel_layer.group_send)(
                            "stock_updates",
                            {
                                "type": "stock_update",
                                "message": {
                                    "event": "product_bulk_updated",
                                    "data": ProductSerialiser(modified_products, many=True).data
                                }
                            }
                        )

                        factureData = Facture.objects.filter(pk=facture.pk).first()
                        factureDatas = FactureSerialiser(factureData).data
                        
                        async_to_sync(channel_layer.group_send)(
                            "transaction_updates",
                            {
                                "type": "transaction_update",
                                "message": {
                                    "event": "vente_bulk_created",
                                    "data": factureDatas
                                }
                            }
                        )
                    except Exception as e:
                        print(f"Erreur WebSocket (Redis): {e}")

                    return Response(factureDatas, status=status.HTTP_201_CREATED)
                else:
                    return Response({'message': "Erreur de création"}, status=status.HTTP_400_BAD_REQUEST)

        except AttributeError as e:
            return Response({"message": f"Erreur d'attribut{e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": f"Erreur: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateFilAttenteProduct(VendeurEditorMixin, generics.ListCreateAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        filtre = {"type_transaction" : "attente"}
        return qs.filter(**filtre)

    def post(self, request):
        datas = request.data
        user = request.user
            
        customer = datas.get('customer')
        prixRestant = datas.get('prix_restant', 0)
        venteList = datas.get("ventes", [])
        venteInstancList = []
        
        try:
            with transaction.atomic():
                customer_object, created = Customer.objects.get_or_create(nom=customer)
                filAttente = FilAttenteProduct(
                    prix_total=0,
                    prix_restant=0,
                    owner=user,
                    customer=customer_object
                )
                filAttente.save()
                prix_gros = 0
                modified_products = []
                
                for vente in venteList:
                    product_id = vente['product_id']
                    new_prix_vente = vente.get('new_prix_vente', None)
                    try:
                        produit = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)
                    
                    qteGrosVente = vente['qte_gros_transaction']
                    
                    if qteGrosVente < 0:
                        return Response({"message": "Erreur de quantité de vente"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    qteGrosStock = produit.qte_gros
                    qteGrosStockAvant = qteGrosStock

                    if qteGrosStock >= qteGrosVente:
                        if qteGrosStock < qteGrosVente:
                            return Response({"message": "Stock insuffisant"}, status=status.HTTP_400_BAD_REQUEST)
                        qteGrosStock -= qteGrosVente
                    else:
                        return Response({"message": 'La quantité est invalide ou dépasse le stock'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    produit.qte_gros = qteGrosStock

                    venteInstance = VenteProduct(
                        product=produit,
                        qte_gros_transaction=qteGrosVente,
                        qte_avant=qteGrosStockAvant,
                        qte_apres=qteGrosStock,
                        prix_vente=new_prix_vente if new_prix_vente else produit.prix_gros,
                        type_transaction="Attente",
                        prix_total=(int(qteGrosVente * new_prix_vente) if new_prix_vente
                                    else int(qteGrosVente * produit.prix_gros)),
                        fil_attente=filAttente,
                    )
                    
                    produit.save()
                    modified_products.append(produit)
                    prix_gros += int(qteGrosVente * new_prix_vente) if new_prix_vente else int(qteGrosVente * produit.prix_gros)
                    
                    venteInstancList.append(venteInstance)
                
                filAttente.prix_restant = prixRestant
                filAttente.prix_total = prix_gros
                filAttente.save()
                
                if len(venteInstancList) > 0:
                    VenteProduct.objects.bulk_create(venteInstancList)
                    filAttentesSerialiser = FilAttenteSerialiser(filAttente).data

                    channel_layer = get_channel_layer()
                    try:
                        async_to_sync(channel_layer.group_send)(
                            "stock_updates",
                            {
                                "type": "stock_update",
                                "message": {
                                    "event": "product_bulk_updated",
                                    "data": ProductSerialiser(modified_products, many=True).data
                                }
                            }
                        )
                        
                        async_to_sync(channel_layer.group_send)(
                            "transaction_updates",
                            {
                                "type": "transaction_update",
                                "message": {
                                    "event": "fil_attente_created",
                                    "data": filAttentesSerialiser
                                }
                            }
                        )
                    except Exception as e:
                        print(f"Erreur WebSocket (Redis): {e}")
                    
                    return Response(filAttentesSerialiser, status=status.HTTP_201_CREATED)
                else:
                    return Response({'message': "Erreur de création"}, status=status.HTTP_400_BAD_REQUEST)
                
        except AttributeError as e:
            return Response({"message": f"Erreur d'attribut{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"message": f"Erreur: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ValidateFilAttente(VendeurEditorMixin, generics.ListCreateAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer

    def create(self, request, *args, **kwargs):
        try:
            filId = kwargs['pk']
            venteList = FilAttenteProduct.finaliser(self, id=filId)
            data = VenteProductSerializer(venteList, many = True).data
            
            channel_layer = get_channel_layer()
            try:
                async_to_sync(channel_layer.group_send)(
                    "transaction_updates",
                    {
                        "type": "transaction_update",
                        "message": {
                            "event": "fil_attente_validated",
                            "data": {"id": filId, "ventes": data}
                        }
                    }
                )
            except Exception as e:
                print(f"Erreur WebSocket (Redis): {e}")
            return Response(data=data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"message" : f"Erreur {e}"})

class CancelFilAttente(VendeurEditorMixin, generics.RetrieveDestroyAPIView):
    queryset = FilAttenteProduct.objects.all()
    serializer_class = FilAttenteSerialiser
    lookup_field = 'pk'
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        data_id = instance.id
        listVente = instance.venteproduct_related.all()
        with transaction.atomic():
            try:
                productList = []
                for vente in listVente:
                    product = Product.objects.get(id = vente.product.id)
                    qte_gros_cancel = vente.qte_gros_transaction
                    product.qte_gros += qte_gros_cancel
                    productList.append(product)
                    product.save()
                    vente.delete()
                
                self.perform_destroy(instance)

                channel_layer = get_channel_layer()
                try:
                    async_to_sync(channel_layer.group_send)(
                        "stock_updates",
                            {
                            "type": "stock_update",
                            "message": {
                                "event": "product_bulk_updated",
                                "data": ProductSerialiser(productList, many=True).data
                            }
                        }
                    )
                
                    async_to_sync(channel_layer.group_send)(
                        "transaction_updates",
                        {
                            "type": "transaction_update",
                            "message": {
                                "event": "fil_attente_deleted",
                                "data": {"id": data_id}
                            }
                        }
                    )
                except Exception as e:
                    print(f"Erreur WebSocket (Redis): {e}")

                return Response(status=status.HTTP_200_OK, data=ProductSerialiser(productList, many = True).data)
            except Product.DoesNotExist:
                return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({"message": f"Erreur Serveur {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateFilAttente(VendeurEditorMixin, generics.UpdateAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer

    def update(self, request, *args, **kwargs):
        filId = kwargs['pk']
        
        try:
            datas = request.data
            client = datas.get('client', "")
            prixRestant = datas.get('prix_restant', None)
                        
            venteList = datas.get("ventes", [])
            filAttente = FilAttenteProduct.objects.get(id=filId)     
            old_prix_restant = filAttente.prix_restant               
            venteInstanceList = []
            newVenteInstanceList = []
            # newPrixGrosVenteTotal = 0
            increment_prix_restant = 0
            modified_products = []
            with transaction.atomic():
                for vente in venteList:
                    productId = vente.get('product_id', None)
                    new_prix_vente = vente.get('new_prix_vente', None)
                    if productId :
                        try:
                            produit = Product.objects.get(id=productId)
                        except Product.DoesNotExist:
                            return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)
                        
                        qteGrosVente = vente['qte_gros_transaction']
                        
                        if qteGrosVente < 0 :
                            return Response({"message": "Erreur de quantité de vente"}, status=status.HTTP_400_BAD_REQUEST)
                        
                        qteGrosStock = produit.qte_gros
                        #Condition
                        if qteGrosStock >= qteGrosVente:
                            if qteGrosStock < qteGrosVente:
                                return Response({"message": "Stock insuffisant"}, status=status.HTTP_400_BAD_REQUEST)
                            qteGrosStock -= qteGrosVente
                        else:
                            return Response({"message": 'La quantité est invalide ou dépasse le stock'}, status=status.HTTP_400_BAD_REQUEST)
                        
                        produit.qte_gros = qteGrosStock
                        vente_price_total = (int(qteGrosVente * new_prix_vente) if new_prix_vente
                                    else
                                        int(qteGrosVente * produit.prix_gros))
                        # nouvelle vente augmente toujours le restant
                        increment_prix_restant += vente_price_total
                        newVenteInstance = VenteProduct(
                            product=produit,
                            qte_gros_transaction=qteGrosVente,
                            prix_vente = new_prix_vente if new_prix_vente else produit.prix_gros,
                            type_transaction="Attente",
                            prix_total=vente_price_total,
                            fil_attente=filAttente
                        )
                        
                        produit.save()
                        modified_products.append(produit)
                        
                        newVenteInstanceList.append(newVenteInstance)

                    else :
                        venteId = vente.get("id", None)
                        if not venteId:
                            return Response({"message": "ID de vente manquant"}, status=status.HTTP_400_BAD_REQUEST)
                        try:
                            venteInstance = VenteProduct.objects.select_for_update().get(id=venteId, fil_attente=filAttente)
                        except VenteProduct.DoesNotExist:
                            return Response({"message": "Vente introuvable"}, status=status.HTTP_404_NOT_FOUND)

                        product = venteInstance.product
                        old_qte = int(venteInstance.qte_gros_transaction)
                        newQteGrosVente = int(vente.get("qte_gros_transaction", old_qte))

                        if newQteGrosVente < 0:
                            return Response({"message": "Erreur de quantité de vente"}, status=status.HTTP_400_BAD_REQUEST)

                        # calcul de la différence : si augmentation, on prélève et on l'ajoute au prix_restant
                        diff = newQteGrosVente - old_qte
                        if diff > 0:
                            if product.qte_gros < diff:
                                return Response({"message": "Stock insuffisant pour la mise à jour"}, status=status.HTTP_400_BAD_REQUEST)
                            #QTE ajoute (Diif si positif)
                            product.qte_gros -= diff
                            # ajouter la différence au montant restant
                            increment_prix_restant += int(diff * new_prix_vente if new_prix_vente else product.prix_gros)
                        elif diff == 0 and new_prix_vente:
                            increment_prix_restant -= int(old_qte * venteInstance.prix_vente)
                            increment_prix_restant += int(old_qte * new_prix_vente if new_prix_vente else product.prix_gros)
                        elif diff < 0 :
                            # La difference analana anaty prix_restant
                            diff *= -1
                            if diff > 0:
                                qte_dec = diff
                                increment_prix_restant -= int(qte_dec * new_prix_vente if new_prix_vente else product.prix_gros)
                                product.qte_gros += diff
                        product.save()
                        modified_products.append(product)
                        venteInstance.prix_vente = int(new_prix_vente) if new_prix_vente else product.prix_gros
                        venteInstance.prix_total = (int(newQteGrosVente * new_prix_vente) if new_prix_vente
                                                    else
                                                    int(newQteGrosVente * product.prix_gros))
                        venteInstance.qte_gros_transaction = newQteGrosVente
                        venteInstanceList.append(venteInstance)
                        
                #Atao zero aloha veo recalculena
                filAttente.prix_restant = max(0, int(old_prix_restant) + int(increment_prix_restant))
                if len(venteInstanceList) > 0:
                    VenteProduct.objects.bulk_update(venteInstanceList, fields=["qte_gros_transaction", "date", "prix_total", "prix_vente"])

                if prixRestant:
                    filAttente.prix_restant = prixRestant
                if client:
                    filAttente.client = client
                filAttente.date = timezone.now()
                if len(newVenteInstanceList) > 0:
                    VenteProduct.objects.bulk_create(newVenteInstanceList)

                new_total = VenteProduct.objects.filter(fil_attente=filAttente).aggregate(total = Sum("prix_total"))['total'] or 0
                filAttente.prix_total = new_total
                filAttente.save()

            data = FilAttenteSerialiser(filAttente).data
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "transaction_updates",
                    {
                        "type": "transaction_update",
                        "message": {
                            "event": "fil_attente_updated",
                            "data": data
                        }
                    }
                )

                async_to_sync(channel_layer.group_send)(
                    "stock_updates",
                        {
                        "type": "stock_update",
                        "message": {
                            "event": "product_bulk_updated",
                            "data": ProductSerialiser(modified_products, many=True).data
                        }
                    }
                )
            except Exception as e:
                print(f"Erreur WebSocket (Redis): {e}")

            return Response(data, status=status.HTTP_205_RESET_CONTENT) 
        except FilAttenteProduct.DoesNotExist:
            return Response({"message":"Fil d'attente introuvale"})
        except Exception as e:
            return Response({"message" : f"Error ${e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListFilAttente(generics.ListAPIView, userFactureQs):
    queryset = FilAttenteProduct.objects.all()
    serializer_class = FilAttenteSerialiser

class ListVente(generics.ListAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer

class DeleteVente(VendeurEditorMixin, generics.DestroyAPIView):
    queryset = VenteProduct.objects.all()
    serializer_class = VenteProductSerializer

    def destroy(self, request, *args, **kwargs):
        instance : VenteProduct = self.get_object()
        data_id = instance.id
        try:
            with transaction.atomic():
                product : Product = instance.product
                product.qte_gros += instance.qte_gros_transaction
                product.save()
                facture : Facture = instance.facture
                totalVenteDeleted = instance.prix_total
                filAttente = instance.fil_attente
                self.perform_destroy(instance)

                if facture:
                    venteList = facture.venteproduct_related.all()
                    facture.prix_total = 0
                    for vente  in venteList:
                        facture.prix_total += vente.qte_gros_transaction * vente.product.prix_gros
                    facture.save()
                elif filAttente:
                    venteList = filAttente.venteproduct_related.all()
                    filAttente.prix_total = 0
                    for vente  in venteList:
                        filAttente.prix_total += vente.qte_gros_transaction * vente.product.prix_gros
                    # si un montant restant existe, on le réduit du montant de la vente supprimée (sans passer sous 0)
                    if getattr(filAttente, "prix_restant", 0) and filAttente.prix_restant > 0:
                        filAttente.prix_restant = max(0, filAttente.prix_restant - totalVenteDeleted)
                    filAttente.save()

            channel_layer = get_channel_layer()
            try:
                async_to_sync(channel_layer.group_send)(
                    "stock_updates",
                        {
                        "type": "stock_update",
                        "message": {
                            "event": "product_updated",
                            "data": ProductSerialiser(product).data
                        }
                    }
                )

                async_to_sync(channel_layer.group_send)(
                    "transaction_updates",
                    {
                        "type": "transaction_update",
                        "message": {
                            "event": "vente_deleted",
                            "data": {"id": data_id}
                        }
                    }
                )
            except Exception as e:
                print(f"Erreur WebSocket (Redis): {e}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except AttributeError as e:
            return Response({"message": f"Erreur d'attribut{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"message" : f"Error ${e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
      

class ListTransactions(GestionnaireEditorMixin, generics.ListAPIView):
    queryset = AjoutStock.objects.all()
    serializer_class = AjoutStockSerialiser

class RetrieveTransactions(GestionnaireEditorMixin, generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerialiser
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        ajout = instance.ajoutstock_related.all()
        serializer = self.get_serializer(instance)
        ajoutsersialiser = AjoutStockSerialiser(ajout, many = True).data
        return Response(ajoutsersialiser)

##Mbola ts vita
class CancelFacture(VendeurEditorMixin, generics.RetrieveDestroyAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureSerialiser
    lookup_field = 'pk'
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        data_id = instance.id
        listVente = instance.venteproduct_related.all()
        with transaction.atomic():
            try:
                productList = []
                for vente in listVente:
                    product = Product.objects.get(id = vente.product.id)

                    qte_gros_cancel = vente.qte_gros_transaction
                    product.qte_gros += qte_gros_cancel
                    product.save()
                    productList.append(product)
                    
                self.perform_destroy(instance)

                channel_layer = get_channel_layer()
                try:
                    async_to_sync(channel_layer.group_send)(
                        "stock_updates",
                            {
                            "type": "stock_update",
                            "message": {
                                "event": "product_bulk_updated",
                                "data": ProductSerialiser(productList, many=True).data
                            }
                        }
                    )
                
                    async_to_sync(channel_layer.group_send)(
                        "transaction_updates",
                        {
                            "type": "transaction_update",
                            "message": {
                                "event": "facture_cancelled",
                                "data": {"id": data_id}
                            }
                        }
                    )
                except Exception as e:
                    print(f"Erreur WebSocket (Redis): {e}")

                return Response(status=status.HTTP_200_OK, data=ProductSerialiser(productList, many=True).data)
            except Product.DoesNotExist:
                return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({"message": f"Erreur Serveur {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FacturePagination(PageNumberPagination):
    page_size = 50 
    page_size_query_param = 'page_size'  # optionnel: permet au client de définir le nombre d'objets par page
    max_page_size = 100  # optionnel: limite max

class ListFacture(generics.ListAPIView, userFactureQs):
    queryset = Facture.objects.all()
    serializer_class = FactureSerialiser
    pagination_class = FacturePagination

from datetime import datetime
from django.utils.timezone import now, timedelta,  make_aware, datetime, get_current_timezone
from django.db.models import Sum
class TotalFactureView(APIView):
    permission_classes= [IsAuthenticated, ]
    
    def get(self, request):
        today = datetime.combine(now().date(), datetime.min.time())
        next_day = today + timedelta(days=1)

        tz = get_current_timezone()
        today = make_aware(today, timezone=tz)
        # next_day = make_aware(next_day, timezone=tz)
        # qs = qs.filter(date__gte=day, date__lt=next_day)
        # start_week = today - timedelta(days=today.weekday())  # lundi de la semaine
        start_month = today.replace(day=1)
        factureqs = Facture.objects.all()
        user = request.user
        userType = user.groups.filter(name = 'vendeurs').exists()
        if userType:
            data = {"owner" : user}
            factureqs =  factureqs.filter(**data)
        factureThisMonth = factureqs.filter(date__gte=start_month)
        # total_jour = factureQs.filter(date__gte=today, date__lt=next_day).aggregate(total=Sum('prix_total'))['total'] or 0
        # total_semaine = factureQs.filter(date__gte=start_week).aggregate(total=Sum('prix_total'))['total'] or 0
        # total_mois = factureQs.filter(date__gte=start_month).aggregate(total=Sum('prix_total'))['total'] or 0

        return Response(FactureSerialiser(factureThisMonth, many = True).data)
class DeleteFacture(generics.DestroyAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureSerialiser

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        data_id = instance.id
        response = super().destroy(request, *args, **kwargs)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "transaction_updates",
            {
                "type": "transaction_update",
                "message": {
                    "event": "facture_deleted",
                    "data": {"id": data_id}
                }
            }
        )
        return response

class DeleteBulkFacture(APIView):
    def post(self, request):
        factureID = request.data.get('ids', [])
        if not isinstance(factureID, list):
            return Response({'error': 'ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                itemsToDeleted = Facture.objects.filter(id__in = factureID)
                count = itemsToDeleted.count()
                itemsToDeleted.delete()

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "transaction_updates",
                    {
                        "type": "transaction_update",
                        "message": {
                            "event": "facture_bulk_deleted",
                            "data": {"ids": factureID}
                        }
                    }
                )
                return Response({'deleted': count}, status=status.HTTP_200_OK)
        except AttributeError as e:
            return Response({'Erreur Attribut': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UpdateFacture(generics.RetrieveUpdateAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureSerialiser
    lookup_field = 'pk'
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_prix_restant = instance.prix_restant
        with transaction.atomic():
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            instance.refresh_from_db()
            new_prix_restant = instance.prix_restant
            montant_regle = old_prix_restant - new_prix_restant
            if montant_regle < 0:
                montant_regle = 0
            customer_obj = instance.customer
            if montant_regle > 0 and customer_obj:
                Reglement.objects.create(
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    montant=montant_regle
                )
                customer_obj.trosa = (customer_obj.trosa or 0) - montant_regle
                customer_obj.save()
                Reglement.objects.create(
                    content_type=ContentType.objects.get_for_model(Customer),
                    object_id=customer_obj.id,
                    montant=montant_regle,
                    type_r="paiement",
                    remarque=f"facture n°{instance.num} "
                )
        queryset = self.filter_queryset(self.get_queryset())
        if queryset._prefetch_related_lookups:
            instance._prefetched_objects_cache = {}
            prefetch_related_objects([instance], *queryset._prefetch_related_lookups)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "transaction_updates",
            {
                "type": "transaction_update",
                "message": {
                    "event": "facture_updated",
                    "data": serializer.data
                }
            }
        )
        return Response(serializer.data)    
# /*** TROSA  ****/
class CreateTrosa(generics.CreateAPIView):
    queryset = Trosa.objects.all()
    serializer_class = TrosaSerialiser

class ListTrosa(generics.ListAPIView):
    queryset = Trosa.objects.all()
    serializer_class = TrosaSerialiser

class DeleteTrosa(generics.RetrieveDestroyAPIView):
    queryset = Trosa.objects.all()
    serializer_class = TrosaSerialiser

class UpdateTrosa(generics.RetrieveUpdateAPIView):
    queryset = Trosa.objects.all()
    serializer_class = TrosaSerialiser

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_prix_restant = instance.montant_restant

        with transaction.atomic():  # Tout est dans une transaction
            # Valider les données avant de les appliquer
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)

            # Appliquer la mise à jour
            self.perform_update(serializer)

            # Recharger les données mises à jour
            instance.refresh_from_db()
            new_prix_restant = instance.montant_restant

            new_prix_restant = instance.montant_restant
            montant_regle = old_prix_restant - new_prix_restant

            if montant_regle > 0:
                # Création du règlement (rollback automatique si erreur ici)
                Reglement.objects.create(
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    montant=montant_regle
                )

        queryset = self.filter_queryset(self.get_queryset())
        if queryset._prefetch_related_lookups:
            instance._prefetched_objects_cache = {}
            prefetch_related_objects([instance], *queryset._prefetch_related_lookups)

        return Response(serializer.data)
 

class CustomerPagination(PageNumberPagination):
    page_size = 50 
    page_size_query_param = 'page_size'  # optionnel: permet au client de définir le nombre d'objets par page
    max_page_size = 100  # optionnel: limite max

class ListCustomer(generics.ListAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerialiser
    pagination_class = CustomerPagination

    def get_queryset(self):
        params = self.request.query_params
        qs = super().get_queryset()
        if "client" in params:
            qs = qs.filter(nom__icontains = params["client"])
        return qs
class RetrieveCustomer(generics.RetrieveAPIView):
    serializer_class = CustomerSerialiser
    queryset = Customer.objects.all()
    lookup_field = "pk"

class DeleteCustomer(GestionnaireEditorMixin, generics.RetrieveDestroyAPIView):
    serializer_class = CustomerSerialiser
    lookup_field = 'pk'

    def destroy(self, request, *args, **kwargs):
        customer = self.get_object()
        try:
            with transaction.atomic():
                # Refuser la suppression si des factures ont encore un restant > 0
                has_unpaid = Facture.objects.filter(customer=customer, prix_restant__gt=0).exists()
                if has_unpaid:
                    return Response(
                        {"message": "Le Customer a des factures impayées. Suppression impossible."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Supprimer les réglements liés aux factures du Customer
                factures_qs = Facture.objects.filter(customer=customer)
                facture_ids = list(factures_qs.values_list('id', flat=True))
                if facture_ids:
                    Reglement.objects.filter(
                        content_type=ContentType.objects.get_for_model(Facture),
                        object_id__in=facture_ids
                    ).delete()

                # Supprimer les factures liées au Customer
                factures_qs.delete()

                # Supprimer les réglements liés directement au Customer (historique trosa, paiements, ...)
                Reglement.objects.filter(
                    content_type=ContentType.objects.get_for_model(Customer),
                    object_id=customer.id
                ).delete()

                # Enfin supprimer le customer
                self.perform_destroy(customer)
                channel_layer = get_channel_layer()

                async_to_sync(channel_layer.group_send)(
                    f"customer_user_{request.user.id}",
                    {
                        "type": "customer_update",
                        "message": {
                            "action": "deleted",
                            "customer_id": customer.id,
                        }
                    }
                )

                return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"message": f"Erreur serveur: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    queryset = Customer.objects.all()

class ListFactureCustomer(generics.ListAPIView):
    serializer_class = FactureSerialiser

    def get_queryset(self):
        customer_id = self.kwargs.get("pk")

        return (
            Facture.objects
            .filter(customer=customer_id)
            .select_related(
                "customer",
                "owner",
            )
            .prefetch_related(
                Prefetch(
                    "venteproduct_related",
                    queryset=VenteProduct.objects.select_related(
                        "product",
                        "product__detail",
                    )
                ),
                "reglements"
            )
        )
    
class UpdateCustomerTrosa(generics.UpdateAPIView, VendeurEditorMixin):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerialiser
    lookup_field = 'pk'

    def patch(self, request, *args, **kwargs):
        montant = request.data.get('montant')
        if montant is None:
            return Response({"message": "Le montant est requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            montant = Decimal(str(montant))
        except (InvalidOperation, ValueError):
            return Response({"message": "Montant invalide"}, status=status.HTTP_400_BAD_REQUEST)
        if montant <= 0:
            return Response({"message": "Le montant doit être positif"}, status=status.HTTP_400_BAD_REQUEST)

        customer = self.get_object()

        try:
            with transaction.atomic():
                factures = Facture.objects.filter(customer=customer, prix_restant__gt=0).order_by('date')
                restant = montant
                factures_modifiees = []

                for facture in factures:
                    # arreter si le montant est 0
                    if restant <= 0:
                        break
                    # convertir en Decimal pour sécurité
                    prix_restant = Decimal(str(facture.prix_restant))
                    
                    to_paye = min(prix_restant, restant)

                    if to_paye <= 0:
                        continue

                    facture.prix_restant = float(prix_restant - to_paye)
                    facture.save()

                    Reglement.objects.create(
                        content_type=ContentType.objects.get_for_model(facture),
                        object_id=facture.id,
                        montant=(to_paye)
                    )

                    restant -= to_paye
                    factures_modifiees.append(facture)

                montant_applique = (montant - restant)
                if restant > 0:
                    customer.avance = (customer.avance or Decimal("0")) + restant
                if montant_applique > 0:
                    # Mettre à jour la trosa du customer
                    customer.trosa = (customer.trosa or 0) - montant_applique
                    customer.save()
                    # Enregistrer un reglement au niveau client (type_r optionnel)

                    n_factures = len(factures_modifiees)
                    nums = ", ".join(str(getattr(f, "num", f.id)) for f in factures_modifiees) if n_factures > 0 else ""
                    remarque = ""
                    if n_factures > 0:
                        remarque = f"{n_factures} facture(s): {nums}"
                    else:
                        remarque =  f"Règlement de {montant_applique}"
                    # remarque = (f"Règlement de {montant_applique} pour {n_factures} facture(s): {nums}"
                    #             if n_factures > 0 else f"Règlement de {montant_applique}")

                    Reglement.objects.create(
                        content_type=ContentType.objects.get_for_model(Customer),
                        object_id=customer.id,
                        montant=montant_applique,
                        type_r="paiement",
                        remarque=remarque
                    )
                channel_layer = get_channel_layer()
                group_name = f"customer_user_{request.user}"

                async_to_sync(channel_layer.group_send)(
                    f"customer_user_{request.user.id}",
                    {
                        "type": "customer_update",
                        "message": {
                            "action": "payment",
                            "customer": CustomerSerialiser(customer).data,
                            "factures": FactureSerialiser(
                                factures_modifiees,
                                many=True
                            ).data,
                            "montant_applique": float(montant_applique),
                        }
                    }
                )
                return Response({
                    "customer": CustomerSerialiser(customer).data,
                    "factures": FactureSerialiser(factures_modifiees, many=True).data,
                    "montant_recu": float(montant),
                    "montant_applique": montant_applique,
                    "montant_restant": float(restant)
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"message": f"Erreur serveur: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        