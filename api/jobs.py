"""
This module abstracts the job queueing system using Redis.
It handles enqueuing jobs, retrieving results, and monitoring job statuses,
integrating with the Flask application context for robust connection management.
"""
import json
import datetime
import uuid
from flask import current_app, url_for
from api.shared.redis_client import get_redis

# --- Constants ---
# Using constants makes key names consistent and easier to manage across services.
JOB_HASH_PREFIX = "job:"
JOB_QUEUE_KEY = "jobs:queue"
DEAD_LETTER_QUEUE_KEY = "jobs:dead-letter"
LOG_STREAM_KEY = "logs:stream"


def enqueue_scraping_job(job_params: dict, queue_name: str = None) -> str:
    """
    Enqueues a scraping job into Redis with arbitrary parameters, into a specific queue if provided.

    Args:
        job_params (dict): Dictionary of job parameters. Required fields will be injected/overridden.
        queue_name (str): The queue to enqueue into (e.g., 'suffix:postfix').

    Returns:
        str: The job ID.
    """
    redis_client = get_redis()
    job_id = str(uuid.uuid4())
    job_key = f"{JOB_HASH_PREFIX}{job_id}"

    # Required/auto fields
    required_fields = {
        "job_id": job_id,
        "status": "pending",
        "enqueued_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "result_url": url_for('api_bp.get_job_result', job_id=job_id, _external=True),
        "queue": queue_name or "default"
    }
    # Merge: user params take precedence, but required fields always override
    job_payload = {**job_params, **required_fields}

    # Determine queue key
    queue_key = JOB_QUEUE_KEY if not queue_name else f"jobs:queue:{queue_name}"

    # Create queue if it does not exist
    if queue_name:
        if not redis_client.sismember('queues:all', queue_name):
            redis_client.sadd('queues:all', queue_name)
            current_app.logger.info(f"Queue '{queue_name}' did not exist, so it was created.")

    try:
        with redis_client.pipeline() as pipe:
            pipe.hset(job_key, mapping=job_payload)
            pipe.lpush(queue_key, job_id)
            pipe.execute()
        current_app.logger.info(f"Enqueued job: {job_id} into queue {queue_key}")
        return job_id
    except Exception as e:
        current_app.logger.error(f"Failed to enqueue job in Redis: {e}")
        raise


def get_scraping_result(job_id: str) -> dict | None:
    """
    Retrieves the result and status of a scraping job from Redis.
    """
    redis_client = get_redis()
    try:
        job_data = redis_client.hgetall(f"{JOB_HASH_PREFIX}{job_id}")
        if job_data:
            # If a worker has processed this job, ensure it's in the all_workers set
            if 'worker_id' in job_data and job_data['worker_id']:
                redis_client.sadd('workers:all', job_data['worker_id'])

            # Attempt to parse 'result_data' from JSON string to Python object if present
            result_data_str = job_data.get("result_data")
            if result_data_str:
                try:
                    job_data["result_data"] = json.loads(result_data_str)
                except json.JSONDecodeError:
                    current_app.logger.warning(
                        f"Job {job_id}: 'result_data' field is not valid JSON. Keeping as string.")
            return job_data
        return None
    except Exception as e:
        current_app.logger.error(f"Failed to get job result from Redis for job {job_id}: {e}")
        raise


def get_all_job_statuses() -> list[dict]:
    """
    Retrieves a list of all job statuses stored as Redis hashes.
    Skips non-hash keys like job:queue to avoid WRONGTYPE errors.
    """
    redis_client = get_redis()
    jobs = []
    job_keys = []

    try:
        # Step 1: Filter out only keys of type 'hash' - compare as strings
        for key in redis_client.scan_iter(f"{JOB_HASH_PREFIX}*"):
            key_type = redis_client.type(key)
            # Defensive: Ensure key_type is string, not bytes
            if isinstance(key_type, bytes):
                key_type = key_type.decode('utf-8')
            if key_type == "hash":
                job_keys.append(key)
            else:
                current_app.logger.debug(f"Skipping key {key} of type {key_type}")

        if not job_keys:
            current_app.logger.warning("No job hashes found during scan.")

        # Step 2: Use pipeline to fetch all hashes in one go
        with redis_client.pipeline() as pipe:
            for job_key in job_keys:
                pipe.hgetall(job_key)
            results = pipe.execute()

        # Filter out empty dicts in case of race conditions
        jobs = [job_data for job_data in results if job_data]
        return jobs

    except Exception as e:
        current_app.logger.error(f"Failed to get all job statuses from Redis: {e}")
        raise


