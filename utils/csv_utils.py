#! /usr/bin/env python
# -*- coding=utf8 -*-

import os
import sys
import pathlib
import yaml
import logging

from difflib import SequenceMatcher

from django.db.utils import IntegrityError
from django_countries import countries
from django.db.models.functions import Concat, Lower
from django.db.models import CharField, Value
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

import django
from django.conf import settings
sys.path.append(str(pathlib.Path(__file__).parent.parent.absolute()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()

from production.models import Artwork, Event, Film, Installation, Production
from people.models import Artist
from diffusion.models import Award, MetaAward, Place
from school.models import Student, Promotion
from django.contrib.auth.models import User
from assets.models import Gallery, Medium

# Logging
logger = logging.getLogger('kart_utils')
logger.setLevel(logging.DEBUG)

# os.chdir(pathlib.Path(__file__).parent.absolute())


def getArtworkByTitle(aw_title, sim_limit=.7, awlist=False):
    """
    Search an artwork by its title.

    Parameters
        aw_title (str): the title of the artwork
        sim_limit (float): (optional) the minimal similarity score between the given aw title and the one in the db, default 0.7
        list (bool): (optional) if True, return a list of matching artworks (empty list if no match)

    """

    # Retrieve artworks with matching title according to a minimal similarity
    # The list is order by similarity so the first element is the Kart's artwork whose title is the closest to aw_title
    guessAW = Artwork.objects.annotate(
        similarity=TrigramSimilarity('title', aw_title),
    ).filter(similarity__gt=sim_limit).order_by('-similarity')

    # If there is at least one match
    if guessAW :

        # Debug info
        logger.debug(f"\t-> Best guess : \"{guessAW[0].title}\"")
        logger.debug(f"Potential artworks in Kart found for \"{aw_title}\"...")

        # Explore the potential artworks (for debug purposes)
        for gaw in guessAW:
            # If approaching results is exactly the same
            title_match_dist = dist2(aw_title.lower(), gaw.title.lower())
            logger.debug(f"title_match_dist {title_match_dist}")

            # if all([title_match_dist, author_match_dist, title_match_dist == 1, author_match_dist == 1]):
            #     logger.warning("Perfect match: artwork and related authors exist in Kart")
            # if all([title_match_dist, author_match_dist, title_match_dist == 1]):
            #     logger.warning(
            #         f"Sure about the artwork title, confidence in author: {author_match_dist}")
            # if all([title_match_dist, author_match_dist, author_match_dist == 1]):
            #     logger.warning(
            #         f"Sure about the authors, confidence in artwirk: {author_match_dist}")

            # TODO: include author_match_dist for higher specificity
            # if all([title_match_dist, author_match_dist, title_match_dist == 1, author_match_dist == 1]):
            #     logger.warning("Perfect match: artwork and related authors exist in Kart")
            # if all([title_match_dist, author_match_dist, title_match_dist == 1]):
            #     logger.warning(
            #         f"Sure about the artwork title, confidence in author: {author_match_dist}")
            # if all([title_match_dist, author_match_dist, author_match_dist == 1]):
            #     logger.warning(
            #         f"Sure about the authors, confidence in artwirk: {author_match_dist}")


        # Return a list of aw if needed
        if awlist :
            return list(guessAW)

        # Return the best guess (best smiliarity)
        else :
            return guessAW[0]



    else:  # no artwork found in Kart
        logger.debug(f"No approaching artwork in KART for {aw_title}")
        return None


def dist2(item1, item2):
    """Return the distance between the 2 strings"""
    # print(f"dist2 {item1} versus {item2}")
    if not type(item1) == type(item2) == str:
        raise TypeError("Parameters should be str.")
    return round(SequenceMatcher(None, item1.lower(), item2.lower()).ratio(), 2)


#
def getGalleries(id_prod) :
    pass

def getDiffGallery(id_prod, force_list=False) :
    """
    Retrieve the diff gallery of production.

    Args:
        id_prod (int) : the id of the Production
        force_list (bool, optional) : if more than a diff gallery is found, retrieve a list of galleries
                                       (default : False)

    Returns:
        False (bool) : if id_prod does not exist in Kart
        Gallery object : if the Production with id==id_prod has a DiffGallery
        List of Gallery objects : if the Production with id==id_prod has more than a DiffGallery
        None : if the Production with id==id_prod has no DiffGallery
    """

    # Try to get the prod object with provided id
    try :
        prod = Production.objects.get(id=id_prod)
    except ObjectDoesNotExist :
        # Return False to indicate that the prod object was not found
        return False

    # Get the associated galleries
    galleries = prod.diff_galleries.all()

    # Return None if no diff galler is associated to the prod object
    if not galleries :
        return None

    if force_list :
        gal_list = []
        for g in galleries :
            gal_list += [g]
        return gal_list
    else :
        gal = galleries[0]
        return gal


def addMediaToGallery() :
    pass

def is_url(url) :
    """
        Indicate whether a given string is a valid url or not.

        Args :
            url (str) : The url to validate

        Return :
            bool : True is provided url is valid, False otherwise


        >>> is_url("http://www.lefresnoy.net")
        True
        >>> is_url("je s'appelle Groot")
        False

    """
    val = URLValidator()
    try:
        val(url)
    except ValidationError as e:
        return False
    return True


def getUserByNames(firstname="", lastname="", pseudo="", listing=False, dist_min=False): # TODO remove pseudo from params
    """Retrieve the closest user from the first and last names given

    Parameters:
    - firstname: (str) Firstname to look for
    - lastname : (str) Lastname to look for
    - listing  : (bool) If True, return a list of matching artists (Default, return the closest)
    - dist_min : (float) Maximum dist, return False if strinctly under

    Return:
    - artistObj    : (Django obj / bool) The closest user object found in Kart. False if no match.
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

    # List of users that could match
    users_l = []

    # Clean names from accents to
    if lastname:
        # lastname_accent = lastname
        lastname = unidecode.unidecode(lastname).lower()
    if firstname:
        # firstname_accent = firstname
        firstname = unidecode.unidecode(firstname).lower()
    # if pseudo:
    #     # pseudo_accent = pseudo
    #     pseudo = unidecode.unidecode(pseudo).lower()
    fullname = f"{firstname} {lastname}"

    # Cache
    fullkey = f'{firstname} {lastname} {pseudo}'
    try:
        # logger.warning("cache", search_cache[fullkey])
        return search_cache[fullkey] if listing else search_cache[fullkey][0]
    except KeyError:
        pass
    except TypeError:
        pass

    # SEARCH WITH LASTNAME then FIRSTNAME
    # # First filter by lastname similarity
    # guessArtLN = Artist.objects.prefetch_related('user').annotate(
    #     # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
    #     # name but can be stored as "Hee  -- Won Lee"
    #     search_name=Concat('user__first_name__unaccent__lower',
    #                        Value(' '), 'user__last_name__unaccent__lower')
    # ).annotate(
    #     similarity=TrigramSimilarity('search_name', fullname),
    # ).filter(
    #     similarity__gt=0.3
    # ).order_by('-similarity')

    # First filter by lastname similarity
    guessArtLN = User.objects.annotate(
        # Concat the full name "first last" to detect misclassifications like: "Hee Won -- Lee" where Hee Won is first
        # name but can be stored as "Hee  -- Won Lee"
        search_name=Concat('first_name__unaccent__lower',
                           Value(' '), 'last_name__unaccent__lower')
    ).annotate(
        similarity=TrigramSimilarity('search_name', fullname),
    ).filter(
        similarity__gt=0.3
    ).order_by('-similarity')

    # Refine results
    if guessArtLN:
        # TODO: Optimize by checking a same artist does not get tested several times
        for user_kart in guessArtLN:

            # print(f"\tARTIST : {user_kart}")

            # Clear accents (store a version with accents for further accents issue detection)
            kart_lastname_accent = user_kart.last_name
            kart_lastname = unidecode.unidecode(kart_lastname_accent).lower()
            print("kart_lastname_accent", kart_lastname_accent,"kart_lastname", kart_lastname)
            kart_firstname_accent = user_kart.first_name
            kart_firstname = unidecode.unidecode(kart_firstname_accent).lower()

            kart_fullname_accent = user_kart.search_name

            # Stripping issues
            kart_data = {   'cleaned' : {'lastname':kart_lastname, 'firstname':kart_firstname},
                            'raw':{'lastname':kart_lastname_accent, 'firstname':kart_firstname_accent}
                        }

            kart_fullname = f"{kart_firstname} {kart_lastname}".lower()

            dist_full = dist2(kart_fullname, fullname)

            # logger.warning('match ',kart_fullname , dist2(kart_fullname,fullname), fullname,kart_fullname == fullname)
            # In case of perfect match ...
            if dist_full > .9:
                if kart_fullname == fullname:
                    # store the artist in potential matches with extreme probability (2)
                    # and continue with next candidate
                    users_l.append({"user": user_kart, 'dist': 2})
                    continue
                # Check if Kart and candidate names are exactly the same
                elif kart_lastname != lastname or kart_firstname != firstname :

                    logger.warning(f"""Fullnames globally match {fullname} but not in first and last name correspondences:
                    Kart       first: >{kart_firstname}< last: >{kart_lastname}<
                    candidate  first: >{firstname}< last: >{lastname}<
                                            """)
                    users_l.append({"user": user_kart, 'dist': dist_full*2})



                    # ### Control for accents TODO still necessary ?
                    #
                    # accent_diff = kart_lastname_accent != lastname_accent or \
                    #               kart_firstname_accent != firstname_accent
                    # if accent_diff: logger.warning(f"""\
                    #                 Accent or space problem ?
                    #                 Kart: {kart_firstname_accent} {kart_lastname_accent}
                    #                 Candidate: {firstname_accent} {lastname_accent} """)


            # Control for blank spaces

            if  kart_lastname.startswith(" ") or kart_lastname.endswith(" ") :
                print(f"before : kart_lastname.strip() >{kart_lastname}<")
                print(f"kart_lastname.strip() >{kart_lastname.strip()}<")
                print(f"after : kart_lastname.strip() >{kart_lastname}<")

            if  lastname.startswith(" ") or lastname.endswith(" ") :
                print(f"before : lastname.strip() >{lastname}<")
                print(f"lastname.strip() >{lastname.strip()}<")
                print(f"after : lastname.strip() >{lastname}<")
                # Check for leading/trailing whitespace in lastname
                if kart_lastname.strip() == lastname.strip() :
                    if kart_lastname.find(" ") >= 0 :
                        cor = Correction(kart_lastname,kart_lastname.strip())
                    bef = f"\"{kart_lastname}\" <> \"{lastname}\""
                    logger.warning(f"Leading/trailing whitespace {bef}")


                # Check distance btw lastnames without spaces
                elif dist2(kart_lastname.replace(" ", ""), lastname.replace(" ", "")) > .9:
                    bef = f"\"{kart_lastname}\" <> \"{lastname}\""
                    logger.warning(f"whitespace problem ? {bef}")

            if kart_firstname.find(" ") >= 0 or firstname.find(" ") >= 0:

                if kart_firstname.strip() == firstname.strip() :
                    bef = f"\"{kart_firstname}\" <> \"{firstname}\""
                    logger.warning(f"Leading/trailing whitespace {bef}")

                # Check distance btw firstnames without spaces
                elif dist2(kart_firstname.replace(" ", ""), firstname.replace(" ", "")) > .9:
                    bef = f"\"{kart_firstname}\" <> \"{firstname}\""
                    logger.warning(f"whitespace problem ? {bef}")
            ###

            # Artists whose lastname is the candidate's with similar firstname

            # Distance btw the lastnames
            dist_lastname = dist2(kart_lastname, lastname)

            # # try to find by similarity with firstname
            # guessArtFN = Artist.objects.prefetch_related('user').annotate(
            #     similarity=TrigramSimilarity('user__first_name__unaccent', firstname),
            # ).filter(user__last_name=lastname, similarity__gt=0.8).order_by('-similarity')

            guessUserFN = User.objects.annotate(
                similarity=TrigramSimilarity('first_name__unaccent', firstname),
            ).filter(last_name=lastname, similarity__gt=0.8).order_by('-similarity')


            # if user whose lastname is the candidate's with similar firstname names are found
            if guessUserFN:

                # Check users with same lastname than candidate and approaching firstname
                for userfn_kart in guessUserFN:
                    kart_firstname = unidecode.unidecode(userfn_kart.first_name)
                    # Dist btw candidate firstname and a similar found in Kart
                    dist_firstname = dist2(f"{kart_firstname}", f"{firstname}")
                    # Add the candidate in potential matches add sum the distances last and firstname
                    users_l.append({"user": userfn_kart, 'dist': dist_firstname+dist_lastname})

                    # Distance evaluation with both first and last name at the same time
                    dist_name = dist2(f"{kart_firstname} {kart_lastname}",
                                      f"{firstname} {lastname}")
                    # Add the candidate in potential matches add double the name_dist (to score on 2)
                    users_l.append({"user": userfn_kart, 'dist': dist_name*2})

            else:
                # If no close firstname found, store with the sole dist_lastname (unlikely candidate)
                users_l.append({"user": user_kart, 'dist': dist_lastname})

            ### end for user_kart in guessArtLN

        # Take the highest distance score
        users_l.sort(key=lambda i: i['dist'], reverse=True)

        # Return all results if listing is true, return the max otherwise
        if listing:
            search_cache[fullkey] = users_l
            return users_l
        else:
            search_cache[fullkey] = [users_l[0]]
            # Return the result if dist_min is respected (if required)
            if (dist_min is not False and users_l[0]['dist']>dist_min) or (not dist_min) :
                return users_l[0]
            else :
                return False
    else:
        # research failed
        search_cache[fullkey] = False
        return False
    #####




if __name__ == "__main__" :
    import doctest
    doctest.testmod()
