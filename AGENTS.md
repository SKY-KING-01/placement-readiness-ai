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
