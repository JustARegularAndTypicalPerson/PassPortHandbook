# api/routes.py
from flask import Blueprint, abort, jsonify, request, current_app, url_for, render_template
import re
from functools import wraps
from api.scrapers.yandex_scraper import CaptchaRequired
from api.jobs import enqueue_scraping_job, get_scraping_result, get_all_job_statuses, clear_all_logs_stream, LOG_STREAM_KEY
import datetime
import os
import json
from api.shared.redis_client import get_redis

api_bp = Blueprint('api_bp', __name__)


# --- Authentication ---

# Token for administrative tasks (e.g., cancelling jobs, managing workers)
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')
def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_TOKEN:
            return jsonify({'error': 'Server is not configured for admin access'}), 503
        token = request.headers.get('X-Admin-Token')
        if token != ADMIN_TOKEN:
            return jsonify({'error': 'Forbidden', 'message': 'Admin token required'}), 403
        return f(*args, **kwargs)
    return decorated

# Token for general API clients (e.g., creating jobs)
API_TOKEN = os.environ.get('API_TOKEN')
def require_api_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_TOKEN:
            return jsonify({'error': 'Server is not configured for API access'}), 503
        token = request.headers.get('X-Api-Token')
        if token != API_TOKEN:
            return jsonify({'error': 'Forbidden', 'message': 'API token required'}), 403
        return f(*args, **kwargs)
    return decorated

# Add to routes.py
@api_bp.route('/health', methods=['GET'])
def health_check():
    try:
        get_redis().ping()
        return {"status": "ok", "redis": "ok"}, 200
    except Exception as e:
        current_app.logger.error("Health check failed: %s", e, exc_info=True)
        return {"status": "error", "redis": "unreachable"}, 500

# @api_bp.route('/scrapers/add-job/<string:scraper_type>/<string:operation_type>', methods=['POST'])
# @require_api_token
# def create_scraping_job(scraper_type: str, operation_type: str):
#     """
#     Creates and enqueues a new scraping job for a specific scraper and operation.
#     This endpoint is non-blocking. It returns a job ID that can be used
#     to poll for results.
#     Accepts arbitrary job parameters in the JSON body.
#     """
#     if not request.is_json:
#         abort(415, description="Expected Content-Type to be application/json.")

#     data = request.get_json()
#     if not data:
#         abort(400, description="Request body must be non-empty JSON.")

#     # Always inject/override these fields for safety and consistency
#     data['scraper_type'] = scraper_type.lower()
#     data['operation_type'] = operation_type.lower()

#     # Optionally: Validate required fields if you want to enforce some
#     errors = []
#     if 'id' not in data:
#         errors.append("Missing or invalid.")
#     if 'period' in data and data['period'] and not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}-\d{2}\.\d{2}\.\d{4}', data['period']):
#         errors.append("Invalid 'period' format. Expected 'dd.mm.yy-dd.mm.yy'.")
#     if 'page_num' in data and (not isinstance(data['page_num'], int) or data['page_num'] < 1):
#         errors.append("Invalid 'page_num'; must be a positive integer.")
#     if errors:
#         return jsonify({"error": "Bad Request", "messages": errors}), 400

#     # Rename 'id' to 'target_id' for job payload
#     data['target_id'] = int(data.pop('id'))

#     try:
#         job_id = enqueue_scraping_job(data)
#     except Exception as e:
#         current_app.logger.error(f"Failed to enqueue job: {e}", exc_info=True)
#         abort(500, description="Failed to enqueue scraping job.")

#     response_data = {
#         'job_id': job_id,
#         'target_id': data.get('target_id'),
#         'period': data.get('period'),
#         'status': 'accepted',
#         'result_url': url_for('api_bp.get_job_result', job_id=job_id, _external=True)
#     }
#     response = jsonify(response_data)
#     response.status_code = 202
#     response.headers['Location'] = response_data['result_url']
#     return response

