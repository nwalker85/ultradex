from arq.connections import RedisSettings

from core.workers import WorkerSettings, redis_settings_from_env


def test_redis_settings_prefer_compose_dsn(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://:secret@redis.internal:6381/4")
    monkeypatch.setenv("REDIS_HOST", "ignored")

    settings = redis_settings_from_env()

    assert isinstance(settings, RedisSettings)
    assert settings.host == "redis.internal"
    assert settings.port == 6381
    assert settings.database == 4
    assert settings.password == "secret"


def test_worker_registers_the_gateway_job_names():
    assert isinstance(WorkerSettings.redis_settings, RedisSettings)
    assert {"analyze_task", "sync_task"} <= {
        function.name for function in WorkerSettings.functions
    }
    assert WorkerSettings.max_jobs == 10
