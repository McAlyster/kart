# Generated by Django 4.2.16 on 2024-10-31 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0016_email_reminder_date_field'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentapplication',
            name='INE',
            field=models.CharField(blank=True, help_text='Identifiant National Etudiant (only French student) - 9 numbers + 2 letters', max_length=11, null=True),
        ),
    ]