@api_bp.route('/scrapers/add-job/<string:queue_suffix>/<string:queue_postfix>', methods=['POST'])
@require_api_token
def create_scraping_job(queue_suffix: str, queue_postfix: str):
    """
    Creates and enqueues a new scraping job for a specific queue (suffix:postfix).
    If the queue does not exist, it will be created.
    This endpoint is non-blocking. It returns a job ID that can be used to poll for results.
    Accepts arbitrary job parameters in the JSON body.
    """
    if not request.is_json:
        abort(415, description="Expected Content-Type to be application/json.")
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be non-empty JSON.")

    queue_name = f"{queue_suffix}:{queue_postfix}"

    # Optionally: Validate required fields if you want to enforce some
    errors = []
    if 'id' not in data:
        errors.append("Missing or invalid.")
    if errors:
        return jsonify({"error": "Bad Request", "messages": errors}), 400

    # Rename 'id' to 'target_id' for job payload
    data['target_id'] = int(data.pop('id'))

    try:
        from api.jobs import enqueue_scraping_job
        job_id = enqueue_scraping_job(data, queue_name=queue_name)
    except Exception as e:
        current_app.logger.error(f"Failed to enqueue job: {e}", exc_info=True)
        abort(500, description="Failed to enqueue scraping job.")

    response_data = {
        'job_id': job_id,
        'target_id': data.get('target_id'),
        'period': data.get('period'),
        'status': 'accepted',
        'queue': queue_name,
        'result_url': url_for('api_bp.get_job_result', job_id=job_id, _external=True)
    }
    response = jsonify(response_data)
    response.status_code = 202
    response.headers['Location'] = response_data['result_url']
    return response

@api_bp.route('/jobs/status', methods=['GET'])
def get_all_jobs_status():
    """
    Retrieves the status of all active, pending, and completed jobs.
    Supports server-side pagination with ?count and ?page.
    """
    try:
        count = int(request.args.get('count', 50))
        page = int(request.args.get('page', 1))
        from api.jobs import get_all_job_statuses_paginated
        result = get_all_job_statuses_paginated(count=count, page=page)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve all job statuses: {e}", exc_info=True)
        abort(500, description="Failed to retrieve job statuses.")

@api_bp.route('/jobs/monitor', methods=['GET'])
def monitor_jobs():
    """Renders a page to monitor all scraping jobs."""
    return render_template('jobs.html')

# @api_bp.route('/jobs/clear', methods=['POST'])
# @require_admin
# def clear_all_jobs_route():
#     """
#     Clears all jobs, queues, and related data from Redis.
#     This is a destructive operation, hence it requires admin privileges.
#     """
#     try:
#         count = clear_all_jobs()
#         return jsonify({"message": f"Successfully cleared {count} jobs and associated queues."}), 200
#     except Exception as e:
#         current_app.logger.error(f"Failed to clear jobs: {e}", exc_info=True)
#         abort(500, description="An error occurred while clearing jobs.")

@api_bp.route('/jobs/<string:job_id>/result', methods=['GET'])
def get_job_result(job_id: str):
    """
    Poll this endpoint to get the result of a scraping job.
    """
    try:
        result = get_scraping_result(job_id)
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve result for job {job_id}: {e}", exc_info=True)
        abort(500, description=f"Error retrieving result for job {job_id}.")

    if result is None:
        abort(404, description=f"Job with ID '{job_id}' not found.")

    # The job service can return special payloads for different states.
    status = result.get("status")
    if status == "pending":
        return jsonify({"status": "pending", "message": "Job is still being processed."}), 202

    if status == "failed":
        return jsonify(result), 500

    # Assuming success if we reach here
    return jsonify(result), 200

def get_worker_logs():
    """
    Fetches logs from the Redis log stream for monitoring worker activity.
    Supports optional query params: 'start', 'end', 'count', 'worker_id', 'level'.
    """
    # Query params
    start = request.args.get('start', '-')
    end = request.args.get('end', '+')
    count = int(request.args.get('count', 100))
    worker_id = request.args.get('worker_id')
    level = request.args.get('level')

    try:
        redis_client = get_redis()
        entries = redis_client.xrevrange(LOG_STREAM_KEY, max=end, min=start, count=count)
        logs = []
        for entry_id, data in entries:
            # Filter by worker_id and level if provided
            if worker_id and data.get('worker_id') != worker_id:
                continue
            if level and data.get('level') != level:
                continue
            logs.append({"id": entry_id, **data})
        return jsonify({"logs": logs})
    except Exception as e:
        current_app.logger.error(f"Failed to fetch logs from Redis: {e}", exc_info=True)
        abort(500, description="Failed to fetch logs.")
        
@api_bp.route('/logs', methods=['GET'])
def get_logs():
    """
    Fetches logs from the Redis log stream for monitoring activity.
    Supports server-side pagination: 'count', 'page', and filters.
    """
    log_type = request.args.get('type', 'worker')
    count = int(request.args.get('count', 50))
    page = int(request.args.get('page', 1))
    filters = {}
    for key in ['worker_id', 'user_id', 'endpoint', 'action', 'level']:
        val = request.args.get(key)
        if val:
            filters[key] = val
    try:
        from api.jobs import get_logs_paginated
        result = get_logs_paginated(log_type=log_type, count=count, page=page, **filters)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to fetch logs from Redis: {e}", exc_info=True)
        abort(500, description="Failed to fetch logs.")

