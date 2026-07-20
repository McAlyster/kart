
from django.test import TestCase

from django.urls import reverse
from .factories import TagFactory


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
        url = reverse('tag-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
