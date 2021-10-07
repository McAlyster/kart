# -*- encoding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.template.defaultfilters import slugify
from django.utils.crypto import get_random_string

######## IMPORTS
import os
import pathlib
import logging

from django.contrib.postgres.search import TrigramSimilarity

from django.db.models.functions import Concat, Lower
from django.db.models import CharField, Value, Q

import django
import sys
from django.conf import settings
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent.parent.absolute()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()


from django.contrib.auth.models import User
from people.models import FresnoyProfile, Staff, Artist
from production.models import Artwork

from utils.csv_utils import getUserByNames
from utils.correction import Correction

import requests

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

import matplotlib.image as mpimg
from io import BytesIO

##################

# Set file location as current working directory
OLD_CWD = os.getcwd()
curr_dir = pathlib.Path(__file__).absolute().parent

# Logging
# clear the logs
log_path = pathlib.Path(curr_dir/'duplicates.log').absolute()
open(log_path, 'w').close()

logger = logging.getLogger('duplicated_content')

# create file handler which logs even debug messages
fh = logging.FileHandler(log_path)
# create formatter and add it to the handlers
formatter1 = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter1)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter2 = logging.Formatter('%(message)s')
ch.setFormatter(formatter2)
# create formatter and add it to the handlers
# formatter1 = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fh.setFormatter(formatter1)
fh.setLevel(logging.DEBUG)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

# Global logger level
logger.setLevel(logging.CRITICAL)


def prompt_list(items=[], other=True, cancel=True, list_name="items_list", all_items=True) :
    """
    Ask the agent to choose an item in a list or to type a new item.

    Args :
        items (list)    : List of tuples or str to propose
        other (bool)    : Whether the 'other' option is available or not. Will ask the agent to type a new item (optional, default True)
        cancel (bool)   : Whether the 'cancel' option is available or not. (optional, default True)
        list_name (str) : Name of the list (optional)
        all_items (bool)      : Allow the user to select all items (except 'Skip' and 'other')

    Returns :
        The list of selected or typed item (tuple) or false (bool) if the 'cancel' option was choosen

    TODO :
        import inquirer

    """

    import inquirer

    # If no items, propose demo content
    if not items :
        items = [('item demo 1',0),('item demo 2',1),('item demo 3',334),('item demo 4',908),]

    # Check for only strings in items list
    if not all([type(item)==tuple for item in items]) and not all([type(item)==str for item in items]) :
        raise TypeError(f"Items must be tuples or strings.\n{items}")

    # Add other to the list
    if other :
        items += ['Other']

    # Add cancel to the list
    if all_items :
        items = ['All'] + items

    # Add cancel to the list
    if cancel :
        items += ['Skip']

    questions = [

      inquirer.Checkbox(list_name,
                        message="Which items represent the same content ? (press enter without selecting any item to skip)",
                        choices=items,
                        ),
    ]

    # Trigger the question and store answers
    answers = inquirer.prompt(questions)

    # Get rid of the dict structure for a more simple list
    answers = answers[list_name]

    # The "All" selection overrides any other selected items
    if "All" in answers :
        answers = [item[1] for item in items if item not in ['other','Skip','All']]
        print("all selected : ", answers)
        return answers



    # The "other" selection overrides any other selected items
    if "other" in answers :
        answers = ['other']

    # The "cancel" selection returns False
    if not answers or "Skip" in answers  :
        return False

    return answers

def show_user_picture(user_id, media_url="http://preprod.api.lefresnoy.net/media") :
    """
    Display (in current OS) the profile picture of the user with id `user_id`

    args:
        user_id (int)   : a Django user id
        media_url (str) : url of the media dir (optional)

    side effect :
        trigger the display of an image
    """

    # Try to get the FresnoyProfile from the user
    try :
        fp = FresnoyProfile.objects.get(user=user_id)
    except FresnoyProfile.DoesNotExist :
        logger.debug('User {us}')
        return

    if fp and fp.photo :
        photo_url = f"{media_url}/{fp.photo}"
        response = requests.get(photo_url)
        img = Image.open(BytesIO(response.content))
        img.show()


