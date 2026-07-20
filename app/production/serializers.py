from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer
from taggit.serializers import (TagListSerializerField,
                                TaggitSerializer)
from taggit.models import Tag

from .models import (
    Film, FilmGenre, Installation,
    Performance, InstallationGenre,
    Event, Itinerary, StaffTask, OrganizationTask,
    ProductionStaffTask, ProductionOrganizationTask,
    Artwork
)
from people.serializers import StaffSimpleSerializer


class OrganizationTaskSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = OrganizationTask
        fields = '__all__'


class StaffTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffTask
        fields = ('label', 'description')


class ProductionStaffTaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductionStaffTask
        fields = ('url', 'staff', 'task')

    staff = StaffSimpleSerializer()
    task = StaffTaskSerializer()


class PartnerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ProductionOrganizationTask
        fields = ('organization', 'task')


class ProductionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Artwork
        fields = ('url', 'title',)


class ArtworkSerializer(TaggitSerializer, serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Artwork
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True, read_only=True)
    partners = PartnerSerializer(source='organization_tasks', many=True, read_only=True)
    diffusion = serializers.HyperlinkedRelatedField(view_name='diffusion-detail',
                                                    read_only=True,
                                                    many=True)
    award = serializers.HyperlinkedRelatedField(view_name='award-detail', read_only=True, many=True)
    keywords = TagListSerializerField()


class InstallationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Installation
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True, read_only=True)
    partners = PartnerSerializer(source='organization_tasks', many=True, read_only=True)
    diffusion = serializers.HyperlinkedRelatedField(view_name='diffusion-detail',
                                                    read_only=True,
                                                    many=True)
    award = serializers.HyperlinkedRelatedField(view_name='award-detail', read_only=True, many=True)
    keywords = TagListSerializerField()


class FilmSerializer(TaggitSerializer, serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Film
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True, read_only=True,)
    partners = PartnerSerializer(source='organization_tasks', many=True, read_only=True)
    diffusion = serializers.HyperlinkedRelatedField(view_name='diffusion-detail',
                                                    read_only=True,
                                                    many=True)
    award = serializers.HyperlinkedRelatedField(view_name='award-detail', read_only=True, many=True)
    keywords = TagListSerializerField()


class EventSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Event
        exclude = ('polymorphic_ctype',)

    partners = PartnerSerializer(source='organization_tasks', many=True, read_only=True)
    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True, read_only=True,)
    parent_event = serializers.HyperlinkedRelatedField(view_name='event-detail', read_only=True, many=True)
    meta_award = serializers.HyperlinkedRelatedField(view_name='award-detail', read_only=True, many=True)
    meta_event = serializers.HyperlinkedRelatedField(view_name='metaevent-detail',
                                                     read_only=True)


class PerformanceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Performance
        exclude = ('polymorphic_ctype',)

    collaborators = ProductionStaffTaskSerializer(source='staff_tasks', many=True, read_only=True)
    partners = PartnerSerializer(source='organization_tasks', many=True)
    diffusion = serializers.HyperlinkedRelatedField(view_name='diffusion-detail',
                                                    read_only=True,
                                                    many=True)
    award = serializers.HyperlinkedRelatedField(view_name='metaaward-detail', read_only=True, many=True)
    keywords = TagListSerializerField()


class ArtworkPolymorphicSerializer(PolymorphicSerializer):
    resource_type_field_name = 'type'
    model_serializer_mapping = {
        Artwork: ArtworkSerializer,
        Film: FilmSerializer,
        Installation: InstallationSerializer,
        Performance: PerformanceSerializer
    }


class FilmGenreSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = FilmGenre
        fields = '__all__'


class ItinerarySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Itinerary
        fields = '__all__'


class InstallationGenreSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = InstallationGenre
        fields = '__all__'


class KeywordsSerializer(TaggitSerializer, serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'


class ProductionTaskSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ProductionStaffTask
        fields = ('production', 'task')

    production = ProductionSerializer()
    task = StaffTaskSerializer()
