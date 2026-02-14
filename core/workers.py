"""ARQ Worker configuration and setup"""

import os
from arq import create_pool
from arq.connections import ArqRedis


class WorkerSettings:
    """ARQ worker configuration"""

    # Redis connection
    redis_settings = {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "database": 0,
    }

    # Job defaults
    functions = [
        "core.tasks.analyze.analyze_contacts_task",
        "core.tasks.sync.sync_contacts_task",
    ]

    # Queue settings
    max_concurrent_tasks = 10
    idle_timeout = 600  # 10 minutes

    # Health checks
    health_check_interval = 10


async def get_redis() -> ArqRedis:
    """Get Redis connection for use in endpoints"""
    return await create_pool(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        database=0,
    )
