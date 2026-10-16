import csv
import datetime
import os
import re
import unicodedata

import markdownify
import requests
import unidecode
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from langdetect import detect
from taggit.models import Tag

from common.models import Website
from people.models import Artist, Staff, User
from people.utils.artist_tools import getArtistByNames
from people.utils.user_tools import getUserByNames
from production.models import (
    Event,
    Film,
    FilmGenre,
    Installation,
    InstallationGenre,
    Organization,
    OrganizationTask,
    Performance,
    ProductionOrganizationTask,
    ProductionStaffTask,
    StaffTask,
)
from utils.kart_tools import usernamize

"""
    USAGE : ./manage.py import_catalog --path_to_csv <path_to_csv_file>
    OU
    ./manage.py import_catalog --dry-run

"""


# Mapping entre les colonnes CSV et les champs du modèle
FIELD_MAPPING = {
    "email": "user_email",
    "first_name": "user_first_name",
    "last_name": "user_last_name",
    "artist_type": "artist_type",
    "artist_name": "artist_nickname",
    "id_photo": "artist_id_photo",
    "artist_email": "artist_email",
    "website": "artist_website",
    "social_networks": "artist_social_networks",
    "biography": "artist_biography",
    "biography_translated": "artist_biography_translated",
    "type": "artwork_type",
    "title": "artwork_title",
    "subtitle": "artwork_subtitle",
    "description": "artwork_description",
    "description_translated": "artwork_description_translated",
    "duration": "artwork_duration",
    "shooting_format": "artwork_shooting_format",
    "aspect_ratio": "artwork_aspect_ratio",
    "process": "artwork_process",
    "genres": "artwork_genres",
    "languages_vo": "artwork_languages_vo",
    "languages_subtitles": "artwork_languages_subtitles",
    "technical_description": "artwork_technical_description",
    "thanks": "artwork_thanks",
    "partners": "artwork_partners",
    "partners_description": "artwork_partners_description",
    "credits": "artwork_credits",
    "credits_description": "artwork_credits_description",
    "keywords": "artwork_keywords",
    "shooting_places": "artwork_shooting_places",
    "images_process": "artwork_images_process",
    "images_screen": "artwork_images_screen",
    "logos": "artwork_logos",
}


