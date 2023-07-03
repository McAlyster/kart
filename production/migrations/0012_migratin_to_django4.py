# Generated by Django 4.1 on 2023-06-23 05:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0006_languagesfield_newversion'),
        ('common', '0003_migration_to_django2'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('production', '0011_ordering_productionorganizationtask'),
    ]

    operations = [
        migrations.AlterField(
            model_name='artwork',
            name='authors',
            field=models.ManyToManyField(related_name='%(class)ss', to='people.artist'),
        ),
        migrations.AlterField(
            model_name='artwork',
            name='beacons',
            field=models.ManyToManyField(blank=True, related_name='%(class)ss', to='common.btbeacon'),
        ),
        migrations.AlterField(
            model_name='production',
            name='collaborators',
            field=models.ManyToManyField(blank=True, related_name='%(class)s', through='production.ProductionStaffTask', to='people.staff'),
        ),
        migrations.AlterField(
            model_name='production',
            name='partners',
            field=models.ManyToManyField(blank=True, related_name='%(class)s', through='production.ProductionOrganizationTask', to='people.organization'),
        ),
        migrations.AlterField(
            model_name='production',
            name='polymorphic_ctype',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_%(app_label)s.%(class)s_set+', to='contenttypes.contenttype'),
        ),
    ]