import pytest

from django.urls import reverse

from utils.tests.utils import obtain_jwt_token


@pytest.mark.django_db
class TestJWTToken:
    @pytest.mark.parametrize(
        'user_role, expected', [
            (None, 400),
            ('user', 200),
            ('admin', 200),
            ('inactive_user', 400),
            ('joker', 400),
        ]
    )
    def test_raw_obtain_jwt_token(self, client, user_role, expected, user, admin, joker, inactive_user):
        url = reverse('obtain-jwt-token')
        data = {}
        if user_role:
            requestor = locals().get(user_role)
            data['username'] = requestor.username
            data['password'] = 'p4ssw0rd'

        response = client.post(url, data=data)

        assert response.status_code == expected
        if expected == 200:
            assert 'token' in response.json()

    def test_obtain_jwt_token(self, client, user):
        assert obtain_jwt_token(user)