class Command(BaseCommand):
    """
    Find duplicated and ambigous content in People.

    Attributes:

    Methods
    -------
    handle():
        Main method, trigger the search for duplicated and ambigous content.

    """

    help = 'Find duplicates and ambigous entries'


    # Allow to lower data in query with '__lower'
    CharField.register_lookup(Lower)


    def add_arguments(self, parser):
        parser.add_argument('--dry',  action='store_true', help='Dry run. No modification is applied to the database.')
        # parser.add_argument('--debug',  action='store_true', help='Debug mode. Detailed logs')
        parser.add_argument('--pictures',  action='store_true', default=False, dest='display_pictures', help='If True, display pictures of potential similar people.')
        parser.add_argument('--no-prompt',  action='store_true', default=False, help='Disable user prompts (for debug purposes in Atom)')


    def handle(self, *args, **options):

        logger.debug(f"Duplicates called. \n*args : {args}, \n**args:{options}")
        logger.debug("-----------------")

        # Get all users first and last names
        all_users = User.objects.annotate(
            # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
            # name but can be stored as "Hee  -- Won Lee"
            search_name=Concat('first_name__unaccent__lower',
                               Value(' '), 'last_name__unaccent__lower')
        )

        # store the already processed users
        processed_ids = []

        # store the similar (potentialy duplicated content)
        simi_content = []

        # For each user, look for similar occurence in db
        for user in all_users :

            # Init the list of potentially similar users
            simi_users = [user]

            # Avoid double check if a user was already checked
            if user.id in processed_ids :
                continue

            # Get the user fullname
            fullname = user.search_name

            # Log current user
            logger.debug(f"Checking {fullname} ...")

            # First filter by first and lastname similarity
            guessArtLN = User.objects.annotate(
                # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
                # name but can be stored as "Hee  -- Won Lee"
                search_name=Concat('first_name__unaccent__lower',
                                   Value(' '), 'last_name__unaccent__lower')
            ).annotate(
                similarity=TrigramSimilarity('search_name', str(fullname))
            ).filter(
                similarity__gt=0.8
            ).order_by('-similarity')

            # If similar users found..
            if len(guessArtLN)>1 :
                # .. add and log them
                for user_simi in guessArtLN :
                    logger.info(f"\tpotential duplicate {user_simi}, {user_simi.id}")
                    # print(f"\tpotential duplicate {user_simi}, {user_simi.id}")
                    processed_ids += [user_simi.id]
                    # Add the similar user to the list of similar users for further treatment
                    if user_simi not in simi_users :
                        simi_users += [user_simi]



            ###
            # Search for less similar occurences (not added to processed so they can be represented in the algo)
            ###
            guessArtLN2 = User.objects.annotate(
                # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
                # name but can be stored as "Hee  -- Won Lee"
                search_name=Concat('first_name__unaccent__lower',
                                   Value(' '), 'last_name__unaccent__lower')
            ).annotate(
                similarity=TrigramSimilarity('search_name', str(fullname)),
            ).filter(
                Q(similarity__gt=0.5,
                similarity__lt=0.8)
            ).order_by('-similarity')

            # If results
            if len(guessArtLN2)>1 :
                for user_simi2 in guessArtLN2 :
                    logger.info(f"\tLess likely potential duplicate {user_simi2}, {user_simi2.id}")
                    # print(f"\tLess likely potential duplicate {user_simi2}, {user_simi2.id}")
                    # Add the similar user to the list of similar users
                    simi_users += [user_simi2]

            # Add the simi_users list to the main similar content if more than one sim user found (and prompt is permitted)
            if len(simi_users) > 1 and not options['no_prompt']:
                simi_content += [simi_users]

                # Ask human agent to regroup similar content
                if options['display_pictures'] :
                    for us in simi_users :
                        show_user_picture(us.id)

                # Prompt a list of tuples for user to validated similar content from algo cues
                identic_entities = prompt_list([(f"{user.first_name} {user.last_name} ({user.id})",user.id) for user in (simi_users)], other=False)

                if not identic_entities :
                    logger.info('No similar content confirmed.')
                    continue
                else :
                    # print(f"identical : {identic_entities}")
                    # Keep only ids (int)
                    identic_entities = [id for id in identic_entities if isinstance(id, int)]
                    # print("only ids ",identic_entities)

                # Related artworks
                rel_aws = []
                for user_id in identic_entities :
                    # Get all related artworks
                    artist = Artist.objects.filter(user=user_id)
                    # print("Artist", artist)
                    if artist :
                        logger.info(f'Related artist : {artist}')
                        # Get the artworks bu this artist
                        aws = Artwork.objects.prefetch_related('authors__user').filter(authors__in=artist)
                        if aws :
                            for aw in aws :
                                rel_aws += [aw]

                        else :
                            # print("No artwork")
                            pass
                if rel_aws :
                    print("Related artworks : ")
                    for aw in rel_aws :
                        print(aw)
            ##########

        # Simi content holds all potentialy duplicated content in a list of lists [[user_1,user48..], [user34,user983],...]

        # We want to define if the spotted similar user are actually the same user -> ask human agent
        # First : define and group the contents that are related to the same entity
        validated_duplicated_users = []

        # Second : define which is the correct value for each of the similar fields
        print("simi_content",simi_content)



if __name__ == "__main__" :
    os.system("pwd")
    os.system("/Users/ocapra/Desktop/PROJECTS/KART/kart/manage.py duplicates --no-prompt")
    # items = prompt_list()
    # print("ITEMS :", items)
    pass
