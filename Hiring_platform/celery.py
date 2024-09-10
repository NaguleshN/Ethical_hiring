from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Hiring_platform.settings')

app = Celery('Hiring_platform')

app.config_from_object('django.conf:settings', namespace='CELERY')

print("Celery configuration loaded:", app.conf.broker_url, app.conf.result_backend)

app.autodiscover_tasks()