from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "ai_content_automation",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.content_tasks",
        "app.tasks.scheduled_tasks",
        "app.tasks.email_tasks",   # Added in Task 5
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_extended=True,
    task_track_started=True,
    # Task 5: dedicated queues
    task_routes={
        "content.*": {"queue": "content_queue"},
        "email.*":   {"queue": "email_queue"},
    },
)

# Celery Beat schedule (Task 3)
celery_app.conf.beat_schedule = {
    "daily_content_generation": {
        "task": "content.daily_content_generation",
        "schedule": crontab(hour=6, minute=0),
    },
}