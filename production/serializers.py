from rest_framework import serializers

from .models import (
    Film, FilmGenre, Installation,
    Performance, InstallationGenre,
    Event, Itinerary, StaffTask, OrganizationTask,
    ProductionStaffTask, ProductionOrganizationTask,
)
from people.serializers import StaffSerializer


class OrganizationTaskSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = OrganizationTask


class StaffTaskSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = StaffTask
        fields = ('label', 'description')


class ProductionStaffTaskSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ProductionStaffTask
        fields = ('staff', 'task')

    staff = StaffSerializer()
    task = StaffTaskSerializer()


class PartnerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ProductionOrganizationTask
        fields = ('organization', 'task')


class InstallationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Installation
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True)
    partners = PartnerSerializer(source='organization_tasks', many=True)


class FilmSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Film
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True)
    partners = PartnerSerializer(source='organization_tasks', many=True)


class EventSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Event
        exclude = ('polymorphic_ctype',)

    partners = PartnerSerializer(source='organization_tasks', many=True)


class PerformanceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Performance
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True)
    partners = PartnerSerializer(source='organization_tasks', many=True)


class FilmGenreSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = FilmGenre


class ItinerarySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Itinerary


class InstallationGenreSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = InstallationGenre