#! /usr/bin/env python
# -*- coding=utf8 -*-

import os, sys
from difflib import SequenceMatcher
# import matplotlib.pyplot as plt
import pathlib
import logging
import pandas as pd
import pytz
from datetime import datetime
from django.db.utils import IntegrityError
from django_countries import countries
from django.db.models.functions import Concat, Lower
from django.db.models import CharField, Value
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

import warnings
import re
import unidecode

# # Shell Plus Django Imports (uncomment to use script in standalone mode, recomment before flake8)
import django

# Name of the app
APP_NAME = 'kart'

# Add root to python path for standalone running
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent.parent.parent.absolute()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{APP_NAME}.settings")
django.setup()
# Load user model
from django.contrib.auth.models import User

# Import our models
from production.models import Artwork, Event
from people.models import Artist
from diffusion.models import Award, MetaAward, Place
from school.models import Student

from utils.kart_tools import *


# Full width print of dataframe
pd.set_option('display.expand_frame_repr', False)

# TODO: Harmonise created and read files (merge.csv, ...)
dry_run = True  # No save() if True
DEBUG = True

# Set file location as current working directory
OLD_CWD = os.getcwd()
os.chdir(pathlib.Path(__file__).parent.absolute())


# Allow to lower data in query with '__lower'
CharField.register_lookup(Lower)

