# AI-Based Placement Readiness and Future Performance Prediction Platform

This project will help students understand their placement readiness, identify skill gaps for a target role, and plan what to study next. The planned platform will bring together assessments, topic-level feedback, personalized learning roadmaps, and progress tracking for students and placement teams.

The repository starts with synthetic student data and a preprocessing demonstration. The synthetic workbooks support prototyping and data checks. Evaluating future placement predictions will require independently observed outcomes.

## Repository structure

| Folder | What goes there |
| --- | --- |
| `data/source/` | Original source files, including the raw workbook, cleaned workbook, and preprocessing script |
| `data/processed/` | Outputs from preprocessing |
| `data/synthetic/` | Additional synthetic datasets and fixtures |
| `backend/` | Python FastAPI service and PostgreSQL integration |
| `frontend/` | React and TypeScript interface |
| `ml/` | Scikit-learn preprocessing, model training, and evaluation code |
| `scripts/` | Utilities for repeatable local workflows |
| `docs/` | Design notes and user guides |
| `research/` | Experiment records and research notes |
| `tests/` | Automated tests |

`AGENTS.md` records project decisions and development rules. `.env.example` lists placeholders for the future database connection and OpenAI integration. Keep local credentials in an ignored `.env` file.

## Try the preprocessing script

From the project root, create and activate a local Python virtual environment. Install the dependencies and run the script using explicit paths for the uploaded filenames.

```bash
python -m pip install pandas numpy openpyxl scikit-learn matplotlib pillow
python "data/source/placement_preprocessing_pipeline (1).py" --input "data/source/unprocessed_pseudo_dataset (1).xlsx" --output "data/processed/cleaned_pseudo_dataset.xlsx"
```

The script cleans the workbook and generates validation reports, charts, and feature tables. It preserves the input when run with these arguments. Open the supplied cleaned workbook to explore an example of the audit and feature tables.
