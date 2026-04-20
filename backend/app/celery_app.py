import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker"] # Where tasks are defined
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_timeout=3,
    task_track_started=True,
    # SaaS Optimization: Ensure tasks aren't lost if worker crashes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_on_timeout": False,
    },
)

if __name__ == "__main__":
    celery_app.start()
