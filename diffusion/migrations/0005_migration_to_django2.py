# Generated by Django 2.2.6 on 2020-01-08 11:01

import diffusion.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_countries.fields
import multiselectfield.db.fields
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('diffusion', '0004_rename-diffusion_meta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='award',
            name='amount',
            field=models.CharField(blank=True, help_text='money, visibility, currency free', max_length=255),
        ),
        migrations.AlterField(
            model_name='award',
            name='artist',
            # migration was modified : diffusion.models.staff_and_artist_user_limit replaced by diffusion.models.fresnoystaff_and_artist_user_limit
            field=models.ManyToManyField(blank=True, help_text='Staff or Artist', limit_choices_to=diffusion.models.fresnoystaff_and_artist_user_limit, related_name='award', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='award',
            name='event',
            field=models.ForeignKey(limit_choices_to=diffusion.models.main_event_false, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='award', to='production.Event'),
        ),
        migrations.AlterField(
            model_name='award',
            name='giver',
            field=models.ManyToManyField(blank=True, help_text='Who hands the arward', related_name='give_award', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='award',
            name='meta_award',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='award', to='diffusion.MetaAward'),
        ),
        migrations.AlterField(
            model_name='award',
            name='note',
            field=models.TextField(blank=True, help_text='Free note'),
        ),
        migrations.AlterField(
            model_name='award',
            name='sponsor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='award', to='people.Organization'),
        ),
        migrations.AlterField(
            model_name='diffusion',
            name='artwork',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='diffusion', to='production.Artwork'),
        ),
        migrations.AlterField(
            model_name='diffusion',
            name='event',
            field=models.ForeignKey(default=1, limit_choices_to=diffusion.models.main_event_false, on_delete=django.db.models.deletion.PROTECT, to='production.Event'),
        ),
        migrations.AlterField(
            model_name='diffusion',
            name='first',
            field=models.CharField(blank=True, choices=[('WORLD', 'Mondial'), ('INTER', 'International'), ('NATIO', 'National')], help_text='Qualifies the first broadcast', max_length=5, null=True),
        ),
        migrations.AlterField(
            model_name='diffusion',
            name='on_competition',
            field=models.BooleanField(default=False, help_text='IN / OFF : On competion or not'),
        ),
        migrations.AlterField(
            model_name='metaaward',
            name='event',
            field=models.ForeignKey(help_text='Main Event', limit_choices_to=diffusion.models.main_event_true, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='meta_award', to='production.Event'),
        ),
        migrations.AlterField(
            model_name='metaaward',
            name='task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='meta_award', to='production.StaffTask'),
        ),
        migrations.AlterField(
            model_name='metaaward',
            name='type',
            field=models.CharField(choices=[('INDIVIDUAL', 'Individual'), ('GROUP', 'Group'), ('CAREER', 'Career'), ('OTHER', 'Other')], max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='metaevent',
            name='event',
            field=models.OneToOneField(limit_choices_to=diffusion.models.main_event_true, on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name='meta_event', serialize=False, to='production.Event'),
        ),
        migrations.AlterField(
            model_name='metaevent',
            name='genres',
            field=multiselectfield.db.fields.MultiSelectField(choices=[('FILM', 'Films'), ('PERF', 'Performances'), ('INST', 'Installations')], help_text='Global kind of productions shown', max_length=14),
        ),
        migrations.AlterField(
            model_name='metaevent',
            name='important',
            field=models.BooleanField(default=True, help_text='Helps hide minor events'),
        ),
        migrations.AlterField(
            model_name='metaevent',
            name='keywords',
            field=taggit.managers.TaggableManager(blank=True, help_text='Qualifies Festival: digital arts, residency, electronic festival', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
        migrations.AlterField(
            model_name='place',
            name='country',
            field=django_countries.fields.CountryField(default='', max_length=2),
        ),
        migrations.AlterField(
            model_name='place',
            name='zipcode',
            field=models.CharField(blank=True, help_text='Code postal / Zipcode', max_length=10),
        ),
    ]
