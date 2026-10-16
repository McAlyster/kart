from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from .models import Film

from people.choices import CUSTOM_LANGUAGES as LANGUAGES
from production.choices import AUDIO_FEATURE_CHOICES


class FilmAdminForm(forms.ModelForm):
    languages_vo = forms.MultipleChoiceField(
        choices=LANGUAGES, required=False, widget=FilteredSelectMultiple("Langues VO", is_stacked=False)
    )
    languages_subtitles = forms.MultipleChoiceField(
        choices=LANGUAGES, required=False, widget=FilteredSelectMultiple("Langues VO", is_stacked=False)
    )
    shooting_format = forms.MultipleChoiceField(
        choices=Film._meta.get_field("shooting_format").base_field.choices,
        widget=forms.SelectMultiple(attrs={"class": "grp-chosen"}),
        required=False,
        label="Format de tournage",
    )
    aspect_ratio = forms.MultipleChoiceField(
        choices=Film._meta.get_field("aspect_ratio").base_field.choices,
        widget=forms.SelectMultiple(attrs={"class": "grp-chosen"}),
        required=False,
        label="Aspect Ratio",
    )
    process = forms.MultipleChoiceField(
        choices=Film._meta.get_field("process").base_field.choices,
        widget=forms.SelectMultiple(attrs={"class": "grp-chosen"}),
        required=False,
        label="Process",
    )
    languages_audio = forms.MultipleChoiceField(
        choices=Film._meta.get_field("languages_audio").base_field.choices,
        required=False,
        widget=FilteredSelectMultiple("Pistes Audio Export", is_stacked=False),
    )
    audio_features = forms.MultipleChoiceField(
        choices=AUDIO_FEATURE_CHOICES,
        required=False,
        widget=FilteredSelectMultiple("Caractéristiques sonores", is_stacked=False),
    )

    class Meta:
        model = Film
        fields = "__all__"
