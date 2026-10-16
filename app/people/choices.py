from django.conf.global_settings import LANGUAGES
from django.utils.translation import gettext_lazy as _

GENDER_CHOICES = (
    ("M", "Male"),
    ("F", "Female"),
    ("T", "Transgender"),
    ("O", "Other"),
)

EXTRA_LANGUAGES = (("zh", _("Chinese")),)
CUSTOM_LANGUAGES = [(code, _(name)) for code, name in LANGUAGES] + list(EXTRA_LANGUAGES)

CUSTOM_LANGUAGES = tuple(sorted(list(LANGUAGES) + list(EXTRA_LANGUAGES), key=lambda x: x[1]))
