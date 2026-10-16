from tastypie import fields

class StaffOnlyFileField(fields.FileField):
    """
    Champ qui ne renvoie sa valeur que si l'utilisateur est staff, 
    sinon renvoie None.
    """
    def dehydrate(self, bundle, for_list=None):
        if not bundle.request.user or not bundle.request.user.is_staff:
            return None
        return super().dehydrate(bundle, for_list=for_list)
