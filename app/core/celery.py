"""
Celery configuration for background tasks
"""
from celery import Celery
import logging

logger = logging.getLogger(__name__)

# Import settings with error handling
try:
    from app.core.config import settings
    redis_url = settings.redis_url
except Exception as e:
    logger.warning(f"Could not load settings: {e}")
    # Fallback URL for development
    redis_url = "redis://redis:6379/0"

# Create Celery instance
celery_app = Celery(
    "ally360",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.modules.files.tasks",
        "app.modules.products.tasks", 
        "app.modules.email.tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Rate limiting
    task_default_rate_limit="100/m",
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Task routes for different queues
    task_routes={
        "app.modules.files.tasks.*": {"queue": "files"},
        "app.modules.products.tasks.*": {"queue": "products"},
        "app.modules.email.tasks.*": {"queue": "email"},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-expired-files": {
            "task": "app.modules.files.tasks.cleanup_expired_files",
            "schedule": 3600.0,  # Run every hour
        },
        "sync-file-sizes": {
            "task": "app.modules.files.tasks.sync_file_sizes_from_minio",
            "schedule": 86400.0,  # Run daily
        }
    }
)

# Configure logging for Celery
@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

if __name__ == "__main__":
    celery_app.start()