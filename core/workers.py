"""ARQ Worker configuration and setup"""

import os
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.worker import func

from .tasks.analyze import analyze_contacts_task
from .tasks.sync import sync_contacts_task


def redis_settings_from_env() -> RedisSettings:
    """Build one Redis contract shared by API, worker, and Compose."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return RedisSettings.from_dsn(redis_url)
    return RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        database=int(os.getenv("REDIS_DATABASE", "0")),
    )


class WorkerSettings:
    """ARQ worker configuration"""

    # Redis connection
    redis_settings = redis_settings_from_env()

    # Job defaults
    functions = [
        func(analyze_contacts_task, name="analyze_task"),
        func(sync_contacts_task, name="sync_task"),
    ]

    # Queue settings
    max_jobs = 10

    # Health checks
    health_check_interval = 10


async def get_redis() -> ArqRedis:
    """Get Redis connection for use in endpoints"""
    return await create_pool(redis_settings_from_env())
