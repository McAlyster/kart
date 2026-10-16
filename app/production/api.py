from django.urls import re_path
from tastypie import fields
from tastypie.resources import ALL, ALL_WITH_RELATIONS, ModelResource
from tastypie.utils import trailing_slash

from utils.api import StaffOnlyFileField
from assets.api import GalleryResource
from common.api import BTBeaconResource, WebsiteResource
from diffusion.api import PlaceResource
from people.api import ArtistResource, OrganizationResource, StaffResource

from .models import (
    Artwork,
    Event,
    Film,
    FilmGenre,
    Installation,
    Itinerary,
    OrganizationTask,
    Performance,
    ProductionOrganizationTask,
    ProductionStaffTask,
    StaffTask,
)


class StaffTaskResource(ModelResource):
    class Meta:
        queryset = StaffTask.objects.all()
        resource_name = "production/stafftask"


class ProductionStaffTaskResource(ModelResource):
    class Meta:
        queryset = ProductionStaffTask.objects.all()
        resource_name = "production/productionstafftask"

    staff = fields.ForeignKey(StaffResource, "staff", full=True)
    task = fields.ForeignKey(StaffTaskResource, "task", full=True)


class OrganizationTaskResource(ModelResource):
    class Meta:
        queryset = OrganizationTask.objects.all()
        resource_name = "production/organisationtask"


class ProductionOrganizationTaskResource(ModelResource):
    class Meta:
        queryset = ProductionOrganizationTask.objects.all()
        resource_name = "production/productionorganizationtask"

    organization = fields.ForeignKey(OrganizationResource, "organization", full=True)
    task = fields.ForeignKey(StaffTaskResource, "task", full=True)


class ProductionResource(ModelResource):
    collaborators = fields.ToManyField(ProductionStaffTaskResource, "staff_tasks", full=True)
    partners = fields.ToManyField(ProductionOrganizationTaskResource, "organization_tasks", full=True)
    websites = fields.ToManyField(WebsiteResource, "websites", full=True)


class AbstractArtworkResource(ProductionResource):
    """
    A model shared by Artwork subclasses, required to prevent
    dehydrate from looping because of ArtworkResource being shared
    """

    process_galleries = fields.ToManyField(GalleryResource, "process_galleries", full=True)
    mediation_galleries = fields.ToManyField(GalleryResource, "mediation_galleries", full=True)
    in_situ_galleries = fields.ToManyField(GalleryResource, "in_situ_galleries", full=True)
    press_galleries = fields.ToManyField(GalleryResource, "press_galleries", full=True)
    teaser_galleries = fields.ToManyField(GalleryResource, "teaser_galleries", full=True)

    authors = fields.ToManyField(ArtistResource, "authors")
    beacons = fields.ToManyField(BTBeaconResource, "beacons", full=True)

    def dehydrate(self, bundle):
        bundle.data["type"] = f"{self.Meta.queryset.model.__name__.lower()}"

        return bundle


class ArtworkResource(AbstractArtworkResource):
    class Meta:
        queryset = Artwork.objects.all()
        resource_name = "production/artwork"
        filtering = {
            "authors": ALL_WITH_RELATIONS,
            "events": ALL_WITH_RELATIONS,
            "title": ALL,
            "genres": ALL_WITH_RELATIONS,
        }
        # cache = SimpleCache(timeout=10)

    authors = fields.ToManyField(ArtistResource, "authors", full=True, full_detail=True, full_list=False)
    events = fields.ToManyField("production.api.EventResource", "events", null=True, blank=True, full=False)
    award = fields.ToManyField("diffusion.api.AwardResource", "award", blank=True, full=False)
    production_contract = StaffOnlyFileField("production_contract", null=True, blank=True)

    def dehydrate(self, bundle):
        res_types = (InstallationResource, FilmResource, PerformanceResource)

        for res_type in res_types:
            if isinstance(bundle.obj, res_type.Meta.queryset.model):
                res = res_type()
                rr_bundle = res.build_bundle(obj=bundle.obj, request=bundle.request)
                bundle.data = res.full_dehydrate(rr_bundle).data
                bundle.data["type"] = f"{res_type.Meta.queryset.model.__name__.lower()}"
                break

        return bundle

    def prepend_urls(self):
        return [
            # path(f"<str:resource_name>{self._meta.resource_name})/search{trailing_slash()}",
            re_path(
                r"^(?P<resource_name>%s)/search%s$" % (self._meta.resource_name, trailing_slash()),
                self.wrap_view("get_search"),
                name="api_get_search",
            ),
        ]

    def get_search(self, request, **kwargs):
        return self.get_list(request, **kwargs)


