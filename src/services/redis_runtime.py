# -*- coding: utf-8 -*-
"""Runtime helper for the local Redis cache used by the Mac mini deployment."""

import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from config.settings import settings


def _is_local_redis_url() -> bool:
    parsed = urlparse(settings.redis_url)
    return parsed.scheme == "redis" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def ensure_local_redis(timeout_seconds: float = 5.0) -> bool:
    """Start the user-space Redis instance when the deployment uses localhost Redis."""
    if not _is_local_redis_url():
        return False

    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
        return True
    except Exception:
        pass

    home = Path.home()
    redis_server = Path(os.getenv("CONTRACT_AI_REDIS_SERVER", str(home / ".local/redis/bin/redis-server")))
    redis_conf = Path(os.getenv("CONTRACT_AI_REDIS_CONF", str(home / ".config/contract-ai/redis.conf")))

    try:
        if redis_server.exists() and redis_conf.exists():
            logs_dir = Path("/Users/legalai/projects/Contract-AI-System-/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            with (logs_dir / "redis.out.log").open("ab") as stdout, (logs_dir / "redis.err.log").open("ab") as stderr:
                subprocess.Popen(
                    [str(redis_server), str(redis_conf)],
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
        else:
            script = Path(os.getenv(
                "CONTRACT_AI_REDIS_ENSURE_SCRIPT",
                "/Users/legalai/projects/Contract-AI-System-/ops/scripts/ensure_redis.sh",
            ))
            if not script.exists():
                logger.warning("Local Redis runtime files are missing; cannot auto-start Redis")
                return False
            subprocess.run([str(script)], check=False, timeout=timeout_seconds)
    except Exception as exc:
        logger.warning(f"Local Redis auto-start failed: {exc}")
        return False

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
            client.ping()
            logger.info("Local Redis auto-started")
            return True
        except Exception:
            time.sleep(0.25)

    logger.warning("Local Redis auto-start timed out")
    return False
