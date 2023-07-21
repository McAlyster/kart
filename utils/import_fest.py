#!/usr/bin/env python
"""Import festivals from csv
19 may 2023
"""

"""
20 juillet : 
TODO create meta event if dont exist, create associated meta awards - DONE 
21 juillet : 
Quid des meta event ? A quoi servent ils sur le front ?

"""
import sys
import os
import copy
import time
import pathlib
import logging
import pandas as pd
import warnings
from pathlib import Path
import re
from difflib import SequenceMatcher
import functools

# Shell Plus Django Imports (uncomment to use script in standalone mode, recomment before flake8)
import django
from django.contrib.postgres.search import TrigramSimilarity

# from utils.kart_tools import *

from django.apps import apps

project_root = str(pathlib.Path(__file__).parent.parent.absolute())
sys.path.append(project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()

# from diffusion.management.commands.import_awards.tools import summary, compareSummariesimport
from production.models import Event, Artwork
from diffusion.models import Place, MetaAward, MetaEvent, Diffusion


# import tools TODO : refactor tools in utils 
sys.path.append(str(pathlib.Path(project_root, 'diffusion/management/commands/_import_awards').absolute()))
print(sys.path)
from tools import safeGet, processPlace

# Logging
global logger
logger = logging.getLogger('import_events')
logger.setLevel(logging.DEBUG)
# clear the logs
open('events.log', 'w').close()
# create file handler which logs even debug messages
fh = logging.FileHandler('awards.log')
fh.setLevel(logging.INFO)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter1 = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter1)
formatter2 = logging.Formatter('%(message)s')
ch.setFormatter(formatter2)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


def custom_formatwarning(msg, *args, **kwargs):
    # ignore everything except the message
    return f"...{args[1][-50:]} line {args[2]} - warning : {str(msg)} \n"


warnings.formatwarning = custom_formatwarning

# DRY RUN
DRY_RUN = True

# Decorator than check required data for object creation
def require(*args):

    def dec_require(func):

        @functools.wraps(func)
        def wrapper(adict):
            # Check if required info are provided
            REQUIRED = set(args)
            akeys = set(list(adict.keys()))
            if not REQUIRED.issubset(akeys):
                # raise IndexError('Required data missing')
                logger.critical(f'Required data missing : {" ".join([req for req in REQUIRED if req not in akeys])}')
                return
            func()
        return wrapper
    return dec_require


def summary(restrict=None):
    """ Return general description and statistics about the current database

        Params
        restrict(list): List of models that will be considered in the summary. If empty (default), all models
        are included.
    """

    # Get the all the current models
    mods = apps.get_models()

    # Dict to hold summary data
    summary_d = {}

    # Iterate through models ...
    for m in mods:
        # .. to populate the summary dict if models is in restrict list
        # or no restriction required
        # print("model", m)
        if (restrict and (m.__name__ in restrict)) or not restrict:
            summary_d[f"{m._meta.app_label}.{m.__name__}"] = m._default_manager.count()

    # Return the summary dict
    return summary_d


def compareSummaries(sum1=None, sum2=None, restrict=None, force_display=False):
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

    if not sum1 or not sum2 or type(sum1) is not dict or type(sum2) is not dict:
        raise TypeError('compareSummaries requires 2 dict as arguments')

    sum1 = {key: value for key, value in sorted(sum1.items())}
    sum2 = {key: value for key, value in sorted(sum2.items())}

    # The dict holding counting differences
    diff_d = {}

    # fake a difference for debug purposes
    fakediff = force_display

    # Try to globally compare dictionnaries
    if sum1 == sum2:
        warnings.warn("Summaries are identical.")
        # return

    # Iterate models and countings
    for k, v in sum1.items():

        # If the model is not in both summaries, no comp is possible
        if k not in sum2.keys():
            warnings.warn(f"Model {k} not in both summaries")
            continue

        # Diff btw before and after countings
        diff = sum2[k]-v

        # If diff and model is in the restricted list, show it
        if fakediff or (diff and ((restrict and (k in restrict and k in sum2.keys())) or not restrict)):
            diff_d[k] = diff
            sign = "-" if diff < 0 else "+"
            print(f"{k} model count was {v}, is now {sum2[k]} ({sign} {diff})")

            # Retriving individual references
            # model = apps.get_model(f"{k}")
            # print(model.objects.values_list('pk'))

    return diff_d


before = summary()
# print("before", before)


ASIA = "AS"
AFRICA = "AF"
ANTARTICA = "AN"
AUSTRALIA = "AU"
EUROPE = "EU"
NORTH_AMERICA = "NA"
SOUTH_AMERICA = "SA"
MIDDLE_EAST = 'ME'
OCEANIA = 'OC'


