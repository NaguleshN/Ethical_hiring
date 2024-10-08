# Generated by Django 5.1.1 on 2024-09-10 10:57

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hiring_app', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ResumeDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, null=True)),
                ('institution', models.CharField(max_length=100, null=True)),
                ('city', models.CharField(max_length=50, null=True)),
                ('passing_out_year', models.IntegerField(default=0, null=True)),
                ('Cgpa', models.FloatField(default=0, null=True)),
                ('Degree', models.CharField(max_length=50, null=True)),
                ('skills', models.CharField(max_length=200, null=True)),
                ('work_experience', models.CharField(max_length=100, null=True)),
                ('projects', models.CharField(max_length=100, null=True)),
                ('achievements', models.CharField(max_length=200, null=True)),
                ('emailid', models.CharField(max_length=50, null=True)),
                ('phone_number', models.IntegerField(null=True)),
            ],
        ),
        migrations.AlterField(
            model_name='resumecheck',
            name='upload_status',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='FileResumePath',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=200, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
