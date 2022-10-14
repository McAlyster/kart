# -*- encoding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.template.defaultfilters import slugify
from django.utils.crypto import get_random_string

######## IMPORTS
import os
import time
from pathlib import Path
import logging

from django.contrib.postgres.search import TrigramSimilarity

from django.db.models.functions import Concat, Lower
from django.db.models import CharField, Value, Q

import django
import sys
from django.conf import settings
sys.path.append(str(Path(__file__).parent.parent.parent.parent.absolute()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()


from django.contrib.auth.models import User
from people.models import FresnoyProfile, Staff, Artist
from school.models import Student, StudentApplication
from production.models import Artwork

from utils.csv_utils import getUserByNames
from utils.correction import Correction

import requests

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

import urllib
from urllib.parse import urlparse

import matplotlib.image as mpimg
from io import BytesIO

import sqlite3

##################

# Set file location as current working directory
OLD_CWD = os.getcwd()
curr_dir = Path(__file__).absolute().parent
# Tmp directory
TMP_DIR = curr_dir/"tmp"
Path.mkdir(TMP_DIR,exist_ok=True)

# Logging
# clear the logs
log_path = Path(curr_dir/'duplicates.log').absolute()
open(log_path, 'w').close()
# Create the logger
logger = logging.getLogger('duplicated_content')

# create file handler which logs even debug messages
fh = logging.FileHandler(log_path)
# create formatter and add it to the handlers
formatter1 = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter1)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter2 = logging.Formatter('%(message)s')
ch.setFormatter(formatter2)
# create formatter and add it to the handlers
# formatter1 = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fh.setFormatter(formatter1)
fh.setLevel(logging.INFO)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

# Global logger level
# logger.setLevel(logging.INFO)


#####################
# Init of local database to store duplicates during process
DB_PATH = curr_dir/'local_db.db'
con = sqlite3.connect(Path(DB_PATH).absolute())
cur = con.cursor()

# Table for similar ids
simi_table = "similar_id"

def init_local_db() :
    # Create table
    cur.execute(f'''CREATE TABLE IF NOT EXISTS {simi_table} (id int, id_simi int, type str, validated bool,  UNIQUE(id,id_simi)) ''')



def prompt_list(items=[], other=True, skip=True, quit=True, list_name="items_list", all_items=True, message="") :
    """
    Ask the agent to choose an item in a list or to type a new item.

    Args :
        items (list)    : List of tuples or str to propose
        other (bool)    : Whether the 'other' option is available or not. Will ask the agent to type a new item (optional, default True)
        skip (bool)   : Whether the 'skip' option is available or not. (optional, default True)
        quit (bool)     : Whether the 'quit' option is available or not. (optional, default True)
        list_name (str) : Name of the list (optional)
        all_items (bool)      : Allow the user to select all items (except 'Skip' and 'other')

    Returns :
        The list of selected or typed item (tuple) or false (bool) if the 'skip' option was choosen

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

    # Init additonal items labels
    other_label = 'Other'
    all_label = 'All'
    skip_label = 'Skip / None (default)'
    quit_label = 'Quit'
    additional_items = [other_label, all_label, skip_label, quit_label]

    # Add other to the list
    if other :
        items += [other_label]

    # Add all to the list
    if all_items :
        items = [all_label] + items

    # Add skip to the list
    if skip :
        items = [skip_label] + items

    # Add quit
    if quit :
        items += [quit_label]

    questions = [

      inquirer.Checkbox(list_name,
                        message=message,
                        choices=items,
                        ),
    ]

    # Trigger the question and store answers
    answers = inquirer.prompt(questions)

    # Get rid of the dict structure for a more simple list
    answers = answers[list_name]

    # The "All" selection overrides any other selected items
    if "All" in answers :
        answers = [item[1] for item in items if item not in additional_items]
        print("all selected : ", answers)
        return answers


    # The "other" selection overrides any other selected items
    if "other" in answers :
        answers = ['other']

    # The "other" selection overrides any other selected items
    if "Quit" in answers :
        answers = ['quit']

    # The "cancel" selection returns False
    if not answers or "Skip" in answers  :
        return False

    return answers

def show_user_picture(user_id, media_url="http://preprod.api.lefresnoy.net/media", pic_name=None) :
    """
    Display (in current OS) the profile picture of the user with id `user_id`

    args:
        user_id (int)   : a Django user id
        media_url (str) : url of the media dir (optional)
        pic_name (str)  : the name under which the file is temporarily saved

    side effect :
        trigger the display of an image
    """

    # Try to get the FresnoyProfile from the user
    try :
        fp = FresnoyProfile.objects.get(user=user_id)
    except FresnoyProfile.DoesNotExist :
        logger.debug(f'User with id {user_id} does not have any profile.')
        return

    if fp and fp.photo :
        # Url of the picture
        photo_url = f"{media_url}/{fp.photo}"
        # Get the picture
        response = requests.get(photo_url)
        # Load image
        img = Image.open(BytesIO(response.content))

        # get the extension
        path = urlparse(photo_url).path
        ext = os.path.splitext(path)[1]
        # Concat filename
        pic_name = pic_name+ext
        # Store locally (tmp)
        tmp_file = Path(TMP_DIR/pic_name)
        img.save(tmp_file)

        # Display image
        if "posix" == os.name :
            os.system(f'open {tmp_file}')
        else :
            os.system(f'start {tmp_file}')


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
        parser.add_argument('-td','--track-duplicates',  action='store_true', default=False, help='Track similar content and propose to merge them.')

        # parser.add_argument('--debug',  action='store_true', help='Debug mode. Detailed logs')
        parser.add_argument('--pictures',  action='store_true', default=False, dest='display_pictures', help='If True, display pictures of potential similar people.')
        parser.add_argument('--no-prompt',  action='store_true', default=False, help='Disable user prompts (for debug purposes in Atom)')
        parser.add_argument('-l','--list-stored',  action='store_true', default=False, help='If True, display the stored similarities')
        parser.add_argument('-fc','--flush-cache',  action='store_true', default=False, help='Remove local db of similar ids')
        parser.add_argument('-dm','--debug-mode',  action='store_true', default=False, help='Switch to debug mode.')


    def handle(self, *args, **options) :

        init_local_db()

        logger.debug(f"Duplicates called. \n*args : {args}, \n**args:{options}")
        logger.debug("-----------------")

        # If list mode
        if options['list_stored'] :
            print("LIST ONLY")
            # Call dedicated function for similarities listing
            return get_stored_simi()

        # If flush mode
        if options['flush_cache'] :
            return drop_local_db(ask=True)

        # Debug mode
        if options['debug_mode'] :
            return debug()

        # If track duplicates mode
        if options['track_duplicates'] :
            pass
        else :
            raise TypeError('At least one argument is required.')

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

        validated_stored_simi = []

        total_users = len(all_users)
        cpt_users = 0

        # For each user, look for similar occurence in db
        for user in all_users :
            #
            cpt_users += 1
            # Clear the terminal window
            clearTerm()
            print(f"Tracking duplicates ... ({round(100*cpt_users/total_users)}%)")
            print("User : ",user)

            # Init the list of potentially similar users
            # simi_users = []
            simi_users = [user]


            # If user.id already processed, we continue
            if not is_ambigous(user.id) :
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
                print("\n\n")
                # .. add and log them
                for user_simi in guessArtLN :

                    # Do not process already stored similar id
                    # print(" user_simi.id in validated_stored_simi ", user_simi.id, validated_stored_simi,user_simi.id in validated_stored_simi )
                    if not is_ambigous(user_simi.id) :
                        continue


                    # Log potential duplicates
                    to_log = f"\t\tpotential duplicate {user_simi}, {user_simi.id}"

                    # Add the status of the user (JUST CANDIDATE, STUDENT or NONE of them)
                    if is_candidate(user=user) and not is_student(user=user) :
                        to_log += " - USER IS JUST A CANDIDATE"
                    else :
                        to_log += " - USER IS A STUDENT"
                    logger.info(to_log)

                    # Add the user id in the processed list
                    processed_ids += [user_simi.id]

                    # Add the similar user to the list of similar users for further treatment
                    # if not already stored
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

                    # Do not process already stored similar id
                    # print(" user_simi2.id in validated_stored_simi ", user_simi2.id, validated_stored_simi,user_simi2.id in validated_stored_simi )
                    if not is_ambigous(user_simi2.id) :
                        continue

                    # Log potential duplicates
                    to_log = f"\t\t Less likely potential duplicate {user_simi2}, {user_simi2.id}"

                    # Add the status of the user (JUST CANDIDATE, STUDENT or NONE of them)
                    if is_candidate(user=user) and not is_student(user=user) :
                        to_log += " - USER IS JUST A CANDIDATE"
                    else :
                        to_log += " - USER IS A STUDENT"
                    logger.info(to_log)

                    # Add the similar user to the list of similar users
                    simi_users += [user_simi2]

            # Add the simi_users list to the main similar content if more than one sim user found (and prompt is permitted)
            if len(simi_users) > 1 and not options['no_prompt']:
                simi_content += [simi_users]

                # Ask human agent to regroup similar content
                if options['display_pictures'] :
                    for us in simi_users :
                        show_user_picture(us.id, pic_name=urllib.parse.quote_plus(us.get_full_name()))

                # Clear term window
                clearTerm()

                # Prompt a list of tuples for user to validated similar content from algo cues
                print(f"**************************\n{user}\n**************************")

                print(f"Which items represent the same content than {user}? (press enter without selecting any item to skip)\n")
                message = f"{user} ({user.id} - {get_user_associated_models(user)}) "
                prompt_l = [(f"{user.first_name} {user.last_name} ({user.id} - {get_user_associated_models(user)})",user.id) for user in (simi_users[1:])]
                identic_entities = prompt_list(prompt_l, other=False, message=message)


                # if quit, quit the script
                if identic_entities and "quit" in identic_entities :
                    # break the loop anq quit the script
                    break

                # If no or one item is selected, continue
                elif not identic_entities :
                    logger.info('No similar content confirmed.')
                    continue

                # If several items are selected, store them as similar
                else :
                    # Keep only ids (int)
                    identic_entities = [user.id] + [id for id in identic_entities if isinstance(id, int)]


                # Related artworks
                rel_aws = []
                rel_artists = []
                for user_id in identic_entities :
                    # Get all related artworks
                    artists = Artist.objects.filter(user=user_id)
                    if artists :
                        rel_artists += artists
                        # Get the artworks bu this artist
                        try :
                            aws = False
                            aws = Artwork.objects.prefetch_related('authors__user').filter(authors__in=artists)
                        except TypeError as te :
                            print('TYPE ERROR',te)

                        if aws :
                            for aw in aws :
                                rel_aws += [aw]
                        else :
                            print(f"no artwork associated with {artists}")
                            pass


                print(f"Found {len(rel_artists)} distinct artist(s) for the similar user(s) {identic_entities}")

                if rel_aws :
                    print(f"and {len(rel_aws)} related artworks : ")
                    for aw in rel_aws :
                        print(aw)

                # Save identical ids in db
                # Insert a row of data
                for id_simi in identic_entities[1:] :
                    req = f"INSERT INTO {simi_table} VALUES ('{identic_entities[0]}','{id_simi}','user',{True})"
                    try :
                        cur.execute(req)
                    except sqlite3.IntegrityError :
                        print("Similarity already spotted !")


                time.sleep(5)
                # Save (commit) the changes
                con.commit()
            ##########

        # Simi content holds all potentialy duplicated content in a list of lists [[user_1,user48..], [user34,user983],...]

        # We want to define if the spotted similar user are actually the same user -> ask human agent
        # First : define and group the contents that are related to the same entity
        validated_duplicated_users = []

        # # Second : define which is the correct value for each of the similar fields
        # print("simi_content",simi_content)

        # We can also close the connection if we are done with it.
        # Just be sure any changes have been committed or they will be lost.
        con.close()


def is_student(user=None, artist=None) :
    """
            Return True if the user is a student (and not just a candidate that DID NOT pass the selection).

            Args :
                - artist (Artist)  : An Artist object
                - user (User)      : A User Object
            Return :
                - bool  : True if user or artist is/was a student, False otherwise
    """
    # Init
    stud = False

    # Check args
    if not (user or artist) :
        raise TypeError("Missing 1 required positional argument: 'artist' or 'user'")
    if user and artist :
        raise TypeError("one positional argument only : 'artist' or 'user'")


    # Check for TypeError
    if artist and type(artist) is not Artist :
        raise TypeError("The argument `artist` is not an Artist object")

    if user and type(user) is not User :
        raise TypeError("The argument `user` is not a User object")


    # Look for a Student through `artist`
    if artist :
        return bool(Student.objects.filter(artist=artist))

    # Look for a Student through `user`
    if user :
        return bool(Student.objects.filter(user=user))


# TODO is_artist



def is_candidate(user=None, artist=None) :
    """
        Return True if the user is a candidate (not necessarly a student).

        Args :
            - artist (Artist)  : An Artist object
            - user (User)      : A User Object
        Return :
            - bool  : True if user or artist is/was candidate, False otherwise
    """

    # Init
    stapp = False

    # Check args
    if not (user or artist) :
        raise TypeError("Missing 1 required positional argument: 'artist' or 'user'")
    if user and artist :
        raise TypeError("one positional argument only : 'artist' or 'user'")


    # Check for TypeError
    if artist and type(artist) is not Artist :
        raise TypeError("The argument `artist` is not an Artist object")

    if user and type(user) is not User :
        raise TypeError("The argument `user` is not a User object")

    if artist :
        # Look for a StudentApplication for `artist`
        stapp = StudentApplication.objects.filter(artist=artist)
    if user :
        try :
            # Get the artist from user and call os_candidate again
            return is_candidate(artist=Artist.objects.get(user=user))
        except Exception as ex :
            return False

    if stapp :
        return True
    else :
        return False

def is_candidate_only(user=None, artist=None) :
    """
        Return True if the user is ONLY a candidate (not selected as a student).

        Args :
            - artist (Artist)  : An Artist object
            - user (User)      : A User Object
        Return :
            - bool  : True if user or artist is/was candidate only, False otherwise
    """

    if user : return is_candidate(user=user) and not is_student(user=user)
    if artist : return is_candidate(artist=user) and not is_student(artist=user)




def is_staff(user=None) :
    """
            Return True if the user is associated to a staff object.

            Args :
                - user (User)      : A User Object
            Return :
                - bool  : True if user or artist is/was a student, False otherwise
    """
    # Init
    staff = False

    # Check args
    if not user :
        raise TypeError("Missing 1 required positional argument: 'user'")


    # Check for TypeError
    if user and type(user) is not User :
        raise TypeError("The argument `user` is not a User object")


    # Look for a Student through `user`
    if user :
        return bool(Staff.objects.filter(user=user))



def is_ambigous(id) :
    """
    Return True if id is not yet checked by human (not yet listed in local db).
    """

    # Check if user.id is already processed in local db
    req = f"SELECT * FROM {simi_table} WHERE id=? OR id_simi=?"
    res = cur.execute(req,(id,id))
    # Fetch results
    stored_simi = cur.fetchall()

    if stored_simi :
        return False
    else :
        return True

        # convert simi tuples to a list of ids of similar content
        # # print("stored_simi before",stored_simi) # stored_simi [(1376,), (1438,)]
        # validated_stored_simi = list(set([i for simituple in stored_simi for i in simituple]))
        # # print("stored_simi after",validated_stored_simi) # stored_simi [1376,1438]
        # continue


def get_stored_simi() :
    """
    Return the similarities already validated and stored in a local database.
    """
    # Get ids already processed in local db
    req = f"SELECT * FROM {simi_table} GROUP BY id"
    res = cur.execute(req)
    rows = cur.fetchall()
    for row in rows :
        artist = row[0]
        simi = row[1]
        type = row[2]
        print(f"({type}) : {artist} and {simi} are similar.")
        # print("entry : ", row)


def drop_local_db(ask=True) :
    """
    Clear the local similarities database.

    args :
        - ask (bool)    : if True (default), ask confirmation before flushing the db. Flush without warning otherwise.

    """
    if ask :
        # Get user confirmation before erasing
        fl = input('Do you confirm you want to erase local database of similarities (y/N) ? ')
        if fl != 'y' :
            print('The local similarities database was NOT flushed.')
            return

    # timestamp
    current_time = time.time()
    os.rename(DB_PATH, Path(DB_PATH.parent/f"local_db_{current_time}.db"))
    # removing without asking
    # os.remove(DB_PATH)
    print("Database has been deleted.")
    return


def get_user_associated_models(user=None, sep="|"):
    """
    Return the models associated with `user` : Student, Staff, Candidate

    args :
        - user : a User object

    return :
        - str   : A concated string of models associated to the user

    """

    ass_mod  = []

    if is_candidate_only(user) : ass_mod += ["Candidate only"]
    if is_student(user) : ass_mod += ["Student"]
    if is_staff(user) : ass_mod += ["Staff"]

    if not ass_mod :
        ass_mod += ["No associated model"]

    return f"{sep}".join(ass_mod)


def debug() :
    """
    Execute debug code
    """
    print("DEBUG ::::::::::::")

    # Get all users
    all_users = User.objects.annotate(
        # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
        # name but can be stored as "Hee  -- Won Lee"
        search_name=Concat('first_name__unaccent__lower',
                           Value(' '), 'last_name__unaccent__lower'),
    ).order_by('-id')

    print(f"{len(all_users)} users.")

    for user in all_users :
        # print(f"user : {user} ()")
        print(f"user : {user} ({get_user_associated_models(user)})")




    ############## AWS
    # user_id = 1059
    # artist = Artist.objects.filter(user=user_id)
    # print("artist",artist)
    # aws = Artwork.objects.prefetch_related('authors__user').filter(authors__in=artist)
    # if aws :
    #     for aw in aws :
    #         print("aw",aw)
    # else :
    #     print(f"no artwork associated to {artist}")


def clearTerm() :
    """
    Clear terminal window
    """
    os.system('cls' if os.name=='nt' else 'clear')




if __name__ == "__main__" :
    # os.system("pwd")
    # os.system("/Users/ocapra/Desktop/PROJECTS/KART/kart/manage.py duplicates --no-prompt")

    os.system("/Users/ocapra/Desktop/PROJECTS/KART/kart/manage.py duplicates --debug-mode")
    # items = prompt_list()
    # print("ITEMS :", items)
    pass
