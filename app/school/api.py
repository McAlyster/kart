# -*- coding: utf-8 -*-

from django.urls import re_path
from django.db.models import Q
from tastypie import fields
from tastypie.resources import ModelResource
from tastypie.resources import ALL, ALL_WITH_RELATIONS
from tastypie.utils import trailing_slash

# from tastypie.authorization import DjangoAuthorization

from people.api import ArtistResource
from .models import Promotion, Student, StudentApplication

from assets.api import GalleryResource

# 03june26
from tastypie.authorization import Authorization
from tastypie.exceptions import Unauthorized


class PromotionResource(ModelResource):
    class Meta:
        queryset = Promotion.objects.all()
        resource_name = "school/promotion"
        ordering = ["starting_year"]


class StudentResource(ArtistResource):
    class Meta:
        queryset = Student.objects.all()
        resource_name = "school/student"
        # ordering = [
        #     "artist",
        #     "user",
        # ]

        ordering = [
            "artist",
        ]
        #  filtering = {
        #      "artist": ALL_WITH_RELATIONS,
        #      "user": ALL_WITH_RELATIONS,
        #      "user__last_name__istartswith": ALL_WITH_RELATIONS,
        #      "promotion": ALL,
        #  }

        filtering = {
            "artist": ALL_WITH_RELATIONS,
            "promotion": ALL,
        }
        # fields = ["id", "number", "promotion", "graduate", "user", "artist"]
        fields = ["id", "number", "promotion", "graduate", "artist"]

    promotion = fields.ForeignKey(PromotionResource, "promotion")
    artist = fields.ForeignKey(ArtistResource, "artist", full=True)

    # BUG Error (why?) user__last_name__istartswith
    # "The 'last_name' field does not support relations"
    def build_filters(self, filters=None, ignore_bad_filters=False):
        # turn off error : ignore_bad_filters et True
        return super(StudentResource, self).build_filters(filters, ignore_bad_filters=True)

    # override user__last_name__istartswith query
    def apply_filters(self, request, applicable_filters):
        base_object_list = super(StudentResource, self).apply_filters(request, applicable_filters)
        # override
        query = request.GET.get("user__last_name__istartswith", None)
        if query:
            qset = Q(user__last_name__istartswith=query)
            base_object_list = base_object_list.filter(qset).distinct()

        return base_object_list

    # end of Bug Error

    def prepend_urls(self):
        return [
            re_path(
                r"^(?P<resource_name>%s)/search%s$" % (self._meta.resource_name, trailing_slash()),
                self.wrap_view("get_search"),
                name="api_get_search",
            ),
        ]

    def get_search(self, request, **kwargs):
        return self.get_list(request, **kwargs)


class StudentApplicationAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        user = bundle.request.user

        if not user or not user.is_authenticated:
            return object_list.none()

        if user.is_staff:
            return object_list

        return object_list.filter(artist__user=user)

    def read_detail(self, object_list, bundle):
        user = bundle.request.user
        obj = bundle.obj

        if not user or not user.is_authenticated:
            raise Unauthorized("Authentication required")

        if user.is_staff:
            return True

        return obj.artist and obj.artist.user_id == user.id

    def create_detail(self, object_list, bundle):
        user = bundle.request.user
        return bool(user and user.is_authenticated)

    def update_detail(self, object_list, bundle):
        user = bundle.request.user
        obj = bundle.obj

        if not user or not user.is_authenticated:
            raise Unauthorized("Authentication required")

        if user.is_staff:
            return True

        return obj.artist and obj.artist.user_id == user.id

    def delete_detail(self, object_list, bundle):
        user = bundle.request.user
        return bool(user and user.is_staff)


class StudentApplicationResource(ModelResource):
    class Meta:
        queryset = StudentApplication.objects.all()
        resource_name = "school/application"
        ordering = ["created_on"]
        # no authorization for Anonymous user
        # authorization = DjangoAuthorization()
        authorization = StudentApplicationAuthorization()

    artist = fields.ForeignKey(ArtistResource, "artist")
    administrative_galleries = fields.ToManyField(GalleryResource, "administrative_galleries", full=True, null=True)
    artwork_galleries = fields.ToManyField(GalleryResource, "artwork_galleries", full=True, null=True)
