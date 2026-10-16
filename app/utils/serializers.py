from rest_framework import serializers

class StaffOnlyFileField(serializers.FileField):
    """
    Champ fichier qui renvoie None si l'utilisateur courant n'est pas staff.
    """
    def to_representation(self, value):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_staff:
            return None
        return super().to_representation(value)