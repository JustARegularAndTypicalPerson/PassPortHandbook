# Worker & Redis Protocol Documentation

## 1. Overview

This document outlines the Redis data structures and protocols used for the distributed job queueing system. The system consists of two main components:

- **API Server (Flask)**: Enqueues jobs, monitors their status, and provides results.
- **Workers (Python Scripts)**: Dequeue and process jobs from the Redis queues.

Workers must follow this protocol to ensure seamless integration and correct state management within the system.

## 2. Redis Data Structures

The system relies on several key patterns in Redis:

| Key Pattern               | Type   | Description                                                                                             |
| ------------------------- | ------ | ------------------------------------------------------------------------------------------------------- |
| `job:<job_id>`            | Hash   | Stores all data and metadata for a single job. The `<job_id>` is a UUID.                                |
| `jobs:queue`              | List   | The default queue for pending jobs. Workers pop `job_id`s from this list.                               |
| `jobs:queue:<name>`       | List   | A named queue for a specific type of job.                                                               |
| `queues:all`              | Set    | A set of all valid queue names (e.g., "default", "priority"). Used by the API to validate queues.       |
| `queue:<name>:forbidden_workers` | Set    | A set of `worker_id`s forbidden from processing jobs from `jobs:queue:<name>`.                        |
| `jobs:dead-letter`        | List   | A queue for jobs that have failed critically and cannot be retried.                                     |
| `workers:all`             | Set    | A set of all `worker_id`s that have processed at least one job. Used for monitoring worker activity.    |
| `logs:stream`             | Stream | A centralized stream for all worker logs.                                                               |

---

## 3. Job Lifecycle & Worker Responsibilities

A worker's primary responsibility is to fetch a job, process it, and update its status in Redis.

### Worker Startup & Queue Selection

To improve system stability, a worker can be dynamically forbidden from processing jobs from a specific queue, for instance, if it has a high failure rate for that queue's job types. The API or an administrative tool is responsible for adding/removing worker IDs from these forbidden sets.

A worker must respect these restrictions during its startup sequence:

1.  **Identify Target Queues**: The worker should have a configured list of queues it intends to watch (e.g., `priority`, `default`).
2.  **Check for Restrictions**: For each target queue `<name>`, the worker must check if its `worker_id` is present in the `queue:<name>:forbidden_workers` set.
    - **Example Check**: `SISMEMBER queue:priority:forbidden_workers "wrk-xyz"`
3.  **Build Final Queue List**: The worker constructs the final list of Redis queue keys for the `BRPOP` command, excluding any queues it is forbidden from.
    - **Example Scenario**: If a worker is configured for `priority` and `default` queues but is forbidden from `priority`, its final list of keys for `BRPOP` should only contain `jobs:queue`.

### Main Processing Loop

The main loop consists of the following steps:

#### Step 1: Fetch a Job

A worker should block and wait for a `job_id` to become available in one of the queues. It's recommended to use `BRPOP` to atomically pop from one or more queues.
The `BRPOP` command should be constructed using the final queue list determined during startup.

**Example:**
`BRPOP jobs:queue:priority jobs:queue 0`

#### Step 2: Acknowledge and Start the Job

Once a `job_id` is retrieved, the worker must immediately update the job's hash to reflect that it is being processed.

1.  **Fetch Job Details**: `HGETALL job:<job_id>`
2.  **Update Status**: Set the status to `in_progress`, and record the `worker_id` and `started_at` timestamp.
    - `HSET job:<job_id> status "in_progress" worker_id "wrk-xyz" started_at "2023-10-27T10:00:00Z"`
3.  **Register Worker**: Add the worker's ID to the global set of workers.
    - `SADD workers:all "wrk-xyz"`

#### Step 3: Perform the Work

The worker executes the task based on the parameters in the job hash (e.g., `scraper_type`, `target_id`).

##### Cancellation
For long-running jobs, the worker should periodically check if a cancellation has been requested. The API signals this by updating the job's status to `cancelling`. The worker should check this field and gracefully terminate if the status is no longer `in_progress`.

**Example Check:** `HGET job:<job_id> status`

#### Step 4: Report Completion

Upon successful completion of the task:

1.  **Update Status**: Set status to `completed`.
2.  **Set Timestamps**: Record the `completed_at` timestamp.
3.  **Store Result**: Store the result payload as a JSON string in the `result_data` field.

**Example:**
`HSET job:<job_id> status "completed" completed_at "2023-10-27T10:05:00Z" result_data "{\"items_scraped\": 150}"`

#### Step 5: Report Failure

If the job fails:

1.  **Update Status**: Set status to `failed`.
2.  **Set Timestamps**: Record the `completed_at` timestamp.
3.  **Store Error**: Store a descriptive error message in the `error_message` field.
4.  **(Optional) Move to Dead-Letter Queue**: For critical, non-retriable errors, the worker can push the `job_id` to the `jobs:dead-letter` queue for manual inspection.
    - `LPUSH jobs:dead-letter <job_id>`

**Example:**
`HSET job:<job_id> status "failed" completed_at "2023-10-27T10:01:00Z" error_message "Target page returned a 404 error."`

---

## 4. Job Data Model (Hash Fields)

The following fields are defined for the `job:<job_id>` hash.

| Field              | Type   | Description                                                                 | Set By      |
| ------------------ | ------ | --------------------------------------------------------------------------- | ----------- |
| `job_id`           | string | Unique identifier for the job.                                              | API         |
| `status`           | string | `pending`, `in_progress`, `completed`, `failed`, `cancelled`, `cancelling`. | API, Worker |
| `queue`            | string | The name of the queue the job was enqueued in (e.g., "default").            | API         |
| `enqueued_at`      | string | ISO 8601 UTC timestamp of when the job was created.                         | API         |
| `scraper_type`     | string | The type of scraper to use (e.g., "playwright", "requests").                | API         |
| `operation_type`   | string | The specific scraping operation to perform.                                 | API         |
| `target_id`        | string | The primary identifier for the scraping target (e.g., a user ID, URL).      | API         |
| `period`           | string | Optional time period for the data being scraped (e.g., "2023-10").          | API         |
| `page_num`         | int    | Optional page number for paginated scraping operations.                     | API         |
| `started_at`       | string | ISO 8601 UTC timestamp of when the worker started the job.                  | Worker      |
| `completed_at`     | string | ISO 8601 UTC timestamp of when the job finished (successfully or not).      | Worker      |
| `worker_id`        | string | Unique identifier for the worker processing the job.                        | Worker      |
| `result_url`       | string | A URL where the full job details and result can be fetched.                 | API         |
| `result_data`      | string | A JSON string containing the job's output data.                             | Worker      |
| `error_message`    | string | A descriptive message if the job failed.                                    | Worker      |

---

## 5. Logging Protocol

Workers should log important events to the centralized Redis Stream for real-time monitoring.

- **Key**: `logs:stream`
- **Command**: `XADD`

Each log entry should be a set of key-value pairs.

| Field       | Description                               |
| ----------- | ----------------------------------------- |
| `level`     | Log level (e.g., `INFO`, `WARNING`, `ERROR`). |
| `message`   | The log message string.                   |
| `worker_id` | The ID of the worker generating the log.    |
| `job_id`    | The ID of the job being processed, if any.  |
| `timestamp` | ISO 8601 UTC timestamp of the log event.    |

**Example:**
`XADD logs:stream * level INFO message "Starting job" worker_id "wrk-xyz" job_id "..."`
