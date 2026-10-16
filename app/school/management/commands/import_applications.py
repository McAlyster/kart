import csv
import random
import shutil
import urllib

from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.core.management.base import BaseCommand
from django.db import transaction

from people.models import Artist, FresnoyProfile
from people.utils.artist_tools import getArtistByNames
from school.models import AdminStudentApplication, Promotion, StudentApplication, StudentApplicationSetup

base_medias_url = ""


class Command(BaseCommand):
    help = "Import candidature to CSV (export with export_selected_applications)"

    def add_arguments(self, parser):
        # Args
        requiredNamed = parser.add_argument_group("required named arguments")
        requiredNamed.add_argument("-i", "--input", help="Input file name", required=True)
        requiredNamed.add_argument("-m", "--mediasurl", help="medias base url", required=True)
        # optional args
        optionalNamed = parser.add_argument_group("optional named arguments")
        optionalNamed.add_argument("-d", "--dryrun", help="Dry run", action="store_true", required=False)

    def handle(self, *args, **options):

        fichier_csv = options["input"]
        medias_url = options["mediasurl"]
        dry_run = options["dryrun"]

        global base_medias_url
        base_medias_url = medias_url
        try:
            with transaction.atomic():
                run(fichier_csv)

                if dry_run:
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


def populateAPI(data):

    # get user / artist
    artist = find_artist(
        data["application__artist__user__first_name"],
        data["application__artist__user__last_name"],
        data["application__artist__nickname"],
    )
    # create
    if not artist:
        user = get_or_create_user(data)
        artist = get_or_create_artist(user, data)
    else:
        user = artist.user

    # print(user, user.id)

    # get campaign
    campaign = get_or_create_campaign(data)

    # get application
    application = get_or_create_application(artist, campaign, data)

    # get admin application
    admin_application = get_or_create_admin_application(application, data)

    print(admin_application)


def get_or_create(model, attr, save=True):
    # get (or create) object with attributes (without exeption)
    created = False
    try:
        instance = model.objects.get(**attr)
    except Exception:
        instance = model(**attr)
        created = True
        # save
        if save:
            instance.save()
    return [instance, created]


def createFileFromUrl(url):
    # dowload file and returne File instance
    if url == "":
        return False

    print("téléchargement du media : (...)" + url[-35:])

    img_temp = NamedTemporaryFile(delete=True)
    try:
        # ouvre la connexion une seule fois
        with urllib.request.urlopen(url, timeout=60) as response:
            # Récupération de la taille depuis les headers
            file_size_bytes = int(response.headers.get("Content-Length", 0))
            file_size_mb = f"{round(file_size_bytes / (1024 * 1024), 2)}MB" if file_size_bytes else "Inconnue"

            print(f"téléchargement du media ({file_size_mb}) : {url}")

            # écrit directement dans le fichier temporaire par blocs (Buffer de 16 Ko)
            # Cela consomme 16 Ko de RAM
            shutil.copyfileobj(response, img_temp)

            # On force l'écriture sur le disque
            img_temp.flush()

    except Exception as e:
        print(f"Erreur lors du téléchargement : {e}")
        return False  # Retourne False en cas d'erreur

    return File(img_temp)


def populate_instance(fields, instance, data, data_prefix):

    media_fields = ["FieldFile", "ImageFieldFile"]

    for field_name in fields:
        # val
        field = getattr(instance, field_name)
        new_value = data[data_prefix + field_name]

        # error with int
        if "position" in field_name and new_value != "":
            new_value = int(float(new_value))

        # set value if different and empty and not deathdate (to avoid overwriting deathdate with empty value)
        if str(new_value) != "" and str(field) != str(new_value) and field_name != "deathdate":
            # instance is File
            if field.__class__.__name__ in media_fields:
                # get file
                file = createFileFromUrl(base_medias_url + new_value)
                # save
                if file:
                    field.save(new_value[-35:], file, save=True)
            else:
                setattr(instance, field_name, new_value)
    # save user
    instance.save()
    return instance


def find_artist(first_name, last_name, nickname):

    artist_name = nickname if nickname else f"{first_name} {last_name}"
    artist_search = getArtistByNames(first_name, last_name, nickname)

    if artist_search and artist_search["dist"]:
        ask = input(
            "Est-ce la même personne ? (db) {}  <-> {} (csv) (y or n) ? ".format(artist_search["artist"], artist_name)
        )
        if "y" in ask:
            return artist_search["artist"]
        else:
            return False

    return False


