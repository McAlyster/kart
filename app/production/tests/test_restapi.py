
from django.test import TestCase
from django.urls import reverse

from utils.tests.factories import UserFactory

from .factories import ArtworkFactory, TagFactory


class KeywordsEndPoint(TestCase):
    """
    Tests concernants le endpoint des User
    """

    def setUp(self):
        self.keyword = TagFactory()

    def tearDown(self):
        pass

    def test_list(self):
        """
        Test list of user
        """
        url = reverse("tag-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

class ArtworkEndPoint(TestCase):
    """
    Tests concernants le endpoint des User
    """

    def setUp(self):
        self.artwork = ArtworkFactory(production_contract="path/to/file.pdf")
        self.user_staff = UserFactory(is_staff=True)

    def tearDown(self):
        pass

    def test_list(self):
        """
        Test list of user
        """
        url = reverse("artwork-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_ressource(self):
        """
        Test acces detail of artwork
        """
        url = reverse("artwork-detail", kwargs={"pk": self.artwork.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("path/to/file.pdf", response.data["productionContract"])

    def test_ressource_auth(self):
        """
        Test acces detail of artwork
        """
        self.client_auth.force_authenticate(user=self.user_staff)

        url = reverse("artwork-detail", kwargs={"pk": self.artwork.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("path/to/file.pdf", response.data["productionContract"])
