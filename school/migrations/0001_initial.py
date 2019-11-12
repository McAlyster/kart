# Generated by Django 2.2.6 on 2019-11-08 13:36

import common.utils
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('assets', '0001_initial'),
        ('people', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Promotion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('starting_year', models.PositiveSmallIntegerField()),
                ('ending_year', models.PositiveSmallIntegerField()),
            ],
            options={
                'ordering': ['starting_year'],
            },
        ),
        migrations.CreateModel(
            name='StudentApplicationSetup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=25, null=True)),
                ('candidature_date_start', models.DateTimeField()),
                ('candidature_date_end', models.DateTimeField()),
                ('interviews_start_date', models.DateField(help_text='Front : interviews start date', null=True)),
                ('interviews_end_date', models.DateField(help_text='Front : interviews end date', null=True)),
                ('date_of_birth_max', models.DateField(blank=True, help_text='Maximum date of birth to apply', null=True)),
                ('interviews_publish_date', models.DateTimeField(help_text='Interviews web publish', null=True)),
                ('selected_publish_date', models.DateTimeField(help_text='Final selection web publish', null=True)),
                ('candidatures_url', models.URLField(help_text='Front : Url list of candidatures')),
                ('reset_password_url', models.URLField(help_text='Front : Url reset password')),
                ('recover_password_url', models.URLField(help_text='Front : Url recover password')),
                ('authentification_url', models.URLField(help_text='Front : Url authentification')),
                ('video_service_name', models.CharField(blank=True, help_text='video service name', max_length=25, null=True)),
                ('video_service_url', models.URLField(help_text='service URL')),
                ('video_service_token', models.CharField(blank=True, help_text='Video service token', max_length=128, null=True)),
                ('is_current_setup', models.BooleanField(default=True, help_text='This configuration is actived')),
                ('promotion', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='school.Promotion')),
            ],
        ),
        migrations.CreateModel(
            name='StudentApplication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_year_application_count', models.CharField(blank=True, default=None, help_text='Auto generated field (current year - increment number)', max_length=8)),
                ('identity_card', models.FileField(blank=True, help_text='Identity justificative', null=True, upload_to=common.utils.make_filepath)),
                ('first_time', models.BooleanField(default=False, help_text="If the first time the Artist's applying")),
                ('last_applications_years', models.CharField(blank=True, help_text='Already candidate', max_length=50)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('remote_interview', models.BooleanField(default=False)),
                ('remote_interview_type', models.CharField(blank=True, help_text='Skype / Gtalk / FaceTime / AppearIn / Other', max_length=50)),
                ('remote_interview_info', models.CharField(blank=True, help_text='ID / Number / ... ', max_length=50)),
                ('master_degree', models.CharField(blank=True, choices=[('Y', 'Yes'), ('N', 'No'), ('P', 'Pending')], help_text='Obtained a Master Degree', max_length=10, null=True)),
                ('experience_justification', models.FileField(blank=True, help_text='If no master Degree, experience letter', null=True, upload_to=common.utils.make_filepath)),
                ('curriculum_vitae', models.FileField(blank=True, help_text='BIO CV', null=True, upload_to=common.utils.make_filepath)),
                ('justification_letter', models.FileField(blank=True, help_text='Justification / Motivation', null=True, upload_to=common.utils.make_filepath)),
                ('reference_letter', models.FileField(blank=True, help_text='Reference / Recommendation letter', null=True, upload_to=common.utils.make_filepath)),
                ('free_document', models.FileField(blank=True, help_text='Free document', null=True, upload_to=common.utils.make_filepath)),
                ('binomial_application', models.BooleanField(default=False, help_text='Candidature with another artist')),
                ('binomial_application_with', models.CharField(blank=True, help_text="Name of the binominal artist's candidate with", max_length=50)),
                ('considered_project_1', models.FileField(blank=True, help_text='Considered project first year', null=True, upload_to=common.utils.make_filepath)),
                ('artistic_referencies_project_1', models.FileField(blank=True, help_text="Artistic references for first first year's project", null=True, upload_to=common.utils.make_filepath)),
                ('considered_project_2', models.FileField(blank=True, help_text='Considered project second year', null=True, upload_to=common.utils.make_filepath)),
                ('artistic_referencies_project_2', models.FileField(blank=True, help_text="Artistic references for second first year's project", null=True, upload_to=common.utils.make_filepath)),
                ('doctorate_interest', models.BooleanField(default=False, help_text='Interest in the doctorate')),
                ('presentation_video', models.URLField(blank=True, help_text='Url presentation video Link', null=True)),
                ('presentation_video_details', models.TextField(blank=True, help_text='Details for the video', null=True)),
                ('presentation_video_password', models.CharField(blank=True, help_text='Password for the video', max_length=50)),
                ('remark', models.TextField(blank=True, help_text="Free expression'", null=True)),
                ('application_completed', models.BooleanField(default=False, help_text="Candidature's validation")),
                ('observation', models.TextField(blank=True, help_text='Administration - Comments on the application', null=True)),
                ('selected_for_interview', models.BooleanField(default=False, help_text='Administration - Is the candidat selected for the Interview')),
                ('interview_date', models.DateTimeField(blank=True, help_text='Administration - Date for interview', null=True)),
                ('wait_listed_for_interview', models.BooleanField(default=False, help_text='Administration - Is the candidat wait listed for the Interview')),
                ('selected', models.BooleanField(default=False, help_text='Administration - Is the candidat selected')),
                ('unselected', models.BooleanField(default=False, help_text='Administration - Is the candidat not choosen by the Jury')),
                ('wait_listed', models.BooleanField(default=False, help_text='Administration - Is the candidat wait listed')),
                ('application_complete', models.BooleanField(default=False, help_text='Administration - Candidature is complete')),
                ('artist', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_application', to='people.Artist')),
                ('campaign', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applications', to='school.StudentApplicationSetup')),
                ('cursus_justifications', models.ForeignKey(blank=True, help_text='Gallery of justificaitons', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='student_application_cursus_justification', to='assets.Gallery')),
            ],
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, max_length=50, null=True)),
                ('graduate', models.BooleanField(default=False)),
                ('artist', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='student', to='people.Artist')),
                ('promotion', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='school.Promotion')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]