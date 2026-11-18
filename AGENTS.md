# Project instructions

## Technology

- Build the backend with Python and FastAPI.
- Build the frontend with React and TypeScript.
- Use PostgreSQL for persistence.
- Use Scikit-learn for preprocessing and evaluation, and compare Random Forest and CatBoost models.
- Use the OpenAI API for generative AI features.
- Develop locally without Docker.
- Support Python 3 as the initial coding assessment language.

## Data and experiments

- Preserve all original source datasets in `data/source/` byte for byte. Write generated outputs to `data/processed/` or `data/synthetic/` as appropriate.
- Prevent data leakage. Split by student before fitting any preprocessing or model. Fit only on training data and keep held-out test data for final evaluation. When predicting future performance, use only information available at the prediction time.
- Make experiments reproducible. Record the dataset version, split assignments, random seeds, dependency versions, model settings, and evaluation metrics.
- Keep real student personal information and credentials out of Git. Use synthetic records for development and tests.
- Run the relevant tests before claiming an implementation is complete.

## Development commands

- From the project root, install with `python -m pip install -e "./backend[dev]"`.
- Migrate native PostgreSQL with `alembic -c backend/alembic.ini upgrade head`. Run the workbook import before simulation persistence.
- Run backend and research checks with `python -m pytest -q backend/tests ml/tests`. Set `PLACEMENT_TEST_DATABASE_URL` for database tests.
- Run `ruff check backend/app backend/alembic backend/tests ml scripts` and `ruff format --check backend/app backend/alembic backend/tests ml scripts`.
- Run frontend checks with `npm --prefix frontend test` and `npm --prefix frontend run build`.
- Keep API routes below `/api/v1`. Enforce role and ownership checks on the server. Keep grading keys and hidden test cases out of public payloads.
- Use OpenAI only through the backend and send aggregated learning evidence without student identifiers. Keep deterministic fallback available.
- The HTTP process stores Python submissions. Add an execution adapter only after verifying isolation independently of application credentials.
- Keep `AI_ML.pptx` outside Git because it contains student identifiers. Use the local ignored original for the audit.