def get_all_job_statuses_paginated(count=50, page=1) -> dict:
    """
    Retrieves a paginated list of all job statuses stored as Redis hashes.
    Returns a dict with 'jobs' and 'total'.
    """
    redis_client = get_redis()
    jobs = []
    job_keys = []
    try:
        for key in redis_client.scan_iter(f"{JOB_HASH_PREFIX}*"):
            key_type = redis_client.type(key)
            if isinstance(key_type, bytes):
                key_type = key_type.decode('utf-8')
            if key_type == "hash":
                job_keys.append(key)
            else:
                current_app.logger.debug(f"Skipping key {key} of type {key_type}")
        if not job_keys:
            current_app.logger.warning("No job hashes found during scan.")
        # Sort keys by enqueued_at descending (most recent first)
        def get_enqueued_at(job):
            try:
                return job.get('enqueued_at') or ''
            except Exception:
                return ''
        # Fetch all jobs, then sort and slice
        with redis_client.pipeline() as pipe:
            for job_key in job_keys:
                pipe.hgetall(job_key)
            results = pipe.execute()
        jobs = [job_data for job_data in results if job_data]
        jobs.sort(key=get_enqueued_at, reverse=True)
        total = len(jobs)
        start = (page - 1) * count
        end = start + count
        jobs_page = jobs[start:end]
        return {"jobs": jobs_page, "total": total}
    except Exception as e:
        current_app.logger.error(f"Failed to get all job statuses from Redis: {e}")
        raise



# def clear_all_jobs() -> int:
#     """
#     Deletes all job-related data from Redis.

#     This includes all job hashes, the main job queue, and the dead-letter queue.
#     WARNING: This is a destructive operation and cannot be undone.

#     Returns:
#         The number of job hashes that were deleted.
#     """
#     redis_client = _get_redis_client()
#     try:
#         # Find all job hash keys using the safer SCAN command
#         job_keys = list(redis_client.scan_iter(f"{JOB_HASH_PREFIX}*"))
        
#         # Use a pipeline to delete all found keys and the queues atomically
#         with redis_client.pipeline() as pipe:
#             if job_keys:
#                 pipe.delete(*job_keys)
#             pipe.delete(JOB_QUEUE_KEY, DEAD_LETTER_QUEUE_KEY)
#             pipe.execute()

#         current_app.logger.info(f"Cleared {len(job_keys)} jobs and associated queues.")
#         return len(job_keys)
#     except Exception as e:
#         current_app.logger.error(f"Failed to clear all jobs from Redis: {e}")
#         raise


def clear_all_logs_stream(log_type: str = 'worker') -> bool:
    """
    Deletes the entire log stream from Redis for a given log type.
    log_type: 'worker', 'app', 'auth', etc.
    WARNING: This is a destructive operation and cannot be undone.
    Returns:
        True if the stream existed and was deleted, False otherwise.
    """
    redis_client = get_redis()
    log_stream_key = f"logs:stream" if log_type == 'worker' else f"logs:{log_type}:stream"
    try:
        deleted_count = redis_client.delete(log_stream_key)
        current_app.logger.info(f"Cleared log stream '{log_stream_key}'. Deleted {deleted_count} key(s).")
        return deleted_count > 0
    except Exception as e:
        current_app.logger.error(f"Failed to clear log stream from Redis: {e}")
        raise


def get_logs_paginated(log_type='worker', count=50, page=1, **filters):
    """
    Retrieves paginated logs from the Redis log stream for a given log type.
    Returns a dict with 'logs' and 'total'.
    Supports optional filters (worker_id, user_id, endpoint, action, level, etc).
    """
    redis_client = get_redis()
    if log_type == 'worker':
        log_stream_key = LOG_STREAM_KEY
    else:
        log_stream_key = f"logs:{log_type}:stream"
    try:
        # Get all entries (could optimize with XRANGE/XREVRANGE and offset in future)
        entries = redis_client.xrevrange(log_stream_key, count=10000)  # limit to 10k for safety
        logs = []
        for entry_id, data in entries:
            # Filter by log type specific fields
            if log_type == 'worker':
                if filters.get('worker_id') and data.get('worker_id') != filters['worker_id']:
                    continue
                if filters.get('level') and data.get('level') != filters['level']:
                    continue
            elif log_type == 'auth':
                if filters.get('user_id') and data.get('user_id') != filters['user_id']:
                    continue
                if filters.get('action') and data.get('action') != filters['action']:
                    continue
                if filters.get('level') and data.get('level') != filters['level']:
                    continue
            elif log_type == 'api':
                if filters.get('endpoint') and data.get('endpoint') != filters['endpoint']:
                    continue
                if filters.get('user_id') and data.get('user_id') != filters['user_id']:
                    continue
                if filters.get('level') and data.get('level') != filters['level']:
                    continue
            elif log_type == 'app':
                if filters.get('level') and data.get('level') != filters['level']:
                    continue
            log = {"id": entry_id, **data}
            logs.append(log)
        total = len(logs)
        start = (page - 1) * count
        end = start + count
        logs_page = logs[start:end]
        return {"logs": logs_page, "total": total}
    except Exception as e:
        current_app.logger.error(f"Failed to fetch logs from Redis: {e}")
        raise
