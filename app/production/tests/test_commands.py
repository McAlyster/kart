import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from people.tests.factories import ArtistFactory
from production.tests.factories import (
    ArtworkFactory,
)


@pytest.mark.django_db
def test_import_catalog(monkeypatch):
    "simple TEST Command: import_catalog"

    # remove 'clear' terminal
    monkeypatch.setattr("os.system", lambda cmd: 0)  # neutralise juste clear
    result = call_command("import_catalog", "--path_to_csv", "coucou.csv")
    # not really tested
    assert result is None


@pytest.mark.django_db
@pytest.mark.unaccent
def test_set_artwork_credits(monkeypatch):
    "simple TEST Command: set_artwork_credits"

    artist = ArtistFactory(
        nickname="Francesco Massaro", user=User.objects.get_or_create(first_name="Francesco", last_name="Massaro")[0]
    )
    artist.save()

    artwork = ArtworkFactory(title="Le Coucou", authors=[artist])
    artwork.save()

    # put Michel Serrault in the credits of the artwork
    responses = iter(
        [
            "Michel Serrault: Actor",  # Ligne 1 du texte de crédits
            "",  # Ligne vide -> valide la fin de multiline_input()
            "Le Coucou",  # Recherche dans searchArtwork() -> input("L'œuvre : ")
            "0",  # Sélection de l'index dans input_choices()
            "n",  # Validation finale ou confirmation (question : Créer un autre ? )
        ]
    )

    # Interception de la fonction builtin input()
    monkeypatch.setattr("builtins.input", lambda *args: next(responses))

    # call the command
    call_command("set_artwork_credits")
    artwork.refresh_from_db()

    assert artwork.collaborators.count() > 0
