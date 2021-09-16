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

os.chdir(pathlib.Path(__file__).parent.absolute())


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


if __name__ == "__main__" :
    import doctest
    doctest.testmod()
