from django.db import models

from people.models import Organization

class Place(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    organization = models.ForeignKey(Organization, related_name='places')

    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.organization)

class Award(models.Model):
    """
    Awards given to artworks & such.
    """
    pass