CONTINENTS = [
        (ASIA, "Asie"),
        (EUROPE, "Europe"),
        (AFRICA, "Afrique"),
        (NORTH_AMERICA, "Amérique du Nord"),
        (SOUTH_AMERICA, "Amérique du Sud"),
        (AUSTRALIA, "Australie"),
        (MIDDLE_EAST, "Moyen Orient"),
        (ANTARTICA, "Antarctique"),
        (OCEANIA, 'Océanie')
    ]



# Utils
def getContinent(name, index=True):
    """
    Return the most similar continent from a given name

    param :
        index: (bool) if true, return the index, the full name otherwise
    """

    #  Loop through continents and compute similarity score
    scores = [SequenceMatcher(None, cont[1], name).ratio() for cont in CONTINENTS]

    # Return the elemens with highest score
    ans = CONTINENTS[scores.index(max(scores))][0] if index else CONTINENTS[scores.index(max(scores))][1]

    # print(f"continent demandé : {name}, continent retourné : {ans}",)
    return ans


def importFestivals():
    # Load csv file
    csvpath = Path(pathlib.Path(__file__).parent, './fest_full_incorrect.csv')
    logger.debug(f"Loading CSV file to dataframe : {csvpath}")
    fest_df = pd.read_csv(csvpath)

    # Clean the columns name
    fest_df.columns = [col.strip() for col in fest_df.columns]
    logger.debug(f"fest_df : {fest_df.columns}")

    # fest_df = pd.read_csv(Path(pathlib.Path(__file__).parent , './fest_full_correct.csv'))
    # print(fest_df)

    # Rename columns (depending on the original csv file)
    if 'ID Event' in fest_df.columns:
        fest_df.rename(columns={'ID Event': 'id'}, inplace=True)
    if 'Refs Kart' in fest_df.columns:
        fest_df.rename(columns={'Refs Kart': 'id'}, inplace=True)

    # Parsing incorrect fest csv
    # get the artwork code
    patt = re.compile('.*code:(.*)$')

    logger.debug("------------ Looping through rows to detect events")

    for ind, data in fest_df.iterrows():

        # Current value e.g. InvidéO - Milan (IT) |code:1143
        id2parse = fest_df.iloc[ind]['id']

        if "code:" in str(id2parse):
            # Extract id e.g. 1143
            r = re.match(patt, id2parse)
            id = r.group(1)

            # Replace former value with new one
            fest_df.loc[ind, 'id'] = id
            logger.debug(f"id event extracted : {id} from \"{id2parse}\"")

    logger.debug("\n\n------------ Looping through events and check their presence in Kart")

    # For each row check if exists in db
    for ind, data in fest_df.iterrows():

        logger.debug(f"\n{data['ville']}")

        # Get the Kart id of the event
        id = data['id']

        # Retrieve the event in Kart
        try:
            ev = Event.objects.get(pk=id)
            logger.debug(f"\n{ev} retrieved")
        except Exception:
            logger.debug(f"Can't find the object with id {id}")
            continue

        # get the place from event
        place = ev.place

        # If no place associated wirth event
        if place is None:
            # Create new place instance
            place = Place()
            # Associate it to current event
            ev.place = place
            logger.debug(f"No place associated to {ev}. Creating one...")

        if not DRY_RUN:
            place.save()

        ####################
        # Cities are replaced with csv data
        ev.place.name = data['ville'].lower()
        logger.debug(f"Fill 'city' from csv : {ev.place.name}")

        # Lat and long come from Kart, because probably the most recent
        # print("same city ? ", ev.place.name.lower() == data['ville'].lower(), data['ville'].lower())
        # print("same lat ? ", float(ev.place.latitude) == float(data['lat']), ev.place.latitude ,data['lat'])
        # print("same lng ? ", float(ev.place.longitude) == float(data['lng']), ev.place.longitude ,data['lng'])
        #####################

        # Example of a row in csv (fest_full_incorrect.csv):
        # Refs Kart	Num	Type	Genre	nom	mois	site web	continent	pays	ville 	lat	lng	Modif
        #  Rencontres Internationales Paris/Berlin - Paris (FR) |code:1032	26	Festival	art contemporain	rencontres
        # internationales paris/berlin	3	www.art-action.org	europe	france	paris	48,859116	2,331839	MODIF GENRE

        # Get modification type
        logger.debug("Get the modif specified in csv ...")

        if 'Modif' in data.keys():
            # init
            modif_l = None

            modif = data['Modif']

            # get rid of "MODIF " string
            # e.g. "MODIF CONTINENT"
            if "MODIF " == modif[:6]:
                # e.g. CONTINENT
                modif = modif[6:]

            # In case of duplicate
            if modif.startswith("A SUPPRIMER - DOUBLON "):
                # Keep DOUBLON XXX
                modif = modif[14:]

            # modif can include plus sign e.g. GENRE + TITRE
            modif_l = modif.split('+')

            # remove lead/trail spaces
            modif_l = [m.strip() for m in modif_l]

            # loop on elements e.g. GENRE,TITRE
            for m in modif_l:

                logger.debug(f"Modif detected : {m}")

                if "DOUBLON" in m:
                    id = data['id']
                    # Info de la part de Danaé :
                    # id to delete from Kart : data['id']
                    # id to Keep : DOUBLON XXXXX
                    pat = r"DOUBLON (\d*)"
                    r = re.match(pat, m)
                    id2keep = r.group(1)

                    # Check if id2keep is different from id to delete
                    if id2keep == id:
                        # do nothing, it's not a true duplicate
                        logger.debug(f"**************** Do nothing, it's not a true duplicate {id2keep} VS {id}")
                        pass
                    else:
                        # Check where the id2del is referenced
                        id2del = id
                        print("id2del : ", id2del)
                        print("id2keep : ", id2keep)

                        # MetaAwards
                        try:
                            ma = MetaAward.objects.get(event_id=id2del)
                            mak = MetaAward.objects.get(event_id=id2keep)
                            logger.debug(f"MetaAwards del : {ma} keep : {mak}")
                        except Exception:
                            pass

                        # MetaEvent
                        try:
                            ma = MetaEvent.objects.get(event_id=id2del)
                            mak = MetaEvent.objects.get(event_id=id2keep)
                            logger.debug(f"MetaEvent del : {ma} keep : {mak}")
                        except Exception:
                            pass

                        # Diffusion
                        try:
                            ma = Diffusion.objects.get(event_id=id2del)
                            mak = Diffusion.objects.get(event_id=id2keep)
                            logger.debug(f"Diffusion del :{ma},keep : {mak}")
                        except Exception:
                            pass

                if 'TITRE' == m:
                    # Depending on csv files "TITRE" column may have different names ...
                    if 'Titre' in data.keys():
                        new_title = data['Titre']
                    # ...
                    if 'nom' in data.keys():
                        new_title = data['nom']

                    if not ev.title == new_title:
                        logger.debug(f"titre modifié '{ev.title}' devient  '{new_title}'")
                        ev.title = new_title

                if 'GENRE' == m:
                    logger.debug(f"Genre : {data['Genre']}")
                    if 'Genre' in data.keys():
                        new_subtype = data['Genre']
                        logger.debug(f"ev.subtype {ev.subtype} --- new_subtype : {new_subtype}")

                        if ev.subtype != new_subtype:
                            print('subtype modifié', ev.subtype, ' >> ', new_subtype)
                            ev.subtype = new_subtype
                            if not DRY_RUN:
                                ev.save()
                            else:
                                logger.debug(f"Dry run : {ev} (subtype) not saved")

                if 'CONTINENT' == m:
                    new_continent = getContinent(data['continent'], True)
                    if not place.continent == new_continent and place:
                        if not place.continent:
                            logger.debug("Continent non renseigné dans Kart")
                        logger.debug(f"Continent modifié '{place.continent}'  devient  '{new_continent}'")
                        place.continent = new_continent
                        if not DRY_RUN:
                            place.save()
                        else:
                            logger.debug(f"Dry run : {place} (place) not saved")

                if not DRY_RUN:
                    place.save()
                    logger.info(f"Place {place} saved")
                    ev.save()
                    logger.info(f"Event {ev} saved")
                else:
                    logger.debug(f"Dry run : {ev} not saved")


