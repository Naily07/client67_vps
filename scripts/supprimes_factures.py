from datetime import datetime
from django.utils.timezone import make_aware
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from stock.models import Facture, Reglement

date_limite = make_aware(datetime(2026, 5, 1))

with transaction.atomic():

    factures = Facture.objects.filter(
        prix_restant=0,
        date__lt=date_limite
    )

    facture_ids = list(
        factures.values_list("id", flat=True)
    )

    # Suppression des règlements associés aux factures
    Reglement.objects.filter(
        content_type=ContentType.objects.get_for_model(Facture),
        object_id__in=facture_ids
    ).delete()

    nb_factures = factures.count()

    # Suppression des factures
    factures.delete()

    print(f"{nb_factures} factures supprimées.")