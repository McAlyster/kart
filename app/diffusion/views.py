from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets

from .models import Award, Diffusion, MetaAward, MetaEvent, Place
from .serializers import AwardSerializer, DiffusionSerializer, MetaAwardSerializer, MetaEventSerializer, PlaceSerializer


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class AwardViewSet(viewsets.ModelViewSet):
    queryset = Award.objects.all()
    serializer_class = AwardSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class MetaAwardViewSet(viewsets.ModelViewSet):
    queryset = MetaAward.objects.all()
    serializer_class = MetaAwardSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class MetaEventViewSet(viewsets.ModelViewSet):
    queryset = MetaEvent.objects.all()
    serializer_class = MetaEventSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class DiffusionViewSet(viewsets.ModelViewSet):
    queryset = Diffusion.objects.all()
    serializer_class = DiffusionSerializer
    filter_backends = (filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filterset_fields = ("event__parent_event__meta_event__important", "artwork", "event")
