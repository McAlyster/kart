from django.contrib.auth import get_user_model

from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat
from django.contrib.postgres.search import TrigramSimilarity
from django.core.management.base import BaseCommand

User = get_user_model()

class Command(BaseCommand):
    help = "Fusionne les utilisateurs dupliqués"

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.5,
            help='Seuil de similarité pour considérer deux utilisateurs comme des doublons (entre 0 et 1, par défaut 0.5)'
        )
        # ajout d'un argument facultatif pour rechercher avec un nom spécifique
        parser.add_argument(
            '--name',
            type=str,
            help='Rechercher des doublons pour un nom spécifique (ex: "Dupont")',
            required=False
        )

    def handle(self, *args, **options):
        threshold = options['threshold'] or 0.5
        name_filter = options['name']
        # On concatène pour une recherche plus précise
        users = User.objects.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name')
        ).order_by('id')

        if name_filter:
            users = users.filter(full_name__unaccent__icontains=name_filter)

        processed = set()
        for u1 in users:
            if u1.id in processed:
                continue
            processed.add(u1.id)

            matches = User.objects.exclude(id__in=processed).annotate(
                full_name=Concat('first_name', Value(' '), 'last_name'),
                similarity=TrigramSimilarity('full_name', u1.full_name)
            ).filter(similarity__gt=threshold)

            for u2 in matches:
                self.stdout.write(self.style.WARNING(f"\nDUPLICATE FOUND ({u2.similarity:.2f})"))
                self.stdout.write(f"1) {describe_user(u1)}")
                self.stdout.write(f"2) {describe_user(u2)}")

                
                choice = input("Keep (1/2/Skip): ").strip()
                if choice == '1':
                    merge_users(u1, u2)
                    processed.add(u2.id)
                elif choice == '2':
                    merge_users(u2, u1)
                    break # u1 n'existe plus



def merge_users(keep_user, delete_user):
    with transaction.atomic():        

        # Gestion du OneToOne : FresnoyProfile
        merge_profiles(keep_user, delete_user)

        # Gestion des relations génériques (Artist, Staff, etc.)
        for rel in delete_user._meta.related_objects:
            # On ignore le profil car déjà traité manuellement
            if rel.get_accessor_name() == 'profile':
                continue
                
            accessor_name = rel.get_accessor_name()
            try:
                related_manager = getattr(delete_user, accessor_name)
                
                if rel.one_to_many:
                    related_manager.update(**{rel.field.name: keep_user})
                elif rel.many_to_many:
                    for item in related_manager.all():
                        getattr(keep_user, accessor_name).add(item)
                elif rel.one_to_one:
                    # Si c'est un autre OneToOne inconnu, on redirige si possible
                    if not hasattr(keep_user, accessor_name):
                        obj = related_manager
                        setattr(obj, rel.field.name, keep_user)
                        obj.save()
            except Exception:
                continue

        # Fusion des infos de base si vides chez le keep_user
        fields_to_check = ['first_name', 'last_name', 'email']
        updated = False
        for field in fields_to_check:
            if not getattr(keep_user, field) and getattr(delete_user, field):
                setattr(keep_user, field, getattr(delete_user, field))
                updated = True
        if updated:
            keep_user.save()

        # gestion des permissions
        keep_user.user_permissions.add(*delete_user.user_permissions.all())
        keep_user.groups.add(*delete_user.groups.all())

        # Suppression du compte en trop
        delete_user.delete()

    
def merge_profiles(keep_user, delete_user):
    if hasattr(delete_user, 'profile'):
        if not hasattr(keep_user, 'profile'):
            # Cas simple : on déplace le profil
            p = delete_user.profile
            p.user = keep_user
            p.save()
        else:
            # Cas complexe : les deux ont un profil
            p_keep = keep_user.profile
            p_delete = delete_user.profile
            
            updated = False
            for field in p_delete._meta.fields:
                if field.name not in ['id', 'user', 'user_id']:
                    val_keep = getattr(p_keep, field.name)
                    val_delete = getattr(p_delete, field.name)
                    
                    # Si le gagnant a un champ vide et que le perdant a une info
                    if val_keep in [None, ""] and val_delete not in [None, ""]:
                        setattr(p_keep, field.name, val_delete)
                        updated = True
            
            if updated:
                p_keep.save()
            
            # Maintenant on peut supprimer le profil en double en toute sécurité
            p_delete.delete()


def describe_user(user):
    email = user.email if user.email else ""

    profile = "Profile" if hasattr(user, 'profile') else ""

    staff_tasks = list(user.staff_set.all().exclude(productionstafftask__isnull=True).values_list('productionstafftask__task__label', flat=True))
    staff_info = f"Staff: {', '.join(staff_tasks)}" if staff_tasks else ""

    artist_info = "Artist" if user.artist_set.exists() else ""

    productions = list(user.artist_set.all().exclude(artworks__isnull=True).values_list('artworks__title', flat=True))
    productions_info = f"Productions: {', '.join(productions)}" if productions else ""

    return f"{user.first_name} {user.last_name} (ID: {user.id}) | {email} | {profile} | {staff_info} | {artist_info} | {productions_info}"
    