# Generated by Django 5.1.1 on 2024-09-11 07:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hiring_app', '0009_alter_resumedetails_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='resumedetails',
            name='video_score',
            field=models.FloatField(default=0),
        ),
    ]