# Logging
tools_logger = logging.getLogger('tools')
tools_logger.setLevel(logging.DEBUG)
# clear the logs
open('awards.log', 'w').close()
# create file handler which logs even debug messages
fh = logging.FileHandler('awards.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter1 = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter1)
formatter2 = logging.Formatter('%(message)s')
ch.setFormatter(formatter2)
# add the handlers to the tools_logger
tools_logger.addHandler(fh)
tools_logger.addHandler(ch)
#####

# Timezone
tz = pytz.timezone('Europe/Paris')

# Clear terminal
os.system('clear')


# def testAwardsProcess():
#     """Stats stuff about the awards
#
#     Dummy code to get familiar with Kart"""
#     # ========= Stacked data: awards by events type ... ==============
#     import matplotlib.colors as mcolors
#     mcol = mcolors.CSS4_COLORS
#     mcol = list(mcol.values())
#     # mixing the colors with suficent gap to avoid too close colors
#     colss = [mcol[x+12] for x in range(len(mcol)-12) if x % 5 == 0]
#     # by type of event
#     awards.groupby(['event_year', 'event_type']).size(
#     ).unstack().plot(kind='bar', stacked=True, color=colss)
#     plt.show()
#
#
# def testArtworks():
#     """Get authors with artwork id
#
#     Dummy code to get familiar with Kart"""
#     # Get the data from csv
#     awards = pd.read_csv('awards.csv')
#     # Strip all data
#     awards = awards.applymap(lambda x: x.strip() if isinstance(x, str) else x)
#
#     # replace NA/Nan by 0
#     awards.artwork_id.fillna(0, inplace=True)
#
#     # Convert ids to int
#     awards.artwork_id = awards['artwork_id'].astype(int)
#
#     for id in awards.artwork_id:
#         # id must exist (!=0)@
#         if not id:
#             continue
#         prod = Production.objects.get(pk=id)
#         tools_logger.info(prod.artwork.authors)




# Events


search_cache = {}




def infoCSVeventTitles():
    """Display info about potentialy existing events in Kart

    Check if event names exist with a different case in Kart and display warning
    """
    eventsToCreate = pd.read_csv('./tmp/events_title.csv')

    for evt_title in eventsToCreate.NomFichier:
        # If a title already exist with different case
        exact = Event.objects.filter(title__iexact=evt_title)
        if exact:
            tools_logger.warning(
                f"Event already exist with same name (but not same case) for {evt_title}:\n{exact}\n")

        # If a title already contains with different case
        contains = Event.objects.filter(title__icontains=evt_title)
        if contains:
            tools_logger.warning(
                f"Event already exist with very approaching name (but not same case) for {evt_title}:\n{contains}\n")


def createEvents(dry_run=False, DEBUG=True):

    """ Create (in Kart) the events listed in awards csv file

    1) Retrieve the data about the events listed in awards csv file
    2) Parse those data and prepare if for Event creation
    3) (optional) Check if meta event exits for the created event, creates it if needed
    """


    # DRY RUN mention
    dry_mention = "(dry run)" if dry_run else ""

    if not dry_run :
        atomic_context = atomic()
    else:
        atomic_context = rollback_atomic()


    # Get the events from awards csv extended with title cleaning (merge.csv)
    events = pd.read_csv('./tmp/merge.csv')

    # Create/get the events in Kart
    for ind, event in events.iterrows():
        title = event.NomDefinitif
        print("TITLE :",title)
        # Starting dates are used only for the year info (default 01.01.XXX)
        starting_date = event.event_year
        # Convert the year to date
        starting_date = datetime.strptime(str(starting_date), '%Y')
        starting_date = pytz.timezone('Europe/Paris').localize(starting_date)

        # All events are associated with type festival
        # TODO: Add other choices to event ? Delete choices constraint ?
        type = "FEST"

        # If no title is defined, skip the event
        if str(title) in ["nan", ""]:
            warnings.warn(f"Create event : no title provided - skipping event...")
            continue

        # Check if meta event exists, if not, creates it
        evt = Event.objects.filter(
            title=title,
            type=type,
            main_event=True
        )
        # If event already exist
        if len(evt):
            # Arbitrarily use the first event of the queryset (may contain more than 1)
            # TODO: what if more than one ?
            evt = evt[0]
            created = False
        else:
            # Create the main event
            evt = Event(
                title=title,
                # default date to 1st jan 70, should be replaced by the oldest edition
                starting_date=datetime.strptime("01-01-70", "%d-%m-%y").date(),
                type=type,
                main_event=True
            )
            evt.save(dry_run=False)
            created = True

        if created:
            tools_logger.info(f"META {title} was created ! {dry_mention}")
        else:
            tools_logger.info(f"META {title} was already in Kart !")

        # Check if event exists, if not, creates it
        evt = Event.objects.filter(
            title=title,
            type=type,
            # just use the starting date for now
            # TODO: events with more details
            starting_date=starting_date
        )



        if len(evt):
            # Arbitrarily use the first event of the queryset
            evt = evt[0]
            created = False
        else:
            tools_logger.info("obj is getting created")
            evt = Event(
                title=title,
                type=type,
                starting_date=starting_date
            )
            if not dry_run:
                evt.save()
            created = True


        if created:
            tools_logger.info(f"{title} was created {dry_mention}")
        else:
            tools_logger.info(f"{title} was already in Kart")
        # Store the ids of newly created/already existing events in a csv
        events.loc[ind, 'event_id'] = evt.id
    events.to_csv('./tmp/events.csv', index=False)


def getISOname(countryName=None, simili=False):
    """Return the ISO3166 international value of `countryName`

    Parameters:
    - countryName  : (str) The name of a country
    - simili         : (bool) If True (default:False), use similarity to compare the names
    """
    # Process the US case (happens often!)
    if re.search('[EeéÉ]tats[ ]?-?[ ]?[Uu]nis', countryName):
        return "US"
    # Kosovo is not liste in django countries (2020)
    if re.search('kosovo', countryName, re.IGNORECASE):
        return 'XK'

    # General case
    if not simili:
        for code, name in list(countries):
            if name == countryName:
                return code
        return False
    else:
        # The dic holding the matches
        matchCodes = []
        for code, name in list(countries):
            dist = SequenceMatcher(None, str(countryName).lower(), name.lower()).ratio()
            # tools_logger.info(f"DIST between {countryName} (unknown) and {name}: {dist}")
            if dist >= .95:
                matchCodes.append({'dist': dist, 'code': code})  # 1 ponctuation diff leads to .88
            if dist >= .85:
                cn1 = unidecode.unidecode(str(countryName))
                cn2 = unidecode.unidecode(name)
                dist2 = SequenceMatcher(None, cn1.lower(), cn2.lower()).ratio()
                if dist2 > dist:
                    tools_logger.info(
                        f"""------------------- ACCENTUATION DIFF {countryName} vs {name}\n
                        Accents removed: {cn1} vs {cn2}: {dist2}""")
                    # 1 ponctuation diff leads to .88
                    matchCodes.append({'dist': dist2, 'code': code})
                else:
                    if DEBUG:
                        return code
                    cont = input(f"""
                                 NOT FOUND but {countryName} has a close match with {name}
                                 Should I keep it ? (Y/n):   """)
                    if re.search("NO?", cont, re.IGNORECASE):
                        continue
                    else:
                        return code

    # Sort the matches by similarity
    sorted(matchCodes, key=lambda i: i['dist'])
    try:
        # Return the code with the highest score
        return matchCodes[0]['code']
    except IndexError:
        return False





def associateEventsPlaces(dry_run=False, DEBUG=True):
    """Fill the place field of created events with the created places

    """
    # Ignore association in dry mode
    if dry_run : return
    # Get the events and places csv
    evt_places = pd.read_csv("./tmp/merge_events_places.csv")

    # Update the events with the place
    for ind, award in evt_places.iterrows():

        # Retrieve the event id
        event_id = int(award.event_id) if not dry_run else 9999

        if str(award.place_id) != "nan":
            try:  # some events have no places specified
                place_id = int(award.place_id)
                evt = Event.objects.get(pk=event_id)
                evt.place_id = place_id
                # evt.save(dry_run=dry_run)
                evt.save()
                tools_logger.info(evt)
            except ValueError as ve:
                tools_logger.info("ve", ve, "award.place_id", award.place_id)





        # print("CPT", cpt)

# Fonctions à lancer dans l'ordre chronologique
# WARNING: eventCleaning and artworkCleaning should not be used !! (Natalia, head of diffusion, already
# validated diffusion/utils/import_awards/events_title.csv and diffusion/utils/import_awards/artworks_artists.csv)

# WARNING: this function requires a human validation and overrides `events_title.csv` & `merge.csv`
# eventCleaning()
# WARNING: this function requires a human validation and overrides `artworks_title.csv` & `merge.csv`
# artworkCleaning()

# tools_logger.setLevel(logging.CRITICAL)
# dry_run = True
# #
# # # createEvents()
# # # createPlaces()
# # # associateEventsPlaces()
# createAwards()
# #
#
# art = getArtistByNames(firstname="Daphné", lastname="Hérétakis", pseudo=None, listing=False)
# print('\n')
# print(art['artist'].id)

from django.apps import apps


def custom_formatwarning(msg, *args, **kwargs):
    # ignore everything except the message
    return f"...{args[1][-50:]} line {args[2]} - warning : {str(msg)} \n"


warnings.formatwarning = custom_formatwarning

def summary(restrict=None) :
    """ Return general description and statistics about the current database

        Params
        restrict(list): List of models that will be considered in the summary. If empty (default), all models are included.
    """

    # Get the all the current models
    mods = apps.get_models()

    # Dict to hold summary data
    summary_d = {}

    # Iterate through models ...
    for m in mods :
        # .. to populate the summary dict if models is in restrict list
        # or no restriction required
        if  (restrict and (m.__name__ in restrict)) or not restrict :
            summary_d[f"{m._meta.app_label}.{m.__name__}"] = m._default_manager.count()

    # Return the summary dict
    return summary_d


def compareSummaries(sum1=None, sum2=None, restrict=None, force_display=False) :
    """ Compare 2 summaries and expose counting differences

        params :
        - sum1(dict) : a summary generated by the summary function
        - sum2(dict) : a summary generated by the summary function
        - restrict(list) : list of models that will be compared
        - force_display(bool) : force the display of result even if no differences spotted

        Examples :
        # Ask for full summary
        sum1 = summary()
        # Restrict summary to some models
        # sum1 = summary(['Student','Diffusion'])
        sum2 = summary()
        compareSummaries(sum1)
    """

    if not sum1 or not sum2 or type(sum1) is not dict or type(sum2) is not dict :
        raise TypeError('compareSummaries requires 2 dict as arguments')

    sum1 = {key: value for key, value in sorted(sum1.items())}
    sum2 = {key: value for key, value in sorted(sum2.items())}

    # The dict holding counting differences
    diff_d = {}

    # fake a difference for debug purposes
    fakediff = force_display

    # Try to globally compare dictionnaries
    if sum1 == sum2 :
        warnings.warn(f"Summaries are identical.")
        # return

    # Iterate models and countings
    for k,v in sum1.items() :

        # If the model is not in both summaries, no comp is possible
        if not k in sum2.keys() :
            warnings.warn(f"Model {k} not in both summaries")
            continue

        # Diff btw before and after countings
        diff = sum2[k]-v

        # If diff and model is in the restricted list, show it
        if  fakediff or (diff and ( (restrict and (k in restrict and k in sum2.keys() )) or not restrict)):
            diff_d[k] = diff
            sign = "-" if diff < 0 else "+"
            print(f"{k} model count was {v}, is now {sum2[k]} ({sign} {diff})")

            # Retriving individual references
            model = apps.get_model(f"{k}")
            print(model.objects.values_list('pk'))

    return diff_d




# Ask for full summary
# sum1 = summary()
# # Restrict summary to some models
# # sum1 = summary(['Student','Diffusion'])
# sum2 = summary()
#
# compareSummaries(sum1)
