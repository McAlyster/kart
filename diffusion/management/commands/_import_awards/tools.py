#! /usr/bin/env python
# -*- coding=utf8 -*-

import os
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

import re
import unidecode

# # Shell Plus Django Imports (uncomment to use script in standalone mode, recomment before flake8)
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()

# Load user model
from django.contrib.auth.models import User

# Import our models
from production.models import Artwork, Event
from people.models import Artist
from diffusion.models import Award, MetaAward, Place
from school.models import Student


# Full width print of dataframe
pd.set_option('display.expand_frame_repr', False)


# TODO: Harmonise created and read files (merge.csv, ...)
DRY_RUN = False  # No save() if True
DEBUG = True

# Set file location as current working directory
OLD_CWD = os.getcwd()
os.chdir(pathlib.Path(__file__).parent.absolute())


# Allow to lower data in query with '__lower'
CharField.register_lookup(Lower)

# Logging
logger = logging.getLogger('import_awards')
logger.setLevel(logging.DEBUG)
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
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)
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
#         logger.info(prod.artwork.authors)


def dist2(item1, item2):
    """Return the distance between the 2 strings"""
    if not type(item1) == type(item2) == str:
        raise TypeError("Parameters should be str.")
    return round(SequenceMatcher(None, item1.lower(), item2.lower()).ratio(), 2)


# Events








search_cache = {}


