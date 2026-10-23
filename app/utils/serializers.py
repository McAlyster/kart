from rest_framework import serializers

from dj_rest_auth.serializers import LoginSerializer
from django.contrib.auth import get_user_model


class StaffOnlyFileField(serializers.FileField):
    """
    Champ fichier qui renvoie None si l'utilisateur courant n'est pas staff.
    """

    def to_representation(self, value):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_staff:
            return None
        return super().to_representation(value)


User = get_user_model()


class EmailOrUsernameLoginSerializer(LoginSerializer):
    username = serializers.CharField(required=False, allow_blank=False)
    email = serializers.EmailField(required=False, allow_blank=False)
    login = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        login_value = attrs.get("login") or attrs.get("email") or attrs.get("username")
        password = attrs.get("password")

        if login_value and password:
            if "@" in login_value:
                try:
                    user = User.objects.get(email__iexact=login_value)
                    attrs["username"] = user.username
                except User.DoesNotExist:
                    pass
            else:
                attrs["username"] = login_value

        # Nettoyage des champs alternatifs pour ne garder que username et password pour le parent
        attrs.pop("login", None)
        attrs.pop("email", None)

        return super().validate(attrs)