class InstallationGenreResource(ModelResource):
    class Meta:
        queryset = FilmGenre.objects.all()
        resource_name = "production/installationgenre"


class InstallationResource(AbstractArtworkResource):
    class Meta:
        queryset = Installation.objects.all()
        resource_name = "production/installation"
        filtering = {"authors": ALL_WITH_RELATIONS, "events": ALL_WITH_RELATIONS}

    authors = fields.ToManyField(ArtistResource, "authors", full=True, full_detail=True, full_list=False)
    events = fields.ToManyField("production.api.EventResource", "events", blank=True, full=False)
    genres = fields.ToManyField(InstallationGenreResource, "genres", full=True)

    production_contract = StaffOnlyFileField("production_contract", null=True, blank=True)


class FilmGenreResource(ModelResource):
    class Meta:
        queryset = FilmGenre.objects.all()
        resource_name = "production/filmgenre"


class FilmResource(AbstractArtworkResource):
    class Meta:
        queryset = Film.objects.all()
        resource_name = "production/film"
        filtering = {"authors": ALL_WITH_RELATIONS, "events": ALL_WITH_RELATIONS, "genres": ALL_WITH_RELATIONS}

    authors = fields.ToManyField(ArtistResource, "authors", full=True, full_detail=True, full_list=False)
    events = fields.ToManyField("production.api.EventResource", "events", blank=True, full=False)
    genres = fields.ToManyField(FilmGenreResource, "genres", full=True, full_detail=True, full_list=False)
    awards = fields.ToManyField("diffusion.api.AwardResource", "award", blank=True, full=False)

    production_contract = StaffOnlyFileField("production_contract", null=True, blank=True)


class PerformanceResource(AbstractArtworkResource):
    class Meta:
        queryset = Performance.objects.all()
        resource_name = "production/performance"
        filtering = {"authors": ALL_WITH_RELATIONS, "events": ALL_WITH_RELATIONS, "genres": ALL_WITH_RELATIONS}

    authors = fields.ToManyField(ArtistResource, "authors", full=True, full_detail=True, full_list=False)

    events = fields.ToManyField("production.api.EventResource", "events", blank=True, full=False)

    production_contract = StaffOnlyFileField("production_contract", null=True, blank=True)


class EventResource(ProductionResource):
    class Meta:
        queryset = Event.objects.all()
        resource_name = "production/event"

    place = fields.ForeignKey(PlaceResource, "place", full=True, null=True)

    installations = fields.ToManyField(
        InstallationResource, "installations", full=True, full_list=False, full_detail=True
    )

    films = fields.ToManyField(FilmResource, "films", full=True, full_list=False, full_detail=True)

    performances = fields.ToManyField(PerformanceResource, "performances", full=True, full_list=False, full_detail=True)

    subevents = fields.ToManyField("production.api.EventResource", "subevents", blank=True, full=False)


class ItineraryResource(ModelResource):
    class Meta:
        queryset = Itinerary.objects.all()
        resource_name = "production/itinerary"

    artworks = fields.ToManyField(
        ArtworkResource, "artworks", use_in=["detail"], full_detail=True, full_list=False, full=True, blank=True
    )

    gallery = fields.ToManyField(GalleryResource, "gallery", use_in=["detail"], full_detail=True, full=True, blank=True)


class ExhibitionResource(EventResource):
    class Meta:
        queryset = Event.objects.filter(type="EXHIB")
        resource_name = "production/exhibition"

    itineraries = fields.ToManyField(ItineraryResource, "itineraries", full_list=False, full_detail=True)