class Command(BaseCommand):
    help = "Import catalogue csv file into kart database"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {}
        self.remote_base_url = ""
        self.media_path = ""
        self.dry_run = False
        self.download_images = True
        self.start_line = 0

    def add_arguments(self, parser):
        # -- required
        parser.add_argument("--path_to_csv", type=str, required=True, help="CSV Path")
        parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
        parser.add_argument(
            "--no-images-download", action="store_false", help="Ne télécharge pas les images (pour les tests)"
        )
        parser.add_argument("--started-on-line", type=int, default=0, help="Commence à la ligne (pour les tests)")

    def handle(self, *args, **options):
        # Clear terminal
        self.stdout.write("\033[H\033[J")

        # get path to csv file
        path_to_csv = options.get("path_to_csv")
        self.dry_run = options.get("dry_run", False)
        self.download_images = options.get("no_images_download", True)
        self.start_line = options.get("started_on_line", 0)

        print("Chemin CSV : ", path_to_csv)
        print("DRY RUN : ", self.dry_run)
        print("LINE START : ", self.start_line)
        print("Téléchargemetnt des images : ", self.download_images)

        self.stdout.write(f"Importing catalogue from file: {path_to_csv}")

        try:
            with transaction.atomic():
                self.init_process(path_to_csv)

                if self.dry_run:
                    self.stdout.write(self.style.WARNING("\n[DRY RUN] Annulation des changements..."))
                    raise RuntimeError("Dry run rollback")

                self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Traitement enregistré !"))
        except RuntimeError as e:
            if str(e) != "Dry run rollback":
                raise e
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.ERROR("\n[STOP] Script interrompu par l'utilisateur. Aucun changement enregistré.")
            )

    def map_csv_to_model(self, row):
        """Map les données d'une ligne CSV aux champs du modèle."""

        mapped_data = {}
        for csv_column, model_field in FIELD_MAPPING.items():
            mapped_data[model_field] = row.get(csv_column).strip()
        return mapped_data

    def init_process(self, path_to_csv, *args):
        # get the file
        fichier_csv = path_to_csv
        if not os.path.exists(fichier_csv):
            print("Le fichier CSV n'existe pas : " + fichier_csv)
            return

        # Clear terminal
        # self.stdout.write("\033[H\033[J")

        input("Vérifiez que vous avez la dernière version du catalalogue à mettre dans : " + fichier_csv)

        # create Panorama event
        current_year = datetime.datetime.now().year
        event = Event.objects.get(
            title="Panorama " + str(current_year + 2 - 2000),
            # créer le panorama à la main avant de lancer le script
            # starting_date=datetime.datetime(current_year, 1, 1, tzinfo=pytz.timezone("Europe/Paris")),
        )

        if not event:
            print("Le panorama n'existe pas, créez-le !")
            return

        with open(fichier_csv, "r") as csvfile:
            lecteur_csv = csv.DictReader(csvfile, delimiter=",", quotechar='"')

            for i, row in enumerate(lecteur_csv):
                if i < self.start_line:
                    print("next line : " + str(i))
                    continue
                data = self.map_csv_to_model(row)
                artwork = self.populateAPI(data)
                # set event to panorama
                match artwork.polymorphic_ctype.model:
                    case "film":
                        event_artworks = event.films
                    case "installation":
                        event_artworks = event.installations
                    case "performance":
                        event_artworks = event.performances
                event_artworks.add(artwork)

        for elt in self.stats:
            print(elt + " : " + str(len(self.stats[elt])))

        event.save()

        print("Termine !")

    def populateAPI(self, data):

        # GET DB ARTIST
        # get name
        artist_name = (
            data["artist_nickname"]
            if data["artist_nickname"]
            else data["user_first_name"] + " " + data["user_last_name"]
        )
        # search
        artist_search = getArtistByNames(data["user_first_name"], data["user_last_name"], data["artist_nickname"])
        artist_search_list = getArtistByNames(
            data["user_first_name"], data["user_last_name"], data["artist_nickname"], True
        )

        print(f"\n\n{artist_name}")

        # doute ?
        if artist_search["dist"] < 0.99:
            ask = input(
                "Est-ce la même personne oui/non ? (db) {}  <-> {} (csv)".format(artist_search["artist"], artist_name)
            )
            if "n" in ask:
                print("Artiste non trouvé")
                print("Et dans cette liste ? ")
                select_with_result_list = self.input_choices(artist_search_list)
                if select_with_result_list:
                    artist_search = select_with_result_list["artist"]
                    created = False
                else:
                    # reverse name/lastname
                    artist_search_reverse_list = getArtistByNames(
                        data["user_last_name"], data["user_first_name"], data["artist_nickname"], True
                    )
                    select_with_result_list_reverse = self.input_choices(artist_search_reverse_list)
                    if select_with_result_list_reverse:
                        artist_search = select_with_result_list_reverse["artist"]
                        created = False
                    else:
                        print("ARTIST CREATOR ERROR !!! ")
                        print("il n'existe pas alors que normalement il doit être dans la base")
                        return

        artist = artist_search["artist"]

        print("START WITH ARTIST")
        print(f"  {artist} ")
        print("*********")

        # BIO
        bio_fr = self.select_french_text(data["artist_biography"], data["artist_biography_translated"])
        bio_en = self.select_english_text(data["artist_biography"], data["artist_biography_translated"])

        artwork_type = data["artwork_type"]

        artwork_title = data["artwork_title"]
        artwork_subtitle = data["artwork_subtitle"]
        artwork_text_fr = self.select_french_text(data["artwork_description"], data["artwork_description_translated"])
        artwork_text_en = self.select_english_text(data["artwork_description"], data["artwork_description_translated"])

        # film
        artwork_duration = data["artwork_duration"]
        artwork_shooting_format = data["artwork_shooting_format"]
        artwork_aspect_ratio = data["artwork_aspect_ratio"]
        artwork_process = data["artwork_process"]
        shooting_places = data["artwork_shooting_places"]
        artwork_languages_vo = data["artwork_languages_vo"]
        artwork_languages_subtitles = data["artwork_languages_subtitles"]
        # install
        artwork_technical_description = data["artwork_technical_description"]
        # thanks
        artwork_thanks = data["artwork_thanks"]
        # partners
        artwork_partners = data["artwork_partners"]
        partners_description = data["artwork_partners_description"]
        # credits
        artwork_credits = data["artwork_credits"]
        artwork_credits_description = data["artwork_credits_description"]
        if artwork_credits == "" and "\n" in artwork_credits_description and ":" in artwork_credits_description:
            artwork_credits = artwork_credits_description
        # keywords
        keywords = data["artwork_keywords"]
        genres = data["artwork_genres"]
        # images
        images_process = data["artwork_images_process"]
        images_screen = data["artwork_images_screen"]
        # replace urls
        images_process = self.replaceUrlMedia(images_process)
        images_process = images_process.split("|")

        images_screen = self.replaceUrlMedia(images_screen)
        images_screen = images_screen.split("|")

        artwork_avatar = images_screen.pop(0) if images_screen else images_process.pop(0) if images_process else ""
        artwork_medias = images_screen + images_process

        artwork_partners_media = self.replaceUrlMedia(data["artwork_logos"]).split("|") if data["artwork_logos"] else []

        # artist
        artist_db = artist

        print("ARTWORK")
        print(f"  {artwork_title} - {artwork_type}")
        print("*********")

        artwork = None
        if artist_db:
            artwork = self.getOrCreateProduction(artist_db, artwork_title, artwork_type)

        # subtitle
        artwork.subtitle = artwork_subtitle

        # artist bio
        artist_db = self.updateArtistBio(artist_db, bio_fr, bio_en)

        # update user email
        if artist_db.user and data["user_email"] and artist_db.user.email != data["user_email"]:
            artist_db.user.email = data["user_email"]
            artist_db.user.save()

        # set nickname
        db_artist_name_slug = (
            self.slugify(artist_db.user.first_name + " " + artist_db.user.last_name)
            if artist_db.user
            else artist_db.nickname
        )
        if artist_name and self.slugify(artist_name) != db_artist_name_slug:
            artist_db.nickname = artist_name

        # photo
        if data.get("artist_id_photo") and not artist_db.artist_photo:
            artist_id_photo = data["artist_id_photo"].replace(
                "identity/", f"{self.remote_base_url + self.media_path}/identity/"
            )
            id_photo_name = artist_id_photo.split("/")[-1]
            id_photo_file = self.createFileFromUrl(artist_id_photo)

            artist_db.artist_photo.save(id_photo_name[-35:], id_photo_file, save=True)

        # union websites & RS
        websites = data["artist_website"] + "\n" + data["artist_social_networks"]
        for website in websites.split("\n"):
            if website.strip() != "":
                website = website.strip()
                self.set_website_or_social_network(artist_db, website)

        # ARTIST SAVE
        artist_db.save()

        # duration
        if artwork_duration:
            hours = minutes = seconds = 0
            # 20:00 or 00:20:00
            duration = artwork_duration.split(":")
            hours = int(duration[0])
            minutes = int(duration[1])
            # 00:20:00
            if len(duration) > 2:
                seconds = int(duration[2])
            if hours > 2:
                seconds = minutes
                minutes = hours
                hours = 0
            artwork.duration = datetime.timedelta(
                hours=hours,
                minutes=minutes,
                seconds=seconds,
            )
            print("Duration : ", artwork_duration, artwork.duration)

        # text
        # artwork.description_fr = markdownify.markdownify(artwork_text_fr)
        artwork.description_fr = artwork_text_fr
        # artwork.description_en = markdownify.markdownify(artwork_text_en)
        artwork.description_en = artwork_text_en

        # keywords
        self.set_keywords(artwork, "keywords", keywords)

        # genres
        genres_list = genres.split(",")
        for genre in genres_list:
            self.set_genre(artwork, genre)

        # print(artwork)

        # shooting_places
        if artwork_type.lower() == "film" and shooting_places:
            places_list = shooting_places.split("\n")
            for str_place in places_list:
                place = self.getPlace(str_place)
                if place:
                    artwork.shooting_place.add(place)

        # shooting format -> keep first()
        if artwork_type.lower() == "film" and artwork_shooting_format:
            artwork.shooting_format = artwork_shooting_format.split(",")[0]

        # aspect_ratio -> keep first()
        if artwork_type.lower() == "film" and artwork_shooting_format:
            artwork.aspect_ratio = artwork_aspect_ratio.split(",")[0]

        # languages_vo
        if artwork_type.lower() == "film" and artwork_languages_vo:
            self.set_languages(artwork, "languages_vo", artwork_languages_vo)

        # artwork_languages_subtitles
        if artwork_type.lower() == "film" and artwork_languages_subtitles:
            self.set_languages(artwork, "languages_subtitles", artwork_languages_subtitles)

        # process
        if artwork_type.lower() == "film" and artwork_process:
            artwork.process = artwork_process.split(",")[0]

        if artwork_type.lower() == "installation":
            artwork.technical_description = artwork_technical_description

        # avatar
        if artwork_avatar == "" and artwork_medias:
            artwork_avatar = artwork_medias.pop(0)

        if artwork_avatar and not artwork.picture:
            avatar_name = artwork_avatar.split("/")[-1]
            avatar_file = self.createFileFromUrl(artwork_avatar)
            artwork.picture.save(avatar_name[-35:], avatar_file, save=True)
        # gallery
        if images_process:
            # create gallery from images_process
            gallery_process, gall_created = self.createGalleryFromArtwork(artwork, artist_db, "Images du processus")
            artwork.process_galleries.add(gallery_process.id)
            if gall_created:
                for url in images_process:
                    self.createMediaFromUrl(url, gallery_process.id)

        if images_screen:
            # create gallery from images_screen
            gallery_screen, gall_created = self.createGalleryFromArtwork(artwork, artist_db, "Images de l'écran")
            artwork.in_situ_galleries.add(gallery_screen.id)
            if gall_created:
                for url in images_screen:
                    self.createMediaFromUrl(url, gallery_screen.id)

        # partners
        # set base production
        orga_fresnoy = Organization.objects.filter(name__icontains="le fresnoy").first()
        task_prod = OrganizationTask.objects.filter(label__icontains="producteur")

        if task_prod.count() > 1:
            print("Plusieurs task 'producteur' trouvés : ", task_prod)
            task_prod = self.input_choices(task_prod)

        else:
            task_prod = task_prod.first()

        po, created = ProductionOrganizationTask.objects.get_or_create(
            task=task_prod, organization=orga_fresnoy, production=artwork
        )

        self.setStats(po, created)

        self.set_partners(artwork, artwork_partners, artwork_partners_media)

        # collaborators -> credits
        self.set_credits(artwork, artwork_credits)

        artwork.thanks_fr = markdownify.markdownify(artwork_thanks)
        artwork.credits_fr = markdownify.markdownify(artwork_credits_description)

        if partners_description:
            artwork.credits_fr += "\n\nDescription du partenariat:  \n"
            artwork.credits_fr += markdownify.markdownify(partners_description)

        # ARTWORK SAVE
        artwork.save()

        print("END ARTWORK")
        print("  {} - {}".format(artwork.title, artwork.id if artwork.id else "None"))
        print("*********")

        return artwork

    def replaceUrlMedia(self, str):
        return str.replace("app/static/uploads/photos/", self.remote_base_url + self.media_path)

    def setStats(self, value_from_model, created):
        class_name = value_from_model.__class__.__name__.lower()
        attibute = class_name + "_created" if created else class_name + "_reused"
        if attibute not in self.stats:
            self.stats[attibute] = []
        self.stats[attibute].append(value_from_model)

    def get_or_create(self, model, attr):

        created = False
        try:
            instance = model.objects.get(**attr)
        except Exception:
            instance = model(**attr)
            created = True
            instance.save()
        return [instance, created]

    def select_french_text(self, str1, str2):
        str1_language = detect(str1)
        if str1_language == "fr":
            # print("LAngue FR : ", str1[:25])
            return str1
        # print("LAngue FR : ", str2[:25])
        return str2

    def select_english_text(self, str1, str2):
        str1_language = detect(str1)
        if str1_language == "en":
            # print("LAngue EN : ", str1[:25])
            return str1
        # print("LAngue EN : ", str2[:25])
        return str2

    def input_choices(self, values):

        if not values:
            return False

        print("Plusieurs valeurs sont possibles, selectionnez-en une :")
        for id, value in enumerate(values):
            print(f"{id} : {value} {self.highlightChoices(value)}")

        print("n : pas dans la liste")
        select = input("Votre choix : ")

        # select = input("Plusieurs valeurs sont possibles, selectionnez-en une :"
        #                + str([str(id) + " : " + str(s) for id, s in enumerate(values)]))
        try:
            select_int = int(select)
            selected = values[select_int]
            return selected
        except Exception:
            return False

    def highlightChoices(self, dict):
        hl_text = ""
        try:
            if "user" in dict:
                user = dict["user"]
                hl_text += "\n   > User : " + str(user.id) + " - " + str(user)
                if user.staff_set.exists():
                    hl_text += self.highlightStaff(user.staff_set.first())
                if user.artist_set.exists():
                    hl_text += self.highlightArtist(user.artist_set.first())
            if "artist" in dict:
                artist = dict["artist"]
                hl_text += self.highlightArtist(artist)
                if artist.user.staff_set.exists():
                    hl_text += self.highlightStaff(artist.user.staff_set.first())
        except Exception:
            # print("Error in highlightChoices: ", e)
            hl_text += "\n   > " + str(dict)
        return hl_text

    def highlightArtist(self, artist):
        hl_text = "\n   > "
        hl_text += "Artist : " + str(artist.id) + " - " + str(artist)
        if artist.artworks.exists():
            hl_text += "\n   > "
            hl_text += "Artworks : " + ", ".join(artist.artworks.all().values_list("title", flat=True))
        return hl_text

    def highlightStaff(self, staff):
        hl_text = ""
        if staff.productionstafftask_set.exists():
            hl_text += "\n   > "
            hl_text += "Tasks : " + ", ".join(staff.productionstafftask_set.all().values_list("task__label", flat=True))
        return hl_text

    def set_partners(self, artwork, partners_str, partners_media):
        if partners_str.strip() == "":
            return
        # FORME - type : structure \n
        partners_arr = partners_str.split("\n")
        for partner in partners_arr:
            # la forme Coproduction : Julien Taïb, Crossed Lab
            partner = partner.strip()
            if partner == "":
                continue
            if ":" not in partner:
                # set default partenaire type
                partner = "Partenaire : " + partner

            # TYPE
            partner_type_str = partner.split(":")[0].strip()
            partner_types = self.getOrCreateMultiInstancesByStr(OrganizationTask, "label", partner_type_str)

            # ORGANIZATION
            organization_str = partner.split(":")[1].strip()
            organizations = self.getOrCreateMultiInstancesByStr(Organization, "name", organization_str)

            # ADD logo to ORGA
            for organization in organizations:
                name = organization.name
                if not organization.picture and partners_media:
                    print("Organisation : " + name + " est sans logo, est-ce qu'il est dans ce choix ? ")
                    media_choice = self.input_choices(partners_media)
                    if media_choice:
                        name = media_choice.split("/")[-1]
                        file = self.createFileFromUrl(media_choice)
                        if file:
                            organization.picture.save(name[-35:], file, save=True)

            # HAVE TO
            # ONE type ONE organization
            # One type Multi organizations
            # Multi types -> problems One task
            # Multi type multi organizations -> problem
            if (
                len(partner_types) == 0
                or len(organizations) == 0
                or (len(partner_types) > 1 and len(organizations) > 1)
            ):
                print("*****PROBLEME DE PARTNERS  ******")
                print(partner)
                continue
            # partner : organization
            elif len(partner_types) == 1 and len(organizations) == 1:
                partner_type = partner_types[0]
                organization = organizations[0]
                pot, created = ProductionOrganizationTask.objects.get_or_create(
                    task=partner_type, organization=organization, production=artwork
                )
                self.setStats(pot, created)
                print(pot)
            # partner : organization 1, organization 2
            elif len(partner_types) == 1 and len(organizations) > 1:
                partner_type = partner_types[0]
                for organization in organizations:
                    pot, created = ProductionOrganizationTask.objects.get_or_create(
                        task=partner_type, organization=organization, production=artwork
                    )
                    self.setStats(pot, created)
                    print(pot)
            # partner, coproduction  : organization
            elif len(partner_types) > 1 and len(organizations) == 1:
                organization = organizations[0]
                for partner_type in partner_types:
                    pot, created = ProductionOrganizationTask.objects.get_or_create(
                        task=partner_type, organization=organization, production=artwork
                    )
                    self.setStats(pot, created)
                    print(pot)

    def getOrCreateMultiInstancesByStr(self, model, attr, txt_str):
        instances = []
        txt_str = txt_str.strip()
        char_split = [
            ",",
            "/",
            ";",
            " & ",
        ]
        if " et " in txt_str:
            print(f"'ET' est présent dans '{txt_str}', s'agit il de PLUSIEURS {model.__name__} ?")
            if self.input_choices([False, True]):
                char_split.append(" et ")

        if any(sep in txt_str for sep in char_split):
            # split by comma or "et" or " / "
            for sep in char_split:
                txt_str = txt_str.replace(sep, ",")
            str_split = txt_str.split(",")
            for s in str_split:
                instance = self.getOrCreateModelInstanceByStr(model, attr, s)
                instances.append(instance)
        else:
            instance = self.getOrCreateModelInstanceByStr(model, attr, txt_str)
            instances.append(instance)

        return instances

    def getOrCreateModelInstanceByStr(self, model, attr, txt_str):

        instance = False

        txt_str = txt_str.strip()

        query = model.objects.filter(**{attr + "__iexact": txt_str})

        if query.count() == 0:
            query = model.objects.filter(**{attr + "__icontains": txt_str})

        if query.count() == 0:
            query = model.objects.filter(**{attr + "__unaccent__icontains": txt_str})

        if query.count() > 1:
            print(str(model) + " (csv) : " + txt_str)
            instance = self.input_choices(query)

        elif query.count() == 1:
            instance = query.first()

        if not instance:
            instance, created = model.objects.get_or_create(**{attr: txt_str.title()})
            self.setStats(instance, created)
            print("Création d'une instance" + str(model.__name__) + " : " + str(instance))

        return instance

    def set_languages(self, instance, field, str):
        if not hasattr(instance, field):
            print("Erreur Language", instance, field, str)
            return

        list = []
        str_list = str.split(",")
        for s in str_list:
            s = s.lower().strip()
            # sometimes some detail add with lang (es_419, fr,ar_001,aeb) in str we don't need this specifications
            s = re.split(r"[^a-z]+", s)[0]
            list.append(s)
        list_str = ", ".join(list)
        setattr(instance, field, list_str)
        print("Set Languages", field, str)

    def set_keywords(self, instance, field, str):
        if not hasattr(instance, field):
            print("Erreur KEYWORDS", instance, field, str)
            return

        list = []
        str_list = str.split(",")
        contentype_id = ContentType.objects.get_for_model(instance).id
        for s in str_list:
            # sanitize
            s = s.lower().strip()
            if not s:
                continue
            # search for an existig Tag
            q = Tag.objects.filter(name__unaccent=s, taggit_taggeditem_items__content_type=contentype_id)
            if not q:
                q = Tag.objects.filter(name__unaccent=s)
            # get the most used tag
            tag_db = q.annotate(tag_count=Count("taggit_taggeditem_items")).order_by("-tag_count")
            tag_db_first = tag_db.first()
            if tag_db_first:
                # WHY sometimes hassattr ou directly an str ??
                tag_str = tag_db_first.name if hasattr(tag_db_first, "name") else tag_db_first
                if len(tag_str) == len(s):
                    s = tag_str
                else:
                    # used ? (befor name__unaccent__icontains)
                    stats_values = (
                        q.annotate(tag_count=Count("taggit_taggeditem_items"))
                        .order_by("-tag_count")
                        .values_list(
                            "name",
                            "tag_count",
                        )
                    )
                    print(f"keywords '{s}' ambigus {stats_values}")

                    r = self.input_choices([s, tag_str])
                    # avoid error when input_choices is not in the list
                    while type(r) is bool:
                        r = self.input_choices([s, tag_str])
                    s = r

            list.append(s)

        print("Keywords :", str, list)
        instance.keywords.set(list)

    def set_genre(self, aw, genre_str):
        genre_str = genre_str.strip()

        if genre_str == "":
            return

        modelGenre = None
        match aw.polymorphic_ctype.model:
            case "film":
                modelGenre = FilmGenre
            case "installation":
                modelGenre = InstallationGenre
            case "performance":
                # no genre in performance
                return
            case _:
                # default
                return
        # query genre
        genre_query = modelGenre.objects.filter(label__iexact=genre_str)
        if genre_query.count() == 0:
            genre_query = modelGenre.objects.filter(label__unaccent__icontains=genre_str)

        genre = False
        if genre_query and genre_query.count() == 1:
            genre = genre_query.first()

        elif genre_query and genre_query.count() > 1:
            print("Genre csv : " + genre_str)
            genre = self.input_choices(genre_query)

        if not genre:
            print("********** GENRE PROBLEME *********** ")
            print(genre)
        else:
            aw.genres.add(genre)

    def set_credits(self, aw, credits):

        # many ways detected in csv
        # staf : task \n
        # staf : name or fistname, lastname

        if "\n" not in credits:
            return False

        credits_arr = credits.split("\n")

        for credit in credits_arr:
            if ":" not in credit:
                print("/!\\ credit n'a pas de ':'" + credit)
                continue

            print("********** CREDIT *********** ")
            isReverseStaffTask = self.is_staff_task_reverse(credit)
            print(credit, "isReverseStaffTask: ", isReverseStaffTask)
            # if is reverse, we have to switch staf and task
            staffIndex = 0 if not isReverseStaffTask else 1
            taskIndex = 1 if not isReverseStaffTask else 0

            # SEARCH FOR USER
            user_str = credit.split(":")[staffIndex].strip()
            print("SEARCH FOR USER : " + user_str)
            users = []
            user = False
            # "," in name mean that this is an human in DB (comme with catalog plateform dev)
            # but mean sometimes two person for the same task Nina Guseva, Anna Collard : céramiste
            # OR Nina Guseva et Anna Collard (or Nina Guseva / Anna Collard)
            # on demande si "&"" : "Good Loc & Co"
            char_split = [",", "/", ";", " et "]
            if " & " in user_str:
                print(f"'&' est présent dans {user_str}, s'agit il de plusieurs personnes ?")
                if self.input_choices([False, True]):
                    char_split.append("&")

            if any(sep in user_str for sep in char_split):
                for sep in char_split:
                    user_str = user_str.replace(sep, ",")
                str_split = user_str.split(",")
                first_user = str_split[0].strip()
                # is multi ? il y a un espace (nom prénom) et c'est assez long OU plus de une virgule
                if (" " in first_user and len(first_user) > 3) or len(str_split) > 2:
                    # multi user
                    for u in str_split:
                        user, created = self.get_or_create_user(u)
                        users.append(user)
            # "," est gérée dans get_or_create_user
            if not user:
                user, created = self.get_or_create_user(user_str)
                users.append(user)

            # Is staff
            staffs = []
            for user in users:
                if user.staff_set.count() > 0:
                    staff = user.staff_set.first()
                else:
                    staff, created = Staff.objects.get_or_create(user=user)
                    self.setStats(staff, created)
                staffs.append(staff)

            # search for task
            task_str = credit.split(":")[taskIndex].strip()
            # sometimes Benjamin Griere : Graphisme 3D, Développeur 3D
            tasks = self.getOrCreateMultiInstancesByStr(StaffTask, "label", task_str)

            # HAVE TO
            # ONE user ONE task
            # One user Multi tasks
            # Multi users One task
            # Multi user multi task -> problem
            if len(staffs) == 0 or len(tasks) == 0 or (len(staffs) > 1 and len(tasks) > 1):
                print("*****PROBLEME DE CREDIT ******")
                print(credit)
                continue
            elif len(staffs) == 1 and len(tasks) == 1:
                staff = staffs[0]
                task = tasks[0]
                pst, created = ProductionStaffTask.objects.get_or_create(staff=staff, task=task, production=aw)
                self.setStats(pst, created)
                print(pst)

            elif len(staffs) > 1 and len(tasks) == 1:
                task = tasks[0]
                for staff in staffs:
                    pst, created = ProductionStaffTask.objects.get_or_create(staff=staff, task=task, production=aw)
                    self.setStats(pst, created)
                    print(pst)

            elif len(staffs) == 1 and len(tasks) > 1:
                staff = staffs[0]
                for task in tasks:
                    pst, created = ProductionStaffTask.objects.get_or_create(staff=staff, task=task, production=aw)
                    self.setStats(pst, created)
                    print(pst)

        # END OF FOR CREDITS

    def is_staff_task_reverse(self, credit):
        """
        Détecte si le crédit est dans l'ordre inverse : 'task : staff'
        Normal : 'Staff : Task' (ex: "Haein Cho : réalisatrice, scénario")
        Inverse : 'Task : Staff' (ex: "Graphisme 3D : Benjamin Gruyere")
        """
        if ":" not in credit:
            return False

        credit_staff = credit.split(":", 1)[0].strip()
        credit_task = credit.split(":", 1)[1].strip()

        if not credit_staff or not credit_task:
            return False

        # Nettoyage des caractères non-alphabétiques pour le calcul des ratios
        letters_staff = re.sub(r"[^a-zA-ZÀ-ÿ]", "", credit_staff)
        letters_task = re.sub(r"[^a-zA-ZÀ-ÿ]", "", credit_task)

        # Sécurité si l'un des côtés est vide après nettoyage (ex: uniquement des chiffres)
        if not letters_staff or not letters_task:
            return False

        # Calcul du ratio de majuscules (densité)
        upper_staff = sum(1 for c in letters_staff if c.isupper())
        upper_task = sum(1 for c in letters_task if c.isupper())

        ratio_staff = upper_staff / len(letters_staff)
        ratio_task = upper_task / len(letters_task)

        # Mots-clés métiers typiques
        task_keywords = {
            "montage",
            "réalisation",
            "réalisatrice",
            "réalisateur",
            "scénario",
            "actrice",
            "acteur",
            "décoratrice",
            "décorateur",
            "assistant",
            "assistante",
            "caméra",
            "électricien",
            "électricienne",
            "régie",
            "production",
            "étalonnage",
            "bruitage",
            "mixage",
            "son",
            "animation",
            "vfx",
            "graphisme",
            "infographie",
            "2d",
            "3d",
        }

        # On vérifie si un mot-clé métier se trouve dans le membre de gauche (credit_staff)
        words_left = set(re.findall(r"\b\w+\b", credit_staff.lower()))
        has_task_keyword_on_left = len(words_left.intersection(task_keywords)) > 0

        # Analyse de la capitalisation du premier mot (Title Case)
        # Un nom propre commence généralement par une majuscule.
        first_word_left = re.findall(r"\b\w+\b", credit_staff)
        starts_with_upper_left = first_word_left[0][0].isupper() if first_word_left else False

        # --- PRISE DE DÉCISION (SCORE) ---
        score_reverse = 0

        # Si un mot-clé de tâche est à gauche -> fort indice d'inversion
        if has_task_keyword_on_left:
            score_reverse += 3

        # Si la partie gauche ne commence pas par une majuscule -> fort indice d'inversion
        if not starts_with_upper_left:
            score_reverse += 2

        # Si la densité de majuscules à gauche est très faible par rapport à droite
        if ratio_task > ratio_staff * 1.5:
            score_reverse += 2

        # Si la densité de majuscules à droite est bcp plus forte (ex: "nom" à droite)
        if ratio_task > 0.15 and ratio_staff < 0.08:
            score_reverse += 1.5

        # Déclenchement de l'alerte ou décision automatique
        # Score >= 3 : inversion presque sûre
        if score_reverse >= 3:
            return True
        # Score douteux (ex: égalité de ratio, cas ambigus) -> on demande à l'utilisateur
        elif 1 <= score_reverse < 3:
            print(f"\n[Doute] Le crédit n'est pas clair : '{credit}'")
            print(f"Est-ce que '{credit_staff}' est une tâche / un rôle ?")
            # Remplace par ton système de choix utilisateur : self.input_choices([False, True])
            return self.input_choices([False, True])

        return False

    # SET WEBSITE / SOCIAL NETWORK
    def set_website_or_social_network(self, artist, url):
        """
        Set website and social network for a user
        :param user: Artist instance
        :param urls: str separate by \n
        :return: None
        """
        if not artist:
            print("No artist provided to set website and social network.")
            return

        if not url:
            print("No URLs provided to set website and social network.")
            return

        rs_list = ["facebook", "instagram", "twitter", "linkedin", "vimeo", "youtube", "tiktok", "mastodon"]

        website_type = "Site Web"
        website_url = url.strip()
        # set website
        # ex: Instagram : @camillesauerartk / Site web : aleksandrezharaya.net /
        if ": " in url or " :" in url:
            # split by :
            website_type, website_url = url.split(":", 1)
            website_type = website_type.strip().lower()
            website_url = website_url.strip()

            if website_type in rs_list:
                # not an URL
                if "/" not in website_url:
                    website_url = "https://www.{}.com/{}".format(website_type, website_url.replace("@", ""))

        if "@" in website_url and "http" not in website_url:
            website_type = "instagram"
            website_url = "https://www.instagram.com/{}".format(website_url.replace("@", ""))

        if "http" not in website_url:
            website_url = f"https://{website_url}"

        if any(rs in url for rs in rs_list):
            # get the good one
            for rs in rs_list:
                if rs in url:
                    website_type = rs
                    break

        # find in DB
        artist_website_db = artist.websites.filter(url__icontains=website_url)
        if artist_website_db.exists():
            print(f"Le siteweb existe {website_type}", artist_website_db)
            return

        # test url is valid return code 2XX
        test_url_error = False
        print(f"URL test {website_type} : {website_url} ({url})")
        try:
            response = requests.get(website_url, timeout=50)
            if response.status_code >= 400:
                print(f"Invalid URL: {website_url} (status code: {response.status_code})")
                test_url_error = True

        except requests.RequestException as e:
            print(f"Error accessing URL: {website_url} - {e}")
            test_url_error = True

        if test_url_error:
            print("Le site web n'a pas l'air de répondre, sauvegarde quand-même ?")
            if not self.input_choices([False, True]):
                return

        # instagram -> Instagram
        website_type = website_type.title()
        # create new website
        print("Site web inexistant dans la base, création")
        website, created = Website.objects.get_or_create(
            title_fr=f" {website_type} de {artist} ",
            title_en=f" {artist}' {website_type}",
            language="FR",
            url=website_url,
        )
        artist.websites.add(website)

        artist.save()

    # END WEBSITE / SOCIAL NETWORK

    def get_or_create_user(self, user_str):
        # search user from usersearchutils
        # return user

        first_name, last_name = self.get_first_last_name_from_str(user_str)
        print("firsname:" + first_name)
        print("lastname:" + last_name)

        user = False
        user_search = False
        created = False
        search_list_artist = False
        # are we lucky ?
        # , mean that this is an human in DB
        if "," in user_str:
            user_search = getUserByNames(user_str.split(",")[0], user_str.split(",")[1])
            search_list = getUserByNames(first_name, last_name, True)

        # search by artist : ça arrive (SMITH?!)
        if not user_search:
            user_search = getArtistByNames("", "", user_str)
            search_list_artist = getArtistByNames("", "", user_str, True)
            if user_search and user_search["dist"] >= 0.9:
                artist = user_search["artist"]
                # ça peut etre un DUO ?
                if not artist.user and artist.collectives.all().count() > 1:
                    print("c'est un duo d'artistes, on crée un userStaff pour le collectif")
                    user = False
                    created = False
                    user_search = False
                else:
                    user = artist.user
                    created = False
            else:
                user_search = False
                user = False

        # try user_search if we are not in previous cases
        if not user and not user_search:
            user_search = getUserByNames(first_name, last_name)
            search_list = getUserByNames(first_name, last_name, True)

        # search in DB
        if not user and user_search:
            if user_search["dist"] <= 1:
                print("Recherche d'un User : " + user_str)
                # concat arrays if exist
                list = search_list + search_list_artist if search_list_artist else search_list
                select_with_result_list = self.input_choices(list)
                if select_with_result_list:
                    if "user" in select_with_result_list:
                        user = select_with_result_list["user"]

                    if "artist" in select_with_result_list:
                        artist = select_with_result_list["artist"]
                        user = artist.user
                    created = False
            else:
                user = user_search["user"]
                created = False
                print("KNOW User : " + str(user) + "(kart)  pour " + user_str + " (csv)")
                # print(user_search)

        if not user:
            username = usernamize(first_name, last_name, False)
            try:
                user, created = User.objects.get_or_create(
                    first_name=first_name.title(), last_name=last_name.title(), username=username
                )
            except Exception:
                username = usernamize(first_name, last_name, True)
                user, created = User.objects.get_or_create(
                    first_name=first_name.title(), last_name=last_name.title(), username=username
                )
            self.setStats(user, created)
            print("CREATE User : " + str(user))

        return [user, created]

    def get_or_create_stafftask(self, task_str):
        print("SEARCH FOR TASK : " + task_str)
        # delete spaces
        task_str = task_str.strip()
        # search by query exact and second time filter
        task_query = StaffTask.objects.filter(label__iexact=task_str)
        if task_query.count() == 0:
            task_query = StaffTask.objects.filter(label__unaccent__icontains=task_str)
        # init task
        task = False
        # find more than one ? choose !
        if task_query.count() > 1:
            print("Plusieurs tâches ont été trouvées pour : " + task_str)
            task = self.input_choices(task_query)

        elif task_query.count() == 1:
            task = task_query.first()
        if not task:
            task, created = StaffTask.objects.get_or_create(label=task_str.title())
            self.setStats(task, created)
            print("Création TASK : " + str(task))

        print(task)

        return task

    def get_first_last_name_from_str(self, str):
        str = str.strip()
        sep_list = [",", " "]
        for sep in sep_list:
            if sep in str:
                str_split = str.split(sep, 1)
                first_name = str_split[0]
                last_name = str_split[1]

                return [first_name, last_name]

        return ["", str]

    def getPlace(self, str_place):
        from geopy import distance
        from geopy.geocoders import Nominatim

        from diffusion.models import Place

        # recharche dans les places existant
        print("Place cherche : ", str_place, ".")
        # clear str
        if str_place.strip() == "":
            return None
        # error
        # char_split = [",", "/", ";", " & ", " et ", " - ", "(", ")"]
        char_split = [
            ",",
            "/",
            ";",
            " & ",
            " et ",
            " - ",
        ]
        if any(sep in str_place for sep in char_split):
            # split by comma or "et" or " / "
            for sep in char_split:
                str_place = str_place.replace(sep, ",")

        if "," not in str_place:
            city = country = str(str_place)
        else:
            city, country = str_place.split(",", 1)
        # search place in bdd
        place_search_db = (
            Place.objects.filter(city__unaccent__icontains=city)
            .union(Place.objects.filter(name__unaccent__icontains=city))
            .union(Place.objects.filter(name__unaccent__icontains=str_place))
            .union(Place.objects.filter(name__unaccent__icontains=country))
        )
        place = self.input_choices(place_search_db)
        if place:
            # print( "Trouve dans la base : ", place)
            return place
        else:
            # recherche dans les internets
            geolocator = Nominatim(user_agent="panorama_creation_place")
            location = geolocator.geocode(str_place, language="fr", addressdetails=True, timeout=None)

            if not location:
                # print( "!!!!!!!! Nouvel essaie : ", str_place)
                from functools import partial

                geo = partial(geolocator.geocode, language="fr", addressdetails=True, timeout=None)
                location = geo(str_place)

            if not location:
                # print( "!!!!!_____ Nouvel essaie : ", str_place)
                from functools import partial

                geo = partial(geolocator.geocode, language="fr", addressdetails=True, timeout=None)
                location = geo(country)

            if not location:
                # print( "!!!!!_____ Nouvel essaie : ", str_place)
                from functools import partial

                geo = partial(geolocator.geocode, language="fr", addressdetails=True, timeout=None)
                location = geo(city)

            if not location:
                # print( "!!!!!_____ Nouvel essaie : ", str_place)
                from functools import partial

                geo = partial(geolocator.geocode, language="fr", addressdetails=True, timeout=None)
                location = geo(str_place + ", " + country)

            if location:
                # print( "Trouve dans les internets : ", location)
                # -> si trouve, recherche si pas loin d'une place existante
                places = Place.objects.all()
                for p in places:
                    point1 = (p.latitude, p.longitude)
                    point2 = (location.latitude, location.longitude)
                    if distance.distance(point1, point2).km < 0.1:
                        print("_______ UNE place dans la base a été trouvée : ", p)
                        return p
                print("Pas de place dans la base à proximité, création")

                country_code = location.raw["address"]["country_code"] if location.raw else ""
                # city
                location_city = city
                for key in ["town", "city", "village", "province"]:
                    if key in location.raw["address"]:
                        location_city = location.raw["address"][key]
                        break

                place = Place(
                    name=city,
                    description=city,
                    address=location.address[:255],
                    latitude=location.latitude,
                    longitude=location.longitude,
                    city=location_city[:50],
                    country=country_code,
                )
                print("Place crée : " + str(place))
                place.save()

                return place
        print("/!\\/!\\/!\\/!\\ Rien trouvé ! :", str_place, "\n")
        return None

    def createFileFromUrl(self, url):
        import shutil
        import urllib.request

        from django.core.files import File
        from django.core.files.temp import NamedTemporaryFile

        if not url:
            return None

        if not self.download_images:
            print(f"Skip - téléchargement du media : {url}")
            return None

        img_temp = NamedTemporaryFile(delete=True)

        try:
            # 1. On ouvre la connexion une seule fois
            with urllib.request.urlopen(url, timeout=60) as response:
                # Récupération de la taille depuis les headers (évite de télécharger pour rien)
                file_size_bytes = int(response.headers.get("Content-Length", 0))
                file_size_mb = f"{round(file_size_bytes / (1024 * 1024), 2)}MB" if file_size_bytes else "Inconnue"

                print(f"téléchargement du media ({file_size_mb}) : {url}")

                # 2. On écrit directement dans le fichier temporaire par blocs (Buffer de 16 Ko)
                # Cela consomme 16 Ko de RAM au lieu de 31 Mo !
                shutil.copyfileobj(response, img_temp)

                # On force l'écriture sur le disque
                img_temp.flush()

        except Exception as e:
            print(f"Erreur lors du téléchargement : {e}")
            return None

        # On replace le curseur au début du fichier pour que Django puisse le lire
        img_temp.seek(0)
        return File(img_temp)

    def createMediaFromUrl(self, url, gallery_id):
        from assets.models import Medium

        if url == "":
            return None

        file = self.createFileFromUrl(url)
        name = url.split("/")[-1]

        medium = Medium()
        medium.gallery_id = gallery_id
        medium.picture.save(name[-35:], file, save=True)

        medium.save()

        return medium

    def createGalleryFromArtwork(self, artwork, authors, gallery_type):
        from assets.models import Gallery

        label = f"{gallery_type} - {artwork.title}"
        gallery, created = self.get_or_create(Gallery, {"label": label})

        gallery.description = f"{authors} \n {artwork.title}"
        gallery.description += f"{artwork.polymorphic_ctype.name} {artwork.production_date.year}"
        gallery.description += "\nProduction Le Fresnoy – Studio national des arts contemporains"
        gallery.description += f"\n© {authors}"

        gallery.save()
        return [gallery, created]

    def updateArtistBio(self, artist, bio_fr, bio_en):

        bio_fr = markdownify.markdownify(bio_fr)
        bio_en = markdownify.markdownify(bio_en)

        # print(bio_fr)
        # verify empty bio
        if artist.bio_fr == "":
            # print(artist.__str__() + " : update bio")
            artist.bio_fr = bio_fr
        else:
            # keep infos
            # print(artist.__str__() + " : has an old bio")
            if "<!--" not in artist.bio_fr and bio_fr not in artist.bio_fr:
                # print(artist.__str__() + " : update his old bio")
                artist.bio_fr = "<!--" + artist.bio_fr + "-->\n" + bio_fr

        if artist.bio_en == "":
            artist.bio_en = bio_en
        else:
            if "<!--" not in artist.bio_en and bio_fr not in artist.bio_en:
                artist.bio_en = "<!--" + artist.bio_en + "-->\n" + bio_en

        return artist

    def getStudent(self, name, firstname, email):
        return self.getArtist(name, firstname, email, True)

    def createArtist(self, name, firstname, email):
        username = unidecode.unidecode(firstname[0] + name)
        user, user_created = User.objects.get_or_create(
            username=username, email=email, first_name=firstname, last_name=name
        )
        artist, artist_created = Artist.objects.get_or_create(user=user)

        return artist

    def getArtist(self, idartist):
        searchresult = None
        try:
            return Artist.objects.get(id=idartist)
        except (Artist.MultipleObjectsReturned, Artist.DoesNotExist):
            searchresult = None
        return searchresult

    def getOrCreateProduction(self, artist, title, type):

        production = None
        created = False
        production_year = datetime.datetime.now().year

        if type.lower() == "film":
            production, created = self.get_or_create(
                Film, {"title": title, "production_date": datetime.date(production_year, 1, 1)}
            )

        if type.lower() == "installation":
            production, created = self.get_or_create(
                Installation, {"title": title, "production_date": datetime.date(production_year, 1, 1)}
            )
        if type.lower() == "performance":
            production, created = self.get_or_create(
                Performance, {"title": title, "production_date": datetime.date(production_year, 1, 1)}
            )

        if created:
            production.authors.add(artist)

        self.setStats(production, created)

        return production

    def cleanHTML(self, text):
        markdownify.markdownify(text)

    def slugify(self, text):
        """
        Crée un "slug" à partir d'une chaîne de caractères donnée.

        Un slug est une version conviviale pour les URL, généralement en minuscules,
        avec des espaces remplacés par des tirets et les caractères spéciaux supprimés.

        Args:
            text (str): La chaîne de caractères à "slugifier".

        Returns:
            str: Le slug généré.
        """
        text = str(text)
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
        text = re.sub(r"[^\w\s-]", "", text).strip().lower()
        text = re.sub(r"[-\s]+", "-", text)
        return text
