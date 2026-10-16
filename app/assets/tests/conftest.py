import pytest

from school.tests.conftest import *  # NOQA
from utils.tests.conftest import *  # NOQA

from . import factories


@pytest.fixture
def gallery(db_ready):
    return factories.GalleryFactory()


@pytest.fixture
def medium(db_ready):
    return factories.MediumFactory()
