from django.core.management.base import BaseCommand

from school.models import AdminStudentApplication, Student, StudentApplicationSetup


class Command(BaseCommand):
    help = "OnBoarding New Student"

    def add_arguments(self, parser):
        # Args
        parser.add_argument("-i", "--campaign_id", type=int, help="Campaign Id", required=False)
        parser.add_argument("--novalidation", action="store_true", help="No validation required")

    def handle(self, *args, **options):

        campaign_id = options["campaign_id"]
        novalidation = options["novalidation"]

        if campaign_id:
            campaign = StudentApplicationSetup.objects.get(id=campaign_id)
        else:
            campaign = StudentApplicationSetup.objects.filter(is_current_setup=True).last()

        candidatures = AdminStudentApplication.objects.filter(application__campaign=campaign, selected=True)
        candidatures = candidatures.order_by(
            "application__artist__nickname",
            "application__artist__user__last_name",
        )
        promo = campaign.promotion

        # valid promotion
        str_question = f"Les étudiants serons ajoutés à la promo  : {promo.name}   ? [y/n]  -  "
        valid = input(str_question) if not novalidation else "y"

        if valid != "y":
            print("Aucun candidat n'a rejoint la promotion")
            return

        # valid campaign
        str_question = f"La campagne sélectionnée est : {campaign.candidature_date_end.year}  ( {campaign.promotion.name} ) et comporte {candidatures.count()} candidats ? [y/n]  -  "
        valid = input(str_question) if not novalidation else "y"

        if valid != "y":
            print("Aucun candidat n'a rejoint la promotion")
            return

        for admin_app in candidatures:
            artist = admin_app.application.artist
            user = artist.user

            # valid user
            str_question = f"Ajouter {artist} ({user.email}) à la promo {campaign.promotion.name} ? [y/n]  -  "
            valid = input(str_question) if not novalidation else "y"

            if valid == "y":
                student, created = Student.objects.get_or_create(
                    user=user,
                    artist=artist,
                    promotion=promo,
                    number=admin_app.application.current_year_application_count,
                )
                print(f"{student} : {created}")
            else:
                print("skip")
        print(f"Le nombre d'étudiant·es dans la promo {promo} est de  {promo.student_set.count()} ")
        print("FIN")
