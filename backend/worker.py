"""Celery worker entry point.

Run with:
    celery -A worker.celery worker --loglevel=info
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from celery import Celery


def make_celery(app):
    """Create a Celery instance configured from Flask app config."""
    celery = Celery(
        app.import_name,
        broker=app.config["CELERY_BROKER_URL"],
        backend=app.config["CELERY_RESULT_BACKEND"],
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


flask_app = create_app(os.environ.get("FLASK_ENV", "development"))
celery = make_celery(flask_app)

# Beat schedule for periodic tasks
celery.conf.beat_schedule = {
    "publish-scheduled-posts-every-minute": {
        "task": "tasks.publish_scheduled",
        "schedule": 60.0,
    },
}


@celery.task(name="tasks.run_generation", bind=True, max_retries=3)
def run_generation(self, job_id: str):
    """Celery task executing end-to-end generation pipeline."""
    from app.tasks.generation import execute_generation_job
    try:
        return execute_generation_job(job_id).to_dict()
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)


@celery.task(name="tasks.publish_scheduled")
def publish_scheduled():
    """Periodic Celery task checking and publishing due posts."""
    from app.tasks.publishing import publish_due_scheduled_posts
    return publish_due_scheduled_posts()

