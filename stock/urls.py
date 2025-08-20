from django.urls import path
from .views import *

urlpatterns = [
    path('', ListProduct.as_view(), name='produits'),
    path('create-product', CreateProduct.as_view(), name='create-produit'),
    path('create-stock', CreateBulkStock.as_view(), name='create-stock'),
    path('list/<str:etat>', ListProduct.as_view(), name='produit-expirer'),
    path('create-detail', CreateDetail.as_view(), name='create-detail'),
    path('delete-product/<int:pk>', DeleteProduct.as_view(), name='delete'),
    path('update-product/<int:pk>', UpdateProduct.as_view(), name='create-stock'),

    path('list-facture', ListFacture.as_view(), name='create-stock'),
    path('facture/total', TotalFactureView.as_view(), name='facture-total'),
    path('delete-facture/<int:pk>', DeleteFacture.as_view(), name='create-stock'),
    path('facture/bulk-delete', DeleteBulkFacture.as_view(), name='bulk-delete-stock'),
    path('update-facture/<int:pk>', UpdateFacture.as_view(), name='update-facture'),
    path('cancel-facture/<int:pk>', CancelFacture.as_view(), name='vente'),

    #Vendeur
    path('create-fil-attente', CreateFilAttenteProduct.as_view(), name='fil-attente-product'),
    path('validate-fil-attente/<int:pk>', ValidateFilAttente.as_view(), name='fil-attente-product'),
    path('cancel-fil-attente/<int:pk>', CancelFilAttente.as_view(), name='vente'),
    path('list-fil-attente', ListFilAttente.as_view(), name='create-stock'),
    path('update-fil-attente/<int:pk>', UpdateFilAttente.as_view(), name='fil-attente-product'),

    path('delete-vente/<int:pk>', DeleteVente.as_view(), name='vente-produit'),

    path('sell-product', SellBulkProduct.as_view(), name='vente-produit'),
    path('sell-one-product', SellProduct.as_view(), name='vente-produit'),
    path('sell-transactions', ListVente.as_view(), name='vente'),
    path('transactions', ListTransactions.as_view(), name='Ajout-MAJ'),
    path('transactions/<int:pk>', RetrieveTransactions.as_view(), name='Ajout-MAJ'),
    #Trosa
    path('list-trosa/', ListTrosa.as_view(), name='vente-produit'),
    path('create-trosa', CreateTrosa.as_view(), name='vente-produit'),
    path('delete-trosa/<int:pk>', DeleteTrosa.as_view(), name='vente-produit'),
    path('update-trosa/<int:pk>', UpdateTrosa.as_view(), name='vente-produit'),

    # path('list-fournisseur', ListFournisseur.as_view(), name='vente-produit'),
    # path('update-fournisseur', UpdateFournisserur.as_view(), name='update-fournisseur'),

]
