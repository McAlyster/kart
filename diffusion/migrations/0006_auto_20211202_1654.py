# Generated by Django 3.1.13 on 2021-12-02 15:54

import diffusion.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('diffusion', '0005_migration_to_django2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='award',
            name='artist',
            # migration was modified : diffusion.models.staff_and_artist_user_limit replaced by diffusion.models.fresnoystaff_and_artist_user_limit
            field=models.ManyToManyField(blank=True, help_text='FresnoyStaff or Artist', limit_choices_to=diffusion.models.fresnoystaff_and_artist_user_limit, related_name='award', to=settings.AUTH_USER_MODEL),
        ),
    ]