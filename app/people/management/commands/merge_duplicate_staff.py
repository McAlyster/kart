from django.contrib.postgres.search import TrigramSimilarity
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat

from people.models import Staff


class Command(BaseCommand):
    help = "Fusionne les staffs dupliqués"

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.5,
            help="Seuil de similarité pour considérer deux staffs comme des doublons (entre 0 et 1, par défaut 0.5)",
        )
        # ajout d'un argument facultatif pour rechercher avec un nom spécifique
        parser.add_argument(
            "--name", type=str, help='Rechercher des doublons pour un nom spécifique (ex: "Dupont")', required=False
        )

    def handle(self, *args, **options):
        threshold = options["threshold"] or 0.5
        name_filter = options["name"]

        # On concatène pour une recherche plus précise
        staffs = Staff.objects.annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))

        if name_filter:
            staffs = staffs.filter(full_name__unaccent__icontains=name_filter)

        processed = set()
        # On parcourt tous les staffs pour trouver des jumeaux potentiels
        for s1 in staffs:
            processed.add(s1.id)

            # Recherche de jumeaux
            matches = (
                Staff.objects.exclude(id__in=processed)
                .annotate(
                    full_name=Concat("user__first_name", Value(" "), "user__last_name"),
                    similarity=TrigramSimilarity("full_name", s1.full_name),
                )
                .filter(similarity__gt=threshold)
            )

            for s2 in matches:
                self.stdout.write(self.style.WARNING(f"\n--- DOUBLON POTENTIEL (Score: {s2.similarity:.2f}) ---"))
                self.stdout.write(
                    f"1) {s1.user.first_name} {s1.user.last_name} (ID: {s1.id}) | Task: {list(s1.productionstafftask_set.all().values_list('task__label', flat=True))} | Artist: {'Oui' if s1.user.artist_set.all().count() > 0 else 'Non'} | Productions: {list(s1.user.artist_set.all().values_list('artworks__title', flat=True))}"
                )
                self.stdout.write(
                    f"2) {s2.user.first_name} {s2.user.last_name} (ID: {s2.id}) | Task: {list(s2.productionstafftask_set.all().values_list('task__label', flat=True))} | Artist: {'Oui' if s2.user.artist_set.all().count() > 0 else 'Non'} | Productions: {list(s2.user.artist_set.all().values_list('artworks__title', flat=True))}"
                )

                choice = input("Qui garder ? (1 / 2 / Passer [Entrée]) : ").strip()

                if choice == "1":
                    delete_id = merge_staff(keep_staff=s1, delete_staff=s2)
                    self.stdout.write(self.style.SUCCESS(f"ID {delete_id} fusionné dans {s1.id}"))
                elif choice == "2":
                    delete_id = merge_staff(keep_staff=s2, delete_staff=s1)
                    self.stdout.write(self.style.SUCCESS(f"ID {delete_id} fusionné dans {s2.id}"))
                    break  # s1 est supprimé, on arrête de chercher des matches pour lui


def merge_staff(keep_staff, delete_staff):
    with transaction.atomic():  # Sécurité : tout passe ou tout échoue
        for rel in delete_staff._meta.related_objects:
            accessor_name = rel.get_accessor_name()
            print(f"Traitement de la relation {rel.related_model.__name__} via {accessor_name}")
            try:
                # On essaye d'accéder à l'objet lié à cette relation
                related_obj = getattr(delete_staff, accessor_name)
            except rel.related_model.DoesNotExist:
                # Si l'objet n'existe pas, on continue car il n'y a rien à transférer
                continue

            # CAS MANY-TO-ONE (ForeignKey classique)
            if rel.one_to_many:
                related_obj.update(**{rel.field.name: keep_staff})

            # CAS MANY-TO-MANY
            elif rel.many_to_many:
                for item in related_obj.all():
                    # On ajoute l'item au staff qu'on garde
                    getattr(keep_staff, accessor_name).add(item)

            # CAS ONE-TO-ONE
            elif rel.one_to_one:
                # On vérifie si le staff gardé a déjà cette relation
                if not hasattr(keep_staff, accessor_name):
                    setattr(related_obj, rel.field.name, keep_staff)
                    related_obj.save()
                else:
                    # CONFLIT : Les deux ont un profil/objet lié.
                    # On supprime celui du doublon (ou on le merge si nécessaire)
                    related_obj.delete()

        # Suppression finale
        delete_id = delete_staff.id
        delete_staff.delete()

        return delete_id
