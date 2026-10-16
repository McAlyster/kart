import pytest

from production.tests.conftest import *  # NOQA
from utils.tests.conftest import *  # NOQA

from . import factories


@pytest.fixture
def place(db_ready):
    return factories.PlaceFactory()


@pytest.fixture
def meta_award(db_ready):
    return factories.MetaAwardFactory()


@pytest.fixture
def award(db_ready, film):
    return factories.AwardFactory(artwork=[film])


@pytest.fixture
def meta_event(db_ready):
    return factories.MetaEventFactory()


@pytest.fixture
def diffusion(db_ready):
    return factories.DiffusionFactory()
