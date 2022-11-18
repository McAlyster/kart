from django.core.management.base import BaseCommand
from ._import_awards.tools import summary, compareSummaries, createEvents, associateEventsPlaces
from utils.places_utils import createPlaces
from utils.diffusion_utils import createAwards


CREATED_CONTENT = []


class Command(BaseCommand):
    help = 'Import awards from CSV file -  ./manage.py import_awards'

    def handle(self, *args, **options):

        # Tracking of created contents
        global CREATED_CONTENT

        before  = summary()
        createEvents()
        # createPlaces()
        # associateEventsPlaces()
        # createAwards()
        after = summary()
        compareSummaries(before, after, force_display=False)

        self.stdout.write(self.style.SUCCESS('Successfully imported the awards !'))
