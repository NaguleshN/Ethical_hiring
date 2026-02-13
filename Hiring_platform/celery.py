from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Hiring_platform.settings')

# Fix for macOS MPS issues with PyTorch in multiprocessing
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['OMP_NUM_THREADS'] = '1'

app = Celery('Hiring_platform')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure task rate limits and retry policies
app.conf.update(
    # Task rate limiting - limit Gemini API calls to avoid quota issues
    task_default_rate_limit='10/m',  # 10 tasks per minute max
    
    # Task retry configuration
    task_autoretry_for=(Exception,),  # Auto-retry for exceptions
    task_retry_kwargs={'max_retries': 3, 'countdown': 60},  # Wait 60s between retries
    task_acks_late=True,  # Acknowledge task after it completes
    task_reject_on_worker_lost=True,  # Requeue task if worker dies
    
    # Worker prefetch settings - reduce concurrent tasks
    worker_prefetch_multiplier=1,  # Process one task at a time to avoid rate limits
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (helps with memory leaks)
    
    # Timeout settings
    task_soft_time_limit=300,  # 5 minutes soft timeout
    task_time_limit=600,  # 10 minutes hard timeout
)

print("Celery configuration loaded:", app.conf.broker_url, app.conf.result_backend)

app.autodiscover_tasks()