# Python assessment execution

The API stores Python 3 source, owner, problem, status, timestamps and an optional score. Public problem payloads expose only sample cases. A run request returns HTTP 503 with a machine-readable status until a verified worker exists. Setting `PYTHON_EXECUTION_ENABLED=true` without a verified implementation still returns `no_verified_worker`. The submit and history endpoints continue to work.

`app.services.python_runner` defines an evaluator contract with time, memory, maximum output and case inputs. It supports weighted partial scoring and exact coverage validation of results. A worker should consume database-queued submissions, execute outside the API process, redact hidden-case details and persist scores transactionally. The test suite uses predetermined grading outcomes to exercise scoring.

| Host | Verification status |
| --- | --- |
| Linux | The environment has no verified separately privileged grader. A future adapter would need audited process and network isolation, read-only runtime mounts, no project paths, restricted system calls, per-job limits and an unprivileged worker identity. |
| Windows | The local application does not provide verified isolation. Processes and timeouts alone leave filesystem, identity and network access available. |
| macOS | The local application does not provide a verified execution backend. Require an independently administered isolated worker before enabling grading. |

No platform invokes submitted code. The application does not pass database credentials or OpenAI credentials to an executor. Public and hidden sample test payloads are separated in the database and the authorization layer.
