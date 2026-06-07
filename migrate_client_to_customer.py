from django.db import transaction
from django.db.models import Q
from collections import defaultdict
from stock.models import Facture, Customer, Reglement, InvoiceCounter
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


def _generer_num(facture):
    """Génère et sauvegarde un num de facture si manquant."""
    if facture.num:
        print(f"  → Numéro existant : {facture.num}")
        return
    current_year = facture.date.year if facture.date else timezone.now().year
    counter, _ = InvoiceCounter.objects.select_for_update().get_or_create(
        year=current_year,
        defaults={"current": 0}
    )
    counter.current += 1
    counter.save()
    facture.num = f"FAC-{counter.year}-{counter.current:06d}"
    facture.save(update_fields=['num'])
    print(f"  → Numéro généré : {facture.num}")


def _creer_reglement_si_absent(customer_obj, facture):
    """Crée le règlement uniquement s'il n'existe pas déjà."""
    if (facture.prix_restant or 0) <= 0:
        return

    remarque = f"Reste facture {facture.num}"
    customer_ct = ContentType.objects.get_for_model(Customer)

    deja_existant = Reglement.objects.filter(
        content_type=customer_ct,
        object_id=customer_obj.id,
        remarque=remarque
    ).exists()

    if deja_existant:
        print(f"  → Règlement déjà existant pour facture n°{facture.num} — ignoré")
        return

    Reglement.objects.create(
        content_type=customer_ct,
        object_id=customer_obj.id,
        montant=facture.prix_restant,
        type_r="ajout",
        remarque=remarque
    )
    print(f"  → Règlement créé : reste {facture.prix_restant} (facture n°{facture.num})")


def migrate_single_facture(facture_id):
    """Migre une seule facture pour test avant migration globale."""
    try:
        facture = Facture.objects.get(id=facture_id)
    except Facture.DoesNotExist:
        print(f"Facture id={facture_id} introuvable.")
        return

    if not facture.client:
        print(f"Facture id={facture_id} n'a pas de client — ignorée.")
        return

    # Vérification : déjà migrée
    if facture.customer is not None:
        print(f"Facture id={facture_id} déjà migrée (customer={facture.customer}) — ignorée.")
        return

    print(f"\n=== Migration facture id={facture_id} | client='{facture.client}' ===")

    with transaction.atomic():
        _generer_num(facture)

        customer_obj, created = Customer.objects.get_or_create(nom=facture.client)
        action = "créé" if created else "existant"
        print(f"  → Customer '{facture.client}' ({action})")

        if (facture.prix_restant or 0) > 0:
            customer_obj.trosa = (customer_obj.trosa or 0) + facture.prix_restant
            customer_obj.save()
            print(f"  → trosa mise à jour : {customer_obj.trosa}")

        facture.customer = customer_obj
        facture.save(update_fields=['customer'])
        print(f"  → Facture n°{facture.num} assignée au customer")

        _creer_reglement_si_absent(customer_obj, facture)

    print(f"=== Migration facture id={facture_id} terminée ===\n")


@transaction.atomic
def migrate_client_to_customer():
    # 1. Récupérer uniquement les factures pas encore migrées
    factures = list(Facture.objects.filter(
        Q(client__isnull=False) & ~Q(client=""),
        customer__isnull=True  # ← pas encore migrées
    ).select_related())

    if not factures:
        print("Aucune facture à migrer — tout est déjà migré.")
        return

    # 2. Générer les numéros manquants
    factures_sans_num = [f for f in factures if not f.num]
    print(f"{len(factures_sans_num)} facture(s) sans numéro trouvée(s).")
    for facture in factures_sans_num:
        _generer_num(facture)

    # 3. Grouper les factures par nom de client
    factures_by_client = defaultdict(list)
    for facture in factures:
        factures_by_client[facture.client].append(facture)

    print(f"\n{len(factures_by_client)} clients distincts trouvés.")

    for nom_client, factures_list in factures_by_client.items():
        customer_obj, created = Customer.objects.get_or_create(nom=nom_client)
        action = "créé" if created else "existant"
        print(f"\nCustomer '{nom_client}' ({action})")

        total_restant = sum(f.prix_restant or 0 for f in factures_list)
        print(f"  → {len(factures_list)} facture(s) | total prix_restant = {total_restant}")

        customer_obj.trosa = (customer_obj.trosa or 0) + total_restant
        customer_obj.save()

        for facture in factures_list:
            facture.customer = customer_obj
            facture.save(update_fields=['customer'])
            print(f"  → Facture n°{facture.num} assignée (prix_restant={facture.prix_restant})")
            _creer_reglement_si_absent(customer_obj, facture)

    print("\nMigration terminée.")


# --- Usage ---
# Tester sur une seule facture
# migrate_single_facture(facture_id=33729)


# Une fois validé, lancer la migration globale
migrate_client_to_customer()