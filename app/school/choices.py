from django.db import models
from django.utils.translation import gettext_lazy as _


class StudyProgram(models.TextChoices):
    CINEMA_NEW_WRITING = "cinema", _("Filière Nouvelles Écritures du cinéma et de l'image en mouvement")
    HYBRID_FORMS = "hybrid", _("Filière Formes hybrides et technologies émergentes")
