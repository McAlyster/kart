#!/usr/bin/env python
"""Import festivals from csv
19 may 2023
"""


import sys
import os
import copy

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


from difflib import SequenceMatcher


# Shell Plus Django Imports (uncomment to use script in standalone mode, recomment before flake8)
import django
from django.conf import settings
sys.path.append(str(pathlib.Path(__file__).parent.parent.absolute()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()

from pathlib import Path
import re
from production.models import Event
from diffusion.models import Place, MetaAward, MetaEvent, Diffusion


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
        (MIDDLE_EAST,"Moyen Orient"),
        (ANTARTICA, "Antarctique"),
        (OCEANIA, 'Océanie')
    ]


# DRY RUN
dry_run = True
dry_run = False



# Utils 
def getContinent(name, index=True) :
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









# Load csv file 
fest_df = pd.read_csv(Path(pathlib.Path(__file__).parent , './fest_full_incorrect.csv'))
# fest_df = pd.read_csv(Path(pathlib.Path(__file__).parent , './fest_full_correct.csv'))
# print(fest_df)

# Rename columns (depending on the original csv file)
if 'ID Event' in fest_df.columns : fest_df.rename(columns={'ID Event':'id'}, inplace=True)
if 'Refs Kart' in fest_df.columns : fest_df.rename(columns={'Refs Kart':'id'}, inplace=True)

# Parsing uncorrect fest csv 
patt = re.compile('.*code:(.*)$')
for ind, data in fest_df.iterrows():
    
    # Current value e.g. InvidéO - Milan (IT) |code:1143
    id2parse = fest_df.iloc[ind]['id']

    if "code:" in str(id2parse) : 
        # Extract id e.g. 1143
        r = re.match(patt, id2parse)
        id = r.group(1)
        # Replace former value woth new one
        fest_df.loc[ind,'id'] = id
        

# For each row check if exists in db 
for ind, data in fest_df.iterrows():
    
    # Get the Kart id of the event 
    id = data['id']

    # Retrieve the event in Kart 
    try :
        ev = Event.objects.get(pk=id)
    except :
        print(f"Can't find the object with id {id}")
        continue

    # get the place from event
    place = ev.place

    # If no place associated wirth event 
    if place is None :
        # Create new place instance 
        place = Place()
        # Associate it to current event 
        ev.place = place

    ####################
    # Cities are replaced with csv data
    ev.place.name = data['ville'].lower() 

    # Lat and long come from Kart, because probably the most recent 
    # print("same city ? ", ev.place.name.lower() == data['ville'].lower(), data['ville'].lower())
    # print("same lat ? ", float(ev.place.latitude) == float(data['lat']), ev.place.latitude ,data['lat'])
    # print("same lng ? ", float(ev.place.longitude) == float(data['lng']), ev.place.longitude ,data['lng'])
    #####################


    # Example of a row in csv (fest_full_incorrect.csv):           
    # Refs Kart	Num	Type	Genre	nom	mois	site web	continent	pays	ville 	lat	lng	Modif
    #  Rencontres Internationales Paris/Berlin - Paris (FR) |code:1032	26	Festival	art contemporain	rencontres internationales paris/berlin	3	www.art-action.org	europe	france	paris	48,859116	2,331839	MODIF GENRE

    # Get modification type
    if 'Modif' in data.keys() :
        # init 
        modif_l = None

        modif = data['Modif']
        
        # get rid of "MODIF " string
        if "MODIF " == modif[:6]:
            modif = modif[6:]
                
            
        if modif.startswith("A SUPPRIMER - DOUBLON ") :
            # Keep DOUBLON XXX
            modif = modif[14:]
    
        # modif can include plus sign e.g. GENRE + TITRE
        modif_l = modif.split('+')
        
        # remove lead/trail spaces
        modif_l = [m.strip() for m in modif_l]

        # loop on elements e.g. GENRE,TITRE
        for m in modif_l :

            if "DOUBLON" in m :
                id = data['id']
                # Info de la part de Danaé : 
                # id to delete from Kart : data['id']
                # id to Keep : DOUBLON XXXXX
                pat = "DOUBLON (\d*)"
                r = re.match(pat, m)
                id2keep = r.group(1)
               

                # Check if id2keep is different from id to delete
                if id2keep == id :
                    # do nothing, it's not a true duplicate
                    pass
                else :
                    # Check where the id2del is referenced
                    id2del = id 
                    print("id2del : ", id2del)
                    print("id2keep : ", id2keep)
                    # MetaAwards 
                    try :
                        ma = MetaAward.objects.get(event_id=id2del)
                        mak = MetaAward.objects.get(event_id=id2keep)
                        print("MetaAwards del :",ma," keep :", mak)
                    except :
                        pass

                    # MetaEvent 
                    try :
                        ma = MetaEvent.objects.get(event_id=id2del)
                        mak = MetaEvent.objects.get(event_id=id2keep)
                        print("MetaEvent del :",ma," keep :", mak)
                    except :
                        pass

                    # Diffusion 
                    try :
                        ma = Diffusion.objects.get(event_id=id2del)
                        mak = Diffusion.objects.get(event_id=id2keep)
                        print("Diffusion del :",ma," keep :", mak)
                    except :
                        pass
                    

            if 'TITRE' == m :
                # Depending on csv files "TITRE" column may have different names ... 
                if 'Titre' in data.keys() : 
                    new_title = data['Titre']
                # ...                     
                if 'nom' in data.keys() : 
                    new_title = data['nom']
                
                
                if not ev.title == new_title :
                    print('titre modifié', ev.title, ' >> ' , new_title)
                    ev.title = new_title

            if 'GENRE' == m :
                if 'Genre' in data.keys() :
                    new_subtype = data['Genre']
                    if ev.subtype and not ev.subtype==new_subtype :
                        print('subtype modifié', ev.subtype, ' >> ' , new_subtype)
                        ev.subtype = new_subtype

            if 'CONTINENT' == m :
                new_continent = getContinent(data['continent'], True)
                if not place.continent == new_continent and place :
                    print('continent modifié', place.continent, ' >> ' , new_continent)
                    place.continent =  new_continent
                    if not dry_run :
                        place.save()
            

            if not dry_run :
                    place.save()
                    ev.save()
            else :
                print("Event not saved -- DRY RUN")