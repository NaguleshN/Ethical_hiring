# Generated by Django 5.1.1 on 2024-09-10 12:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hiring_app', '0002_resumedetails_alter_resumecheck_upload_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resumedetails',
            name='phone_number',
            field=models.CharField(max_length=20, null=True),
        ),
    ]
