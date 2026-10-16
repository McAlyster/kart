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
    username = None  # reset
    email = None  # reset

    # On redéfinit un champ unique pour la saisie (identifiant ou email)
    login = serializers.CharField(required=True, allow_blank=False)

    def validate(self, attrs):
        login_value = attrs.get("login")
        password = attrs.get("password")

        if login_value and password:
            # Vérifier si la valeur saisie est un e-mail
            if "@" in login_value:
                try:
                    user = User.objects.get(email__iexact=login_value)
                    print(user)
                    attrs["username"] = user.username  # dj_rest_auth a besoin du username
                except User.DoesNotExist:
                    pass
            else:
                attrs["username"] = login_value

        # Nettoyage des champs inutiles pour la validation
        attrs.pop("login", None)

        return super().validate(attrs)
