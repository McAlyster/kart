# Generated by Django 2.1.7 on 2019-03-28 16:09

import common.utils
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('people', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Artist',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nickname', models.CharField(blank=True, max_length=255)),
                ('bio_short_fr', models.TextField(blank=True)),
                ('bio_short_en', models.TextField(blank=True)),
                ('bio_fr', models.TextField(blank=True)),
                ('bio_en', models.TextField(blank=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('twitter_account', models.CharField(blank=True, max_length=100)),
                ('facebook_profile', models.URLField(blank=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user__last_name'],
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('picture', models.ImageField(blank=True, upload_to=common.utils.make_filepath)),
                ('updated_on', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='fresnoyprofile',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to=common.utils.make_filepath),
        ),
    ]