@api_bp.route('/logs/monitor', methods=['GET'])
def monitor_worker_logs():
    """
    Renders a page to monitor worker logs in real time.
    """
    return render_template('logs.html')

@api_bp.route('/logs/clear', methods=['POST'])
@require_admin
def clear_all_logs_route():
    """
    Clears all logs from the Redis stream for a given log type.
    This is a destructive operation, hence it requires admin privileges.
    Accepts optional query param: 'type' (default: 'worker')
    """
    log_type = request.args.get('type', 'worker')
    try:
        from api.jobs import clear_all_logs_stream
        clear_all_logs_stream(log_type=log_type)
        return jsonify({"message": f"Successfully cleared all logs for type '{log_type}'."}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to clear logs: {e}", exc_info=True)
        abort(500, description="An error occurred while clearing logs.")

@api_bp.route('/jobs/<string:job_id>/cancel', methods=['POST'])
@require_admin
def cancel_job(job_id):
    redis_client = get_redis()
    job_key = f"job:{job_id}"
    job_data = redis_client.hgetall(job_key)
    if not job_data:
        abort(404, description=f"Job {job_id} not found.")
    if job_data.get('status') in ['completed', 'failed', 'cancelled']:
        return jsonify({"message": f"Job {job_id} is already {job_data.get('status')}."}), 400
    redis_client.hset(job_key, mapping={
        'status': 'cancelled',
        'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'error_message': 'Job was cancelled by user.'
    })
    return jsonify({"message": f"Job {job_id} cancelled."})

# --- Forbidden Workers Management ---
FORBIDDEN_WORKERS_SET = 'forbidden:workers'

@api_bp.route('/workers/forbidden', methods=['GET'])
@require_admin
def list_forbidden_workers():
    redis_client = get_redis()
    workers = list(redis_client.smembers(FORBIDDEN_WORKERS_SET))
    return jsonify({"forbidden_workers": workers})

@api_bp.route('/workers/forbidden/<worker_id>', methods=['POST'])
@require_admin
def forbid_worker(worker_id):
    redis_client = get_redis()
    redis_client.sadd(FORBIDDEN_WORKERS_SET, worker_id)
    redis_client.hset(f"worker:{worker_id}:meta", "forbidden", 1)
    redis_client.sadd('workers:all', worker_id)
    # Add worker to all queue:<name>:forbidden_workers sets
    all_queues = redis_client.smembers('queues:all')
    for q in all_queues:
        redis_client.sadd(f"queue:{q}:forbidden_workers", worker_id)
    # Also forbid from default queue
    redis_client.sadd("queue:default:forbidden_workers", worker_id)
    return jsonify({"message": f"Worker {worker_id} is now forbidden from all queues."})

@api_bp.route('/workers/forbidden/<worker_id>', methods=['DELETE'])
@require_admin
def unforbid_worker(worker_id):
    redis_client = get_redis()
    redis_client.srem(FORBIDDEN_WORKERS_SET, worker_id)
    redis_client.hset(f"worker:{worker_id}:meta", "forbidden", 0)
    redis_client.sadd('workers:all', worker_id)
    # Remove worker from all queue:<name>:forbidden_workers sets
    all_queues = redis_client.smembers('queues:all')
    for q in all_queues:
        redis_client.srem(f"queue:{q}:forbidden_workers", worker_id)
    # Also unforbid from default queue
    redis_client.srem("queue:default:forbidden_workers", worker_id)
    return jsonify({"message": f"Worker {worker_id} is no longer forbidden from all queues."})

@api_bp.route('/workers/all', methods=['GET'])
@require_admin
def list_all_workers():
    """
    Returns all workers ever seen, their meta (label, queues, forbidden), all available queues, and per-queue forbidden info.
    """
    redis_client = get_redis()
    worker_ids = list(redis_client.smembers('workers:all'))
    all_queues = list(redis_client.smembers('queues:all'))
    workers = []
    for wid in worker_ids:
        meta = redis_client.hgetall(f"worker:{wid}:meta")
        # Per-queue forbidden info
        forbidden_queues = []
        for q in all_queues:
            if redis_client.sismember(f"queue:{q}:forbidden_workers", wid):
                forbidden_queues.append(q)
        workers.append({
            "id": wid,
            "label": meta.get("label", ""),
            "queues": json.loads(meta.get("queues", "[]")),
            "forbidden": bool(int(meta.get("forbidden", "0"))),
            "forbidden_queues": forbidden_queues
        })
    return jsonify({"workers": workers, "all_queues": all_queues})

@api_bp.route('/workers/<worker_id>/meta', methods=['POST'])
@require_admin
def set_worker_meta(worker_id):
    """
    Set label and queues for a worker. Body: {"label": ..., "queues": [...]}
    """
    redis_client = get_redis()
    data = request.get_json(force=True)
    label = data.get('label', '')
    queues = data.get('queues', [])
    redis_client.hset(f"worker:{worker_id}:meta", mapping={
        "label": label,
        "queues": json.dumps(queues)
    })
    # Ensure worker is in the all set
    redis_client.sadd('workers:all', worker_id)
    return jsonify({"message": "Worker meta updated."})

@api_bp.route('/queues', methods=['POST'])
@require_admin
def add_queue():
    redis_client = get_redis()
    data = request.get_json(force=True)
    name = data.get('name')
    if not name:
        return jsonify({"error": "Missing queue name."}), 400
    redis_client.sadd('queues:all', name)
    return jsonify({"message": f"Queue {name} added."})

@api_bp.route('/queues/<queue_name>', methods=['DELETE'])
@require_admin
def remove_queue(queue_name):
    redis_client = get_redis()
    redis_client.srem('queues:all', queue_name)
    return jsonify({"message": f"Queue {queue_name} removed."})

@api_bp.route('/queues/<queue_name>/forbidden/<worker_id>', methods=['POST'])
@require_admin
def forbid_worker_from_queue(queue_name, worker_id):
    """Forbid a specific worker from a single queue."""
    redis_client = get_redis()
    redis_client.sadd(f"queue:{queue_name}:forbidden_workers", worker_id)
    redis_client.sadd('workers:all', worker_id) # Ensure worker is in the list
    return jsonify({"message": f"Worker {worker_id} is now forbidden from queue {queue_name}."})

@api_bp.route('/queues/<queue_name>/forbidden/<worker_id>', methods=['DELETE'])
@require_admin
def unforbid_worker_from_queue(queue_name, worker_id):
    """Unforbid a specific worker from a single queue."""
    redis_client = get_redis()
    redis_client.srem(f"queue:{queue_name}:forbidden_workers", worker_id)
    return jsonify({"message": f"Worker {worker_id} is no longer forbidden from queue {queue_name}."})


# --- Captcha Handling ---
@api_bp.errorhandler(CaptchaRequired)
def handle_captcha_required(error: CaptchaRequired):
    return jsonify({
        "error":       "CaptchaRequired",
        "message":     error.message,
        "captcha_url": error.captcha_url
    }), 409

# --- Error Handling ---
@api_bp.errorhandler(400)
def handle_400(error):
    # Flask 1.0+ provides a JSON-based response for abort(400, description=...)
    # so this handler might be redundant if we only use that. But it's good practice.
    message = error.description or "The browser (or proxy) sent a request that this server could not understand."
    return jsonify({"error": "Bad Request", "message": message}), 400

@api_bp.errorhandler(404)
def handle_404(error):
    message = error.description or "The requested URL was not found on the server."
    return jsonify({"error": "Not Found", "message": message}), 404

@api_bp.errorhandler(415)
def handle_415(error):
    message = error.description or "Unsupported Media Type."
    return jsonify({"error": "Unsupported Media Type", "message": message}), 415

@api_bp.errorhandler(500)
def handle_500(error):
    # For abort(500, description=...), use the description.
    # Otherwise, it's an unhandled exception, so provide a generic message.
    message = error.description or "An internal server error occurred."
    current_app.logger.error(f"Server Error: {error}", exc_info=True)
    return jsonify({"error": "Internal Server Error", "message": message}), 500

@api_bp.route('/', methods=['GET'])
def main_dashboard():
    """
    Главный экран: ссылки на все мониторы, команды для скрапинга, сервера, воркера.
    """
    today = datetime.datetime.now().strftime('%d.%m.%Y')
    return render_template('main_dashboard.html', today=today)

@api_bp.route('/workers/manage', methods=['GET'])
def manage_workers():
    """
    Renders a page to manage all workers (labels, queues, forbidden status, etc).
    """
    return render_template('forbidden_workers.html')
