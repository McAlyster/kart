# Generated by Django 3.1.13 on 2022-06-02 11:36

import diffusion.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('diffusion', '0006_auto_20211202_1654'),
    ]

    operations = [
        migrations.AlterField(
            model_name='award',
            name='artist',
            field=models.ManyToManyField(blank=True, help_text='FresnoyStaff or Artist', limit_choices_to=diffusion.models.fresnoystaff_and_artist_user_limit, related_name='award', to=settings.AUTH_USER_MODEL),
        ),
    ]