#!/usr/bin/env python
"""Import festivals from csv
19 may 2023
"""


import sys
import os

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



# Shell Plus Django Imports (uncomment to use script in standalone mode, recomment before flake8)
import django
from django.conf import settings
sys.path.append(str(pathlib.Path(__file__).parent.parent.absolute()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kart.settings")
django.setup()

from pathlib import Path
import re
from production.models import Event

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
    id= data['id']
    try :
        ev = Event.objects.get(pk=id)
        # print(ev.title, id)
    except :
        print(f"Can't find the object with id {id}")
        continue

      
       
       
          

    # Get modification type
    if 'Modif' in data.keys() :
        modif = data['Modif']
        # get rid off "MODIF "
        if "MODIF " == modif[:6]:
            modif = modif[6:]
        
        # modif can include plus sign e.g. GENRE + TITRE
        modif_l = modif.split('+')
        # remove lead/trail spaces
        modif_l = [m.strip() for m in modif_l]
    
        # loop on elements e.g. GENRE,TITRE
        for m in modif_l :
            if 'GENRE' == m :
                pass
            if 'TITRE' == m :
                if 'Titre' in data.keys() : 
                    new_title = data['Titre']
                    
                if 'nom' in data.keys() : 
                    new_title = data['nom']
                
                print('titre modifié', ev.title, ' >> ' , new_title)
                ev.title = new_title

            if 'CONTINENT' == m :
                # get the place from event
                pass

            
            # ev.save()
            print("event updated !")