def get_or_create_user(data):

    # set unsername
    username = data["application__artist__user__username"]
    # change username to prevent crash of (like Alexandra Melot  <-> Anatole Mélot)
    user = User.objects.filter(username=data["application__artist__user__username"]).first()
    if user:
        if (
            user.first_name != data["application__artist__user__first_name"]
            or user.last_name != data["application__artist__user__last_name"]
            or user.email != data["application__artist__user__email"]
        ):
            username = username + "_" + random.randint(1, 9999).__str__()

    # create user
    user, created = get_or_create(
        User,
        {"username": username, "email": data["application__artist__user__email"]},
    )
    print("User created : " + str(created), user.id)
    # force desactive user (will save after populate_instance)
    user.is_active = False
    # populate user
    user = populate_instance(
        ["first_name", "last_name", "password", "email"], user, data, "application__artist__user__"
    )

    # get profile
    profile, created = get_or_create(FresnoyProfile, {"user": user})
    # print("Profile created : " + str(created))
    profile_fields_to_remove = [
        "id",
        "user",
        "social_insurance_number",
        "homeland_address",
        "homeland_zipcode",
        "homeland_town",
        "homeland_country",
        "family_status",
        "mother_tongue",
        "other_language",
    ]
    profile_fields = [
        field.name for field in FresnoyProfile._meta.get_fields() if field.name not in profile_fields_to_remove
    ]
    profile = populate_instance(
        profile_fields,
        profile,
        data,
        "application__artist__user__profile__",
    )

    return user


def get_or_create_artist(user, data):

    artist, created = get_or_create(
        Artist,
        {
            "user": user,
        },
    )

    artist_fields = ["nickname"]
    artist = populate_instance(
        artist_fields,
        artist,
        data,
        "application__artist__",
    )
    return artist


def get_or_create_campaign(data):

    promotion, created = get_or_create(
        Promotion,
        {
            "starting_year": data["application__campaign__promotion__starting_year"],
            "ending_year": data["application__campaign__promotion__ending_year"],
        },
    )
    promotion = populate_instance(
        [
            "name",
        ],
        promotion,
        data,
        "application__campaign__promotion__",
    )

    campaign, created = get_or_create(
        StudentApplicationSetup,
        {
            "promotion": promotion,
        },
        save=False,
    )
    campaign = populate_instance(
        [
            "name",
            "candidature_date_start",
            "candidature_date_end",
            "candidatures_url",
            "reset_password_url",
            "recover_password_url",
            "authentification_url",
            "video_service_url",
        ],
        campaign,
        data,
        "application__campaign__",
    )

    return campaign


def get_or_create_application(artist, campaign, data):
    application, created = get_or_create(
        StudentApplication,
        {"campaign": campaign, "artist": artist},
    )
    application_fields_to_remove = [
        "id",
        "administration",
        "artist",
        "campaign",
        # "identity_card",
        "first_time",
        "last_applications_years",
        "remote_interview",
        "remote_interview_type",
        "remote_interview_info",
        # "master_degree",
        "experience_justification",
        "reference_letter",
        "doctorate_interest",
        "cursus_justifications",  # keep next year
    ]
    application_fields = [
        field.name for field in StudentApplication._meta.get_fields() if field.name not in application_fields_to_remove
    ]
    application = populate_instance(application_fields, application, data, "application__")

    return application


def get_or_create_admin_application(application, data):

    admin_application, created = get_or_create(
        AdminStudentApplication,
        {
            "application": application,
        },
    )

    admin_app_fields_to_remove = [
        "id",
        "application",
    ]
    admin_app_fields = [
        field.name
        for field in AdminStudentApplication._meta.get_fields()
        if field.name not in admin_app_fields_to_remove
    ]
    admin_application = populate_instance(
        admin_app_fields,
        admin_application,
        data,
        "",
    )

    return admin_application


def run(file):

    with open(file, "r") as csvfile:
        lecteur_csv = csv.DictReader(csvfile)
        for row in lecteur_csv:
            populateAPI(row)
    print("Fin")
