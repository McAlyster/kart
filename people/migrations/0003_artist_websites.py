# Generated by Django 2.1.7 on 2019-04-04 15:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
        ('people', '0002_auto_20190328_1709'),
    ]

    operations = [
        migrations.AddField(
            model_name='artist',
            name='websites',
            field=models.ManyToManyField(blank=True, to='common.Website'),
        ),
    ]