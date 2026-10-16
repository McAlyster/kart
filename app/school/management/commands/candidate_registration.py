"""

Transform valid Canditature to Student in promo

"""

import sys

from django.core.management.base import BaseCommand

from diffusion.management.commands.create_diffusion import input_choices
from people.models import Artist
from people.utils.artist_tools import getArtistByNames
from school.models import Student, StudentApplication, StudentApplicationSetup


class Command(BaseCommand):
    help = "Transform valid Candidature to Student in promo"

    def handle(self, *args, **options):

        campaign = StudentApplicationSetup.objects.filter(is_current_setup=True).last()
        candidatures = StudentApplication.objects.filter(campaign__is_current_setup=True, administration__selected=True)
        promo = campaign.promotion

        # valid promotion
        str_question = f"Les étudiants serons ajoutés à la promo  : {promo.name}   ? [y/n]  -  "
        valid = input(str_question)

        if valid != "y":
            sys.exit()

        # valid campaign
        str_question = f"La campagne de selection est  : {campaign.candidature_date_end.year}  ( {campaign.promotion.name} )  ? [y/n]  -  "
        valid = input(str_question)

        if valid != "y":
            sys.exit()

        # store existing artist
        student_artists = []

        for candidat in candidatures:
            # Skip if artist is already processed
            if candidat.artist in student_artists:
                print(f"Candidature de {candidat.artist} déjà traitée, passage à la suivante")
                continue
            # Process binomial application
            if candidat.binomial_application:
                artist1 = candidat.artist

                print(f"{artist1} candidate en Binome avec {candidat.binomial_application_with}")

                artist2_firstname = candidat.binomial_application_with.split(" ", 1)[0]
                artist2_lastname = candidat.binomial_application_with.split(" ", 1)[1]

                print("Recherche du binome")

                list_artist = getArtistByNames(firstname=artist2_firstname, lastname=artist2_lastname, listing=True)
                artist2_choice = input_choices(list_artist)

                if artist2_choice:
                    artist2 = artist2_choice["artist"]
                    app = artist2.student_application.filter(campaign=campaign).first()
                    if not app:
                        print(f"Aucune candidature trouvée pour {artist2}")
                        break
                    else:
                        print(f"Candidature trouvée pour {artist2} : {app}")
                else:
                    print(f"Aucun artiste trouvé pour {candidat.binomial_application_with}")
                    break

                # create a collective artist
                print("Recherche du nom du binome")
                nickname = artist1.nickname if artist1.nickname != "" else artist2.nickname
                nickname = input_choices([artist1.nickname, artist2.nickname, artist1.user, artist2.user])
                if not nickname:
                    nickname = input("Ecrire le nom du binome : ")

                artist, created = Artist.objects.get_or_create(user=None, nickname=nickname)
                if created:
                    artist.collectives.add(artist1)
                    artist.collectives.add(artist2)
                    artist.save()
                else:
                    print(f"L'artiste {artist} existe déjà, continuer ?")
                    continue_choice = input_choices([False, True])
                    if not continue_choice:
                        break

                student_artists.append(artist1)
                student_artists.append(artist2)
            # Process normal application
            else:
                artist = candidat.artist
            # Create student
            student, created = Student.objects.get_or_create(
                artist=artist, promotion=promo, number=candidat.current_year_application_count
            )

            student_artists.append(artist)

            print("{} {} : {}".format(student, "(binôme)" if candidat.binomial_application else "", created))
        print("FIN")
