# api/shared/redis_client.py
import redis
from flask import current_app


def get_redis():
    """
    Provides a singleton Redis client instance within the Flask app context.

    This function ensures that only one Redis client is created per app context,
    improving performance and resource management. It reads connection details
    from the Flask app's configuration.

    The client is configured to decode responses to UTF-8 by default.
    """
    # Use a unique attribute name on `current_app` to avoid collisions.
    # `_redis_client` is a common convention for a "private" attribute.
    if not hasattr(current_app, '_redis_client'):
        redis_url = current_app.config.get('REDIS_URL')
        redis_password = current_app.config.get('REDIS_PASSWORD')
        if not redis_url:
            raise RuntimeError("REDIS_URL must be configured")

        try:
            current_app._redis_client = redis.from_url(
                redis_url,
                password=redis_password,
                decode_responses=True
            )
            current_app._redis_client.ping()
        except redis.exceptions.RedisError as e:
            current_app.logger.critical("Failed to connect to Redis: %s", e, exc_info=True)
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    return current_app._redis_client