def getMetaAwardBy(label="", event=""):
    """Return a meta award from its label

    Params:
    label: (str) The label to find
    event: (Event) The referenced event in the meta award

    Return:
    if label and event provided : a matching metaward object or None if not found
    if only label or event provided : a list a matching Meta Awards
    """

    # The m-a matching the event
    # The m-a matching the label
    ma_event = ma_label = []

    if event:
        ma_event = MetaAward.objects.filter(event=event)
        if ma_event:
            print(f"Found Meta Awards matching {event} : {ma_event}")
        else :
            print(f"Could not find a meta award referencing that event : {event}")

    if label:
        logger.debug(f"label to find : {label}")

        label = f"\"{str(label).lower()}\""

        guessMetaward = MetaAward.objects.annotate(
            similarity=TrigramSimilarity('label', label),
        ).filter(
            similarity__gt=0.3
        ).order_by('-similarity')

        if guessMetaward:
            ma_label = [ma for ma in guessMetaward]
            print("--------------------", ma_label)

    if event and label:
        logger.debug("Identifying the meta award")
        ma_match = [ma for ma in ma_label if ma in ma_event]
        if ma_match:
            print("ma_match", ma_match)
            # constraint in MetaAward for event + label is UNIQUE
            return ma_match[0]
        else:
            # No m-a corresponding to the provided date
            return False

    if event and not label:
        return ma_event
    else:
        return ma_label



