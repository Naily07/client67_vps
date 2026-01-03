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

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
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
            
        client = datas.get('client', "")
        prixRestant = datas.get('prix_restant', 0)
                    
        venteList = datas.get("ventes", [])
        venteInstancList = []
        
        try:
            with transaction.atomic():
                facture = Facture(
                    prix_total=0,
                    prix_restant=0,
                    owner=user
                )
                # prix_unit = 0
                prix_gros = 0
                # prix_detail = 0
                
                for vente in venteList:
                    product_id = vente.get('product_id', None)
                    new_prix_vente = vente.get('new_prix_vente', None)
                    try:
                        produit = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)

                    qteGrosVente = vente['qte_gros_transaction']
                    
                    if qteGrosVente < 0 :
                        return Response({"message": "Erreur de quantité de vente"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    qteGrosStock = produit.qte_gros
                    #CONVERSION
                    #Condition
                    if qteGrosStock >= qteGrosVente:
                        qteGrosStock -= qteGrosVente
                    else:
                        return Response({"message": 'La quantité est invalide ou dépasse le stock'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # produit.qte_unit = qteUnitStock
                    produit.qte_gros = qteGrosStock
                    # produit.qte_detail = qteDetailStock
                    
                    venteInstance = VenteProduct(
                        product=produit,
                        # qte_unit_transaction=qteUnitVente,
                        qte_gros_transaction=qteGrosVente,
                        prix_vente = new_prix_vente if new_prix_vente else produit.prix_gros,
                        # qte_detail_transaction=qteDetailVente,
                        type_transaction="Vente",
                         prix_total=(int(qteGrosVente * new_prix_vente) if new_prix_vente
                                    else
                                        int(qteGrosVente * produit.prix_gros)),
                        facture=facture,
                    )
                    
                    produit.save()
                    prix_gros += int(qteGrosVente * new_prix_vente) if new_prix_vente else  int(qteGrosVente * produit.prix_gros)
                    
                    venteInstancList.append(venteInstance)
                
                facture.prix_restant = prixRestant
                facture.prix_total =  prix_gros 
                facture.client = client
                facture.save()
                Reglement.objects.create(
                    content_type=ContentType.objects.get_for_model(facture),
                    object_id=facture.id,
                    montant= facture.prix_total - prixRestant
                )
                
                if len(venteInstancList) > 0:
                    VenteProduct.objects.bulk_create(venteInstancList)
                    factureData = Facture.objects.filter(pk=facture.pk).first()
                    factureDatas = FactureSerialiser(factureData).data
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
            
        client = datas.get('client', "")
        prixRestant = datas.get('prix_restant', 0)
        print("RESTANT", prixRestant)
        venteList = datas.get("ventes", [])
        venteInstancList = []
        
        try:
            with transaction.atomic():
                filAttente = FilAttenteProduct(
                    prix_total=0,
                    prix_restant=0,
                    owner=user
                )
                filAttente.save()
                prix_gros = 0
                
                for vente in venteList:
                    product_id = vente['product_id']
                    new_prix_vente = vente.get('new_prix_vente', None)
                    try:
                        produit = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        return Response({"message": "Produit introuvable"}, status=status.HTTP_404_NOT_FOUND)
                    
                    qteGrosVente = vente['qte_gros_transaction']
                    
                    if qteGrosVente < 0 :
                        return Response({"message": "Erreur de quantité de vente"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    qteGrosStock = produit.qte_gros
                    #CONVERSION
                    
                    #Condition
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
                        prix_vente = new_prix_vente if new_prix_vente else produit.prix_gros,
                        type_transaction="Attente",
                        prix_total=(int(qteGrosVente * new_prix_vente) if new_prix_vente
                                    else
                                        int(qteGrosVente * produit.prix_gros)),
                        fil_attente=filAttente,
                    )
                    
                    produit.save()
                    prix_gros += int(qteGrosVente * new_prix_vente) if new_prix_vente else  int(qteGrosVente * produit.prix_gros)
                    
                    venteInstancList.append(venteInstance)
                
                filAttente.prix_restant = prixRestant
                filAttente.prix_total =  prix_gros
                filAttente.client = client
                filAttente.save()
                
                if len(venteInstancList) > 0:
                    VenteProduct.objects.bulk_create(venteInstancList)
                    # filDatas = FilAttenteProduct.objects.filter(id__iexact = filAttente.id).first()
                    filAttentesSerialiser = FilAttenteSerialiser(filAttente).data
                    # print("Return", filAttentesSerialiser)
                    
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
            print("Les ventes", venteList)
            return Response(data=VenteProductSerializer(venteList, many = True).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"message" : f"Erreur {e}"})

class CancelFilAttente(VendeurEditorMixin, generics.RetrieveDestroyAPIView):
    queryset = FilAttenteProduct.objects.all()
    serializer_class = FilAttenteSerialiser
    lookup_field = 'pk'
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        print("Object to delete", instance)
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

            return Response(FilAttenteSerialiser(filAttente).data, status=status.HTTP_205_RESET_CONTENT) 
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
        print("Object to delete", instance)
        listVente = instance.venteproduct_related.all()
        with transaction.atomic():
            try:
                for vente in listVente:
                    product = Product.objects.get(id = vente.product.id)

                    qte_gros_cancel = vente.qte_gros_transaction
                    product.qte_gros += qte_gros_cancel
                    product.save()
                    
                self.perform_destroy(instance)
                return Response(status=status.HTTP_200_OK, data=ProductSerialiser(product).data)
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

        with transaction.atomic():  # Tout est dans une transaction
            # Valider les données avant de les appliquer
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)

            # Appliquer la mise à jour
            self.perform_update(serializer)

            # Recharger les données mises à jour
            instance.refresh_from_db()
            new_prix_restant = instance.prix_restant
            print("Facture", new_prix_restant)
            new_prix_restant = instance.prix_restant
            montant_regle = old_prix_restant - new_prix_restant
            print("montant regele", montant_regle)
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
 
# class ListFournisseur(generics.ListAPIView):
#     queryset = Fournisseur.objects.all()
#     serializer_class = FournisseurSerialiser

# class UpdateFournisserur(generics.UpdateAPIView):
#     queryset = Fournisseur.objects.all()
#     serializer_class = FournisseurSerialiser