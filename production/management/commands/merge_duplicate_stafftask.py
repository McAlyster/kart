from django.contrib.postgres.search import TrigramSimilarity
from django.core.management.base import BaseCommand

# Pense à importer tes bons modèles
from production.models import StaffTask, ProductionStaffTask


def merge_tasks(keep, discard):
    """
    Fusionne la tâche 'discard' dans la tâche 'keep'.
    """
    # find ProductionStaffTask use deleteTask
    # transforme to the keep task
    ProductionStaffTask.objects.filter(task=discard).update(task=keep)

    # Plus rien ne pointe vers 'discard', on peut le supprimer
    discard.delete()


class Command(BaseCommand):
    help = 'Merge duplicate StaffTasks (labels)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.5,
            help='Seuil de similarité pour considérer deux tâches comme des doublons (entre 0 et 1, par défaut 0.5)'
        )
        parser.add_argument(
            '--label',
            type=str,
            help='Rechercher des doublons pour un label de tâche spécifique (ex: "Realisateur")',
            required=False
        )

    def handle(self, *args, **options):
        threshold = options['threshold'] or 0.5
        label_filter = options['label']

        # On requête directement les StaffTask
        tasks = StaffTask.objects.all()

        if label_filter:
            tasks = tasks.filter(label__unaccent__icontains=label_filter)

        processed = set()
        
        for t1 in tasks:
            if t1.id in processed:
                continue
            processed.add(t1.id)

            # On cherche les doublons dans le modèle StaffTask, en excluant ceux déjà traités
            matches = StaffTask.objects.exclude(id__in=processed).annotate(
                similarity=TrigramSimilarity('label', t1.label)
            ).filter(similarity__gt=threshold)

            for t2 in matches:
                self.stdout.write(self.style.WARNING(f"\nDUPLICATE FOUND ({t2.similarity:.2f})"))
                
                # On affiche juste les labels des tâches et le nombre de fois où elles sont utilisées
                count_t1 = ProductionStaffTask.objects.filter(task=t1).count()
                count_t2 = ProductionStaffTask.objects.filter(task=t2).count()
                
                self.stdout.write(f"1) {t1.label} (ID: {t1.id}) - Utilisé dans {count_t1} productions")
                self.stdout.write(f"2) {t2.label} (ID: {t2.id}) - Utilisé dans {count_t2} productions")

                choice = input("Keep (1/2/Skip): ").strip()
                if choice == '1':
                    merge_tasks(t1, t2)
                    processed.add(t2.id)
                elif choice == '2':
                    merge_tasks(t2, t1)
                    break # t1 a été supprimé, on sort de la boucle pour t1