def getArtistByNames(firstname="", lastname="", pseudo="", listing=False):  # TODO pseudo
    """Retrieve the closest artist from the first and last names given

    Parameters:
    - firstname: (str) Firstname to look for
    - lastname : (str) Lastname to look for
    - pseudo   : (str) Pseudo to look for
    - listing  : (bool) If True, return a list of matching artists (Default, return the closest)

    Return:
    - artistObj    : (Django obj / bool) The closest artist object found in Kart. False if no match.
    - dist         : (float) Distance with the given names
    """

    # If no lastname no pseudo
    if not any([lastname, pseudo]):
        logger.info(
            f"\n** getArtistByNames **\nAt least a lastname or a pseudo is required.\nAborting research. {firstname}")
        return False

    # If data not string
    # print([x for x in [firstname,lastname,pseudo]])
    if not all([type(x) == str for x in [firstname, lastname, pseudo]]):
        logger.info(
            "\n** getArtistByNames **\nfirstname,lastname,pseudo must be strings")
        return False

    # List of artists that could match
    art_l = []

    # Clean names from accents to
    if lastname:
        # lastname_accent = lastname
        lastname = unidecode.unidecode(lastname).lower()
    if firstname:
        # firstname_accent = firstname
        firstname = unidecode.unidecode(firstname).lower()
    if pseudo:
        # pseudo_accent = pseudo
        pseudo = unidecode.unidecode(pseudo).lower()
    fullname = f"{firstname} {lastname}"

    # Cache
    fullkey = f'{firstname} {lastname} {pseudo}'
    try:
        # logger.warning("cache", search_cache[fullkey])
        return search_cache[fullkey] if listing else search_cache[fullkey][0]
    except KeyError:
        pass

    # SEARCH WITH LASTNAME then FIRSTNAME
    # First filter by lastname similarity
    guessArtLN = Artist.objects.prefetch_related('user'
                                                 ).annotate(
        # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
        # name but can be stored as "Hee  -- Won Lee"
        search_name=Concat('user__first_name__unaccent__lower',
                           Value(' '), 'user__last_name__unaccent__lower')
    ).annotate(
        similarity=TrigramSimilarity('search_name', fullname),
    ).filter(
        similarity__gt=0.3
    ).order_by('-similarity')

    # Refine results
    if guessArtLN:
        # TODO: Optimize by checking a same artist does not get tested several times
        for artist_kart in guessArtLN:

            # Clear accents (store a version with accents for further accents issue detection)
            kart_lastname_accent = artist_kart.user.last_name
            kart_lastname = unidecode.unidecode(kart_lastname_accent).lower()
            kart_firstname_accent = artist_kart.user.first_name
            kart_firstname = unidecode.unidecode(kart_firstname_accent).lower()
            # kart_fullname_accent = artist_kart.search_name
            kart_fullname = f"{kart_firstname} {kart_lastname}".lower()

            dist_full = dist2(kart_fullname, fullname)

            # logger.warning('match ',kart_fullname , dist2(kart_fullname,fullname), fullname,kart_fullname == fullname)
            # In case of perfect match ...
            if dist_full > .9:
                if kart_fullname == fullname:
                    # store the artist in potential matches with extreme probability (2)
                    # and continue with next candidate
                    art_l.append({"artist": artist_kart, 'dist': 2})
                    continue
                # Check if Kart and candidate names are exactly the same
                elif kart_lastname != lastname or kart_firstname != firstname:

                    logger.warning(f"""Fullnames globally match {fullname} but not in first and last name correspondences:
                    Kart       first: {kart_firstname} last: {kart_lastname}
                    candidate  first: {firstname} last: {lastname}
                                            """)
                    art_l.append({"artist": artist_kart, 'dist': dist_full*2})
                    # ### Control for accents TODO still necessary ?
                    #
                    # accent_diff = kart_lastname_accent != lastname_accent or \
                    #               kart_firstname_accent != firstname_accent
                    # if accent_diff: logger.warning(f"""\
                    #                 Accent or space problem ?
                    #                 Kart: {kart_firstname_accent} {kart_lastname_accent}
                    #                 Candidate: {firstname_accent} {lastname_accent} """)
                    continue

            # Control for blank spaces

            if kart_lastname.find(" ") >= 0 or lastname.find(" ") >= 0:
                # Check distance btw lastnames without spaces
                if dist2(kart_lastname.replace(" ", ""), lastname.replace(" ", "")) < .9:
                    bef = f"\"{kart_lastname}\" <> \"{lastname}\""
                    logger.warning(f"whitespace problem ? {bef}")

            if kart_firstname.find(" ") >= 0 or firstname.find(" ") >= 0:
                # Check distance btw firstnames without spaces
                if dist2(kart_firstname.replace(" ", ""), firstname.replace(" ", "")) < .9:
                    bef = f"\"{kart_firstname}\" <> \"{firstname}\""
                    logger.warning(f"whitespace problem ? {bef}")
            ###

            # Artists whose lastname is the candidate's with similar firstname

            # Distance btw the lastnames
            dist_lastname = dist2(kart_lastname, lastname)

            # try to find by similarity with firstname
            guessArtFN = Artist.objects.prefetch_related('user').annotate(
                similarity=TrigramSimilarity('user__first_name__unaccent', firstname),
            ).filter(user__last_name=lastname, similarity__gt=0.8).order_by('-similarity')

            # if artist whose lastname is the candidate's with similar firstname names are found
            if guessArtFN:

                # Check artists with same lastname than candidate and approaching firstname
                for artistfn_kart in guessArtFN:
                    kart_firstname = unidecode.unidecode(artistfn_kart.user.first_name)
                    # Dist btw candidate firstname and a similar found in Kart
                    dist_firstname = dist2(f"{kart_firstname}", f"{firstname}")
                    # Add the candidate in potential matches add sum the distances last and firstname
                    art_l.append({"artist": artistfn_kart, 'dist': dist_firstname+dist_lastname})

                    # Distance evaluation with both first and last name at the same time
                    dist_name = dist2(f"{kart_firstname} {kart_lastname}",
                                      f"{firstname} {lastname}")
                    # Add the candidate in potential matches add double the name_dist (to score on 2)
                    art_l.append({"artist": artistfn_kart, 'dist': dist_name*2})

            else:
                # If no close firstname found, store with the sole dist_lastname (unlikely candidate)
                art_l.append({"artist": artist_kart, 'dist': dist_lastname})

        # Take the highest distance score
        art_l.sort(key=lambda i: i['dist'], reverse=True)

        # Return all results if listing is true, return the max otherwise
        if listing:
            search_cache[fullkey] = art_l
            return art_l
        else:
            search_cache[fullkey] = [art_l[0]]
            return art_l[0]
    else:
        # research failed
        search_cache[fullkey] = False

        return False
    #####


def infoCSVeventTitles():
    """Display info about potentialy existing events in Kart

    Check if event names exist with a different case in Kart and display warning
    """
    eventsToCreate = pd.read_csv('./tmp/events_title.csv')

    for evt_title in eventsToCreate.NomFichier:
        # If a title already exist with different case
        exact = Event.objects.filter(title__iexact=evt_title)
        if exact:
            logger.warning(
                f"Event already exist with same name (but not same case) for {evt_title}:\n{exact}\n")

        # If a title already contains with different case
        contains = Event.objects.filter(title__icontains=evt_title)
        if contains:
            logger.warning(
                f"Event already exist with very approaching name (but not same case) for {evt_title}:\n{contains}\n")


