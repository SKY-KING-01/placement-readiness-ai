# Placement Readiness

Placement Readiness helps students measure role-specific skills, prepare for reassessment and follow a learning plan. Trainers can review assigned learners. Placement teams can view cohort-level skill gaps and workshop priorities. The repository also contains a reproducible synthetic-data study comparing readiness classifiers and score regressors.

## Local prerequisites

Install Python 3.11 or later, Node.js 20.19 or later (22 or later recommended), npm, and native PostgreSQL. Use your usual package manager on Linux, Homebrew or Postgres.app on macOS, or the Windows PostgreSQL installer with its SQL Shell. Start PostgreSQL and create a dedicated local role and database through pgAdmin or these commands using your PostgreSQL administrator account.

```bash
createuser --pwprompt placement_app
createdb --owner=placement_app placement_readiness
```

On Windows, find `createuser.exe` and `createdb.exe` in the PostgreSQL `bin` folder, or create the role and database in pgAdmin. On Linux, a package-managed PostgreSQL server may require running the commands as its administrative OS user. Grant the application role ownership of only this database.

## Start the backend

Run these commands from the repository root. Activate the virtual environment with the command for your shell.

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
```

```powershell
# Windows PowerShell activation
backend\.venv\Scripts\Activate.ps1
```

```bash
python -m pip install -e "./backend[dev]"
python -m scripts.setup_local
```

Edit the generated root `.env` and fill in `DATABASE_URL`. Use URL encoding for special characters in the PostgreSQL password. The setup script generates `JWT_SECRET_KEY` locally. Either root or backend `.env` is supported, with backend settings taking precedence. Keep both out of Git.

```bash
alembic -c backend/alembic.ini upgrade head
python -m scripts.import_source_data
python -m scripts.generate_synthetic_data --persist
python -m scripts.train_models
python -m scripts.evaluate_role_weights
python -m scripts.check_environment
uvicorn app.main:app --reload --port 8000
```

The API defaults to `http://localhost:8000/api/v1`. Swagger is at `http://localhost:8000/docs`. If port 8000 is in use, pick another backend port and set `PLACEMENT_API_PROXY` to its URL before starting Vite.

## Start the frontend

In a separate terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173` and select **Create an account** to register a student. Choose a career role, complete a standardized assessment, and open **Learning roadmap**. Adaptive practice and coding submissions have their own screens. Scheduled assessments open when due.

Provision each staff account from the repository root and choose a new local password in the hidden prompt. For trainer access, sign in as an administrator and assign the trainer to specific students in **Accounts**.

```bash
python -m scripts.provision_staff --role admin --email admin@example.org --name "Local Admin"
python -m scripts.provision_staff --role trainer --email trainer@example.org --name "Local Trainer"
python -m scripts.provision_staff --role placement --email placement@example.org --name "Local Placement"
```

### Synthetic demo and optional OpenAI

Use the **Synthetic cohort** switch in Placement Analytics. To explore synthetic student history with a local sign-in, set `SYNTHETIC_DEMO_PREDICTIONS=true` and run `python -m scripts.enable_demo_student STU0001` before signing in with the synthetic address printed by the script. The 60-day classification artifact is scoped to eligible first-assessment histories. Next-score regression can be shown for later synthetic assessments. Neither artifact serves forecasts for real users.

Set `OPENAI_API_KEY` and `OPENAI_MODEL` on the backend to enable the optional structured roadmap call. **Update roadmap** requests this integration. Standardized submissions always save a deterministic roadmap immediately, and missing credentials, API errors or invalid outputs use the same deterministic fallback. API use can incur charges. Configure token prices per million in the sample settings to log a usage-based estimate.

The Python screen supports sample cases and saved submissions. Evaluation requires a separate verified isolation service. See [runner design](docs/python_runner.md).

## Tests and research

```bash
# Set PLACEMENT_TEST_DATABASE_URL to a PostgreSQL server where your test role can create a schema.
python -m pytest -q backend/tests ml/tests
ruff check backend/app backend/alembic backend/tests ml scripts
ruff format --check backend/app backend/alembic backend/tests ml scripts
npm --prefix frontend test
npm --prefix frontend run build
```

The database tests use and remove a randomly named test schema. Without the test URL, the PostgreSQL tests are skipped and the unit and research tests still run.

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI, SQLAlchemy, Alembic and API tests |
| `frontend/` | React, Vite, Tailwind and student/staff portals |
| `data/source/` | Original workbooks and preprocessing script. The local original presentation is ignored by Git. |
| `data/synthetic/reassessments/` | Seeded six-attempt histories and source metadata |
| `ml/` | Simulation, temporal features, offline training and selected model artifacts |
| `research/` | Metrics, figures, study design and limitations |
| `docs/` | Source audit, mapping, setup details and implementation report |
| `scripts/` | Import, simulation, training and local setup commands |

For endpoint groups, import headers and validation details, see [API guide](docs/api.md). For the verification results and known limits, see the [implementation report](docs/IMPLEMENTATION_PROGRESS.md). The [research methodology](research/methodology.md) explains the synthetic data and splits.
