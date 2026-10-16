from tastypie.resources import ModelResource

from .models import BTBeacon, Website


class BTBeaconResource(ModelResource):
    class Meta:
        queryset = BTBeacon.objects.all()


class WebsiteResource(ModelResource):
    class Meta:
        queryset = Website.objects.all()