def createEvents():
    """ Create (in Kart) the events listed in awards csv file

    1) Retrieve the data about the events listed in awards csv file
    2) Parse those data and prepare if for Event creation
    3) (optional) Check if meta event exits for the created event, creates it if needed
    """

    # Get the events from awards csv extended with title cleaning (merge.csv)
    events = pd.read_csv('./tmp/merge.csv')

    # Create/get the events in Kart
    for ind, event in events.iterrows():
        title = event.NomDefinitif
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
            if not DRY_RUN:
                evt.save()
            created = True

        if created:
            logger.info(f"META {title} was created")
        else:
            logger.info(f"META {title} was already in Kart")

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
            logger.info("obj is getting created")
            evt = Event(
                title=title,
                type=type,
                starting_date=starting_date
            )
            if not DRY_RUN:
                evt.save()
            created = True

        if created:
            logger.info(f"{title} was created")
        else:
            logger.info(f"{title} was already in Kart")
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
            # logger.info(f"DIST between {countryName} (unknown) and {name}: {dist}")
            if dist >= .95:
                matchCodes.append({'dist': dist, 'code': code})  # 1 ponctuation diff leads to .88
            if dist >= .85:
                cn1 = unidecode.unidecode(str(countryName))
                cn2 = unidecode.unidecode(name)
                dist2 = SequenceMatcher(None, cn1.lower(), cn2.lower()).ratio()
                if dist2 > dist:
                    logger.info(
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





def associateEventsPlaces():
    """Fill the place field of created events with the created places

    """

    # Get the events and places csv
    evt_places = pd.read_csv("./tmp/merge_events_places.csv")

    # Update the events with the place
    for ind, award in evt_places.iterrows():
        event_id = int(award.event_id)
        if str(award.place_id) != "nan":
            try:  # some events have no places specified
                place_id = int(award.place_id)
                evt = Event.objects.get(pk=event_id)
                evt.place_id = place_id
                if not DRY_RUN:
                    evt.save()
                logger.info(evt)
            except ValueError as ve:
                logger.info("ve", ve, "award.place_id", award.place_id)


def safeGet(obj_class=None, default_index=None, force=False, **args):
    """Try to `get`the object in Kart. If models.MultipleObjectsReturned error, return the first oject returned
        or the one in index `default_index`

    Parameters:
    - objClass     : (Django obj) The class on which to apply the get function
    - default      : (int) The index of the queryset to return in case of MultipleObjectsReturned error.
                      '0' is used in case of IndexError
    - args         : the arguments of the get query
    - force        : (bool) Force the return of the whole queryset rather than just one object - Default: False

    Return:
    - obj          : (Django obj or bool) a unique object of `obj_class`matching the **args,
                       False if `ObjectDoesNotExist` is raised
    - filtered     : a boolean indicating if the returned obj was unique or from a >1 queryset
    """

    try:
        obj = obj_class.objects.get(**args)
        return obj, False

    # If the object does not exist, return False
    except ObjectDoesNotExist:
        return False, False

    # If multiple entries for the query, fallback on filter
    except MultipleObjectsReturned:
        objs = obj_class.objects.filter(**args)
        logger.info(f"The request of {args}  returned multiple entries for the class {obj_class}")

        if default_index:
            try:
                return objs[default_index], True
            except ValueError:
                return objs[0], True
        else:
            # Return the first object of the queryset
            return objs[0], True


def objExistPlus(obj_class=None, default_index=None, **args):
    """Return a True if one or more objects with `**args` parameters exist

    Parameters:
    - objClass     : (DjangoObject) The class on which to apply the get function
    - default      : (int) The index of the queryset to return in case of MultipleObjectsReturned error.
                      '0' is used in case of IndexError
    - args         : the arguments of the get query

    Return:
    - exists       : (bool)
    - multiple     : (int) the amount of existing object
    """

    objs, filtered = safeGet(obj_class, force=True, **args)
    if objs:
        return True, len(objs)
    else:
        return False,


def objExist(obj_class=None, default_index=None, **args):
    """Return a True if one or more objects with `**args` parameters exist

    Parameters:
    - objClass     : (DjangoObject) The class on which to apply the get function
    - default      : (int) The index of the queryset to return in case of MultipleObjectsReturned error.
                      '0' is used in case of IndexError
    - args         : the arguments of the get query

    Return:
    - exists       : (bool)
    """

    objs, filtered = safeGet(obj_class, force=True, **args)
    if objs:
        return True
    else:
        return False


def createAwards():
    """Create the awards listed in csv in Kart

    """
    print("Create AWARDS")
    # Load the events associated to places and artworks (generated by createPlaces())
    awards = pd.read_csv("./tmp/merge_events_places.csv")

    # Load the artists and associated artworks (generated by artworkCleaning())
    authors = pd.read_csv("./tmp/artworks_artists.csv")

    # Merge all the data in a dataframe
    total_df = pd.merge(awards, authors, how='left')
    total_df["notes"] = ""
    total_df.fillna('', inplace=True)
    cpt = 0

    # Check if artist are ok (not fully controled before ...)
    # if no artist_id, search by name in db
    for id, row in total_df[total_df['artist_id'] == ''].iterrows():
        art = getArtistByNames(firstname=row['artist_firstname'], lastname=row['artist_lastname'], listing=False)
        # if there is a match
        # dist == 2 is the maximum score for artist matching
        if art and art['dist'] == 2:
            # the id is stored in df
            total_df.loc[id, "artist_id"] = art['artist'].id

    for ind, award in total_df.iterrows():
        # init
        artwork_id = artist = False

        label = award.meta_award_label
        event_id = int(award.event_id)

        # An artwork id is required to create the award
        if (award.artwork_id):
            artwork_id = int(award.artwork_id)
        else:
            logger.warning(f"No idartwork for {award.artwork_title}")
            continue

        if (award.artist_id):
            artist = Artist.objects.get(pk=int(award.artist_id))
        else:
            cpt += 1
            print("NO ID ARTIST ", label, event_id)

        # try:
        #     print("award.artist_id",int(award.artist_id))
        # except ValueError:
        #     print("------------------>", award.artist_id)
        note = award.meta_award_label_details

        description = award.meta_award_label_details
        if pd.isna(award.meta_award_label_details):
            description = ''

        # GET THE META-eventsToCreate
        # Retrieve the Kart title of the event
        event, filt = safeGet(Event, pk=event_id)
        mevent, filt = safeGet(Event, title=event.title, main_event=True)

        # GET OR CREATE THE META-AWARD
        # Check if award exists in Kart, otherwise creates it
        maward, filt = safeGet(MetaAward, label=f"{label}", event=mevent.id)

        if maward:
            logger.info(f"MetaAward {label} exist in Kart")
        else:
            maward = MetaAward(
                label=f"{label}",
                event=mevent,
                description=description,
                type="INDIVIDUAL"  # indivudal by default, no related info in csv
            )
            print(f"label {maward.label}, event {mevent}, description {description}")
            if not DRY_RUN:
                maward.save()
            logger.info(f"\"{maward}\" created ")

        # GET OR CREATE THE AWARDS
        new_aw, filt = safeGet(Award,
                               meta_award=maward.id,
                               artwork=artwork_id,
                               event=event.id,
                               # artists = artist_id
                               )
        logger.setLevel(logging.WARNING)
        if new_aw:
            logger.info(f"{new_aw} exist in Kart")
            try:
                new_aw.artist.add(artist.id)
            except IntegrityError:
                # logger.warning(f"Artist_id: {artist} caused an IntegrityError")
                pass
            except AttributeError:
                # logger.warning(f"Artist_id: {artist} caused an AttributeError")
                pass
            if not DRY_RUN:
                new_aw.save()
        else:
            new_aw = Award(
                meta_award=maward,
                event=event,
                date=event.starting_date,
                note=note
            )
            try:
                if not DRY_RUN:
                    new_aw.save()
                    new_aw.artwork.add(artwork_id)
                    new_aw.save()
                    print(f"{new_aw}  created")
            except ValueError:
                logger.warning(f"Artist_id: {artist} caused an IntegrityError")
                pass
        # print("CPT", cpt)

# Fonctions à lancer dans l'ordre chronologique
# WARNING: eventCleaning and artworkCleaning should not be used !! (Natalia, head of diffusion, already
# validated diffusion/utils/import_awards/events_title.csv and diffusion/utils/import_awards/artworks_artists.csv)

# WARNING: this function requires a human validation and overrides `events_title.csv` & `merge.csv`
# eventCleaning()
# WARNING: this function requires a human validation and overrides `artworks_title.csv` & `merge.csv`
# artworkCleaning()

# logger.setLevel(logging.CRITICAL)
# DRY_RUN = True
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


def summary():
    """ Return general description and statistics about the current database"""

    # all_users = User.objects.values()
    nb_users = len(User.objects.all())
    # Artists
    nb_artists = len(Artist.objects.all())
    # Students
    nb_students = len(Student.objects.all())

    # Events
    nb_events = len(Event.objects.all())
    # Awards
    nb_awards = len(Award.objects.all())

    logger.info(f"Django : {django.VERSION}")
    logger.info(f"USERS : {nb_users}")
    logger.info(f"STUDENTS : {nb_students}")
    logger.info(f"ARTISTS : {nb_artists}")
    logger.info(f"EVENTS : {nb_events}")
    logger.info(f"AWARDS : {nb_awards}")


# summary()