@require('meta_award')
def createAward(adict=None):
    """Create an award from the provided dict
    """
    pass


def importAwards2023():
    """Import awards from the 2023 Danaé CSV file.
    """

    # Load csv file
    csvpath = Path(pathlib.Path(__file__).parent, './awards_all_2023.csv')
    logger.debug(f"Loading CSV file to dataframe : {csvpath}")

    awards_df = pd.read_csv(csvpath, dtype={'event_ref': str, 'event_alternative': str})
    awards_df = awards_df.fillna("")

    # Clean the columns name
    awards_df.columns = [col.strip() for col in awards_df.columns]
    logger.debug(f"awards_df : {awards_df}")

    # Loop over the awards from csv
    for ind, award in awards_df.iterrows():

        # init
        event_to_create = ma_to_create = aw_to_create = None
        # Track the confirmed fields
        valid_aw = None

        # event_ref from csv
        meta_award_label = award.meta_award_label
        meta_award_label_details = award.meta_award_label_details
        event_ref = award.event_ref
        event_year = award.event_year
        # alternative name for event (event without code in csv --> should be created)
        event_alt = award.event_alternative
        event_type = award.event_type
        place_city = award.place_city
        place_country = award.place_country
        aw_ref = award.artwork_ref
        aw_alt = award.artwork_alternative
        comments = award.comments

        # get the event code from csv e.g. : "Ars Electronica - Linz (AT) |code:1100"
        patt = re.compile('.*code:(.*)$')

        # ARTWORK
        # If an artwrok with id is provided, get the id and look for the aw
        if aw_ref:
            # Extract id e.g. 1100
            r = re.match(patt, aw_ref)
            aw_id = int(r.group(1)) if r else None
            # Safe retrieve the event
            aw, filt = safeGet(Artwork, pk=aw_id)
            # Check the aw
            valid_aw = True
            print("aw : ", aw)
        elif aw_alt :
            logger.info(f"No aw with id in csv. Alternative title : {aw_alt}\
                        \ncomments : {comments}")
            logger.info(f"Skipping row {ind}\n")
            continue
        else:
            logger.critical(f"No artwork for row {ind}, skipping")

        if aw_to_create:
            print(f"Should create aw {event_to_create}")

        # PLACE
        place = processPlace(place_city, place_country, dry=DRY_RUN)
        if not place:
            print("No place", place)

        # EVENT
        # If an event with id is provided, get the id and look for the event
        if event_ref:
            # Extract id e.g. 1100
            r = re.match(patt, event_ref)
            event_id = int(r.group(1)) if r else None
            # Safe retrieve the event
            event, filt = safeGet(Event, pk=event_id)

            # If the event don't exist in kart, mark it for creation
            if not event:
                logger.critical(f"#### WARNING ##### Can't find the referenced event from csv {event_ref} in Kart")
                logger.critical(f"Skipping row {ind}")
                continue

            else:
                # Check if meta award exists
                m_a = getMetaAwardBy(label=meta_award_label, event=event_id)

                if not m_a:
                    logger.info(f"The event {event} exists but no Meta Award with this event and this label exist in Kart")
                    ma_to_create = {'event': event}

        # if no event with id provided, use the alternative
        else:
           
            if not event_alt:
                logger.info(f"No alternative event provided, skipping the csv row {ind}...")
                continue
            event_to_create = {'title':event_alt}
            logger.info(f"No event with id in csv, using the alternative : {event_alt}")

        if ma_to_create:
            createAward(ma_to_create)

        if event_to_create:
            print(f"Should create event {event_to_create}")

        ######################
        # Create an award

        print("\n")
        # end of loop through csv row

        # Check if main event exists
        # print(award.meta_award_label)

        # Task metaaward non précisé par défaut (TODO DIFF)
        # category réal si film qq part dans la row



# importFestivals()
importAwards2023()
after = summary()
comp = compareSummaries(before, after)
print(comp)
