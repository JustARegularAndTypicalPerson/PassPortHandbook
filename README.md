# Pass-port Handbook and Job Dispatch (Python)

This is a portfolio snapshot of the handbook and job-dispatch application I worked on during freelance development for Pass-port (2024–2026). The source shows a Flask application with account and business flows, SQLAlchemy models, Redis-backed job queues and status endpoints, Playwright-based business-directory automation, QR-code routes, and a Yclients integration.

The snapshot excludes browser profiles, customer and company media, downloaded website captures, local editor settings, brand fonts, production configuration, and credentials. The original client landing page and legal pages are not included; the replacement pages are portfolio placeholders, not production pages or legal advice.

## Project areas

- `app/`, `auth/`: Flask app setup, account flows, and business models.
- `api/`: job submission, status/result/log endpoints, Redis helpers, and scraper modules.
- `ad/`, `qr/`, `yapi/`: business pages, QR generation, and Yclients signup integration.
- `worker_redis_protocol.md`: worker-side queue and message protocol notes.

## Local setup

The project requires Python 3.10 or newer, a Redis service, and the Python packages in `requirements.txt`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = "generate-a-new-random-value"
$env:ADMIN_TOKEN = "generate-a-new-admin-token"
$env:API_TOKEN = "generate-a-new-api-token"
$env:DATABASE_URL = "sqlite:///portfolio.db"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python scripts/initialize_db.py
python -m flask --app wsgi:app run
```

For a deployed environment, provide stable, newly generated secrets through the platform's secret manager. Use a protected Redis endpoint and a database URL appropriate for that environment. The random development `SECRET_KEY` fallback changes on each process start, so sessions will not persist between restarts unless `SECRET_KEY` is set.

Optional integration settings:

- Yclients: `YCLIENTS_PARTNER_TOKEN`, `YCLIENTS_ACCESS_TOKEN`, `YCLIENTS_APPLICATION_ID`, `YCLIENTS_API_KEY`, and `YCLIENTS_WEBHOOK_URL`.
- The Playwright login helper reads `YANDEX_LOGIN` and `YANDEX_PASSWORD`; it has not been verified against a live account. It creates local browser state when run. Do not commit that state or use it against an account without authorization.

Admin and job-submission endpoints return `503` when their required tokens are not configured and reject missing or invalid tokens. Do not expose these services publicly without a deployment-specific security review.

## Verification and limitations

- Python source compiles with `compileall`.
- No automated test suite is included in this source snapshot.
- Database, Redis, worker, and third-party integrations have not been run end to end here.
- The client branding, captured browser data, production addresses, phone numbers, and original public-site assets are intentionally omitted.
- No separate reuse license is included; this repository is provided for portfolio review.