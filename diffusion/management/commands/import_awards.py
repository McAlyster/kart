from django.core.management.base import BaseCommand
from django.core.management.base import BaseCommand
from django.db.transaction import atomic

import argparse
from contextlib import contextmanager, closing
import csv
import pandas as pd
# from collections.abc import Generator
from typing import Generator, Any

from io import TextIOWrapper

from ._import_awards.tools import summary, compareSummaries, createEvents, associateEventsPlaces
from utils.places_utils import createPlaces
from utils.diffusion_utils import createAwards

CREATED_CONTENT = []


class Command(BaseCommand):
    help = 'Import awards from CSV file -  ./manage.py import_awards'

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--write",
            action="store_true",
            default=False,
            help="Actually edit the database",
        )
        parser.add_argument("--file", type=argparse.FileType(), default="./tmp/merge.csv", required=False)


    def handle(self, *args: Any,  file: TextIOWrapper, write: bool, **options):

        # Tracking of created contents
        global CREATED_CONTENT

        # Dry mode (from https://adamj.eu/tech/2022/10/13/dry-run-mode-for-data-imports-in-django/)
        if write:
            atomic_context = atomic()
        else:
            atomic_context = rollback_atomic()

        # file = './tmp/merge.csv'
        # events = pd.read_csv(file)
        # print(f'events {events}')
        with closing(file), atomic_context:
            csvfile = csv.reader(file)
            header = next(csvfile)
            print(header)



        before  = summary()
        createEvents()
        createPlaces()
        associateEventsPlaces()
        createAwards()
        after = summary()
        compareSummaries(before, after, force_display=False)

        self.stdout.write(self.style.SUCCESS('Successfully imported the awards !'))




class DoRollback(Exception):
    pass



@contextmanager
def rollback_atomic() -> Generator[None, None, None]:
    try:
        with atomic():
            yield
            raise DoRollback()
    except DoRollback:
        pass
