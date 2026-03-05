"""
Celery application configuration.

Defines the Celery app with dual queues (default + llm),
Beat schedule, and task auto-discovery.
"""

from celery import Celery
from celery.schedules import crontab

from packages.shared.config import settings

# ── Celery app ────────────────────────────────────────────────────────────────

app = Celery(
    "property_search",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Default queue
    task_default_queue="default",

    # Timezone
    timezone="Europe/Dublin",
    enable_utc=True,

    # Task behavior
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result expiry
    result_expires=3600,

    # Task routing — LLM tasks go to dedicated queue
    task_routes={
        "apps.worker.tasks.enrich_property_llm": {"queue": "llm"},
        "apps.worker.tasks.enrich_batch_llm": {"queue": "llm"},
    },

    # Task rate limits
    task_annotations={
        "apps.worker.tasks.scrape_source": {"rate_limit": "2/m"},
    },

    # Beat schedule — periodic tasks
    beat_schedule={
        # Scrape all enabled sources every 6 hours
        "scrape-all-sources": {
            "task": "apps.worker.tasks.scrape_all_sources",
            "schedule": crontab(minute=0, hour="*/6"),
        },

        # Evaluate alerts after each scrape cycle
        "evaluate-alerts": {
            "task": "apps.worker.tasks.evaluate_alerts",
            "schedule": crontab(minute=15, hour="*/6"),
        },

        # Import PPR data weekly (Sunday 2am)
        "import-ppr-weekly": {
            "task": "apps.worker.tasks.import_ppr",
            "schedule": crontab(minute=0, hour=2, day_of_week=0),
        },

        # Cleanup old alerts daily
        "cleanup-old-alerts": {
            "task": "apps.worker.tasks.cleanup_old_alerts",
            "schedule": crontab(minute=0, hour=3),
        },
    },
)

# Auto-discover tasks
app.autodiscover_tasks(["apps.worker"])


@app.on_after_finalize.connect
def _initial_scrape(sender, **kwargs):
    """Trigger an initial scrape 30s after worker startup."""
    sender.send_task(
        "apps.worker.tasks.scrape_all_sources",
        countdown=30,
    )
