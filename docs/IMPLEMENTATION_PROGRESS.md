# Implementation and verification

The local project is in `/workspace/work/placement-readiness-ai`. Start with the native PostgreSQL instructions in the repository README and use `docs/api.md` for route groups and import formats.

## Phase results

| Phase | State | Evidence and remaining work |
| --- | --- | --- |
| Source audit | Implemented and tested | Parsed both workbooks and all 18 slides, reviewed the Python pipeline, and matched raw recovery against the cleaned workbook. All four original digests are recorded. |
| 1. PostgreSQL and migration | Implemented and tested | Upgraded, downgraded and upgraded schema 001 on native PostgreSQL 16.2. Checked schema drift and an orphan foreign key. Re-import added zero rows. |
| 2. Reassessment simulation | Implemented and tested | Preserved 100 baselines and added 500 reassessments. Generated 600 assessment, 4,200 topic-score and 12,600 subtopic-score rows. Tested reproducibility, ranges, IDs and ordering. |
| 3. Readiness scoring | Implemented and tested | Measured subtopic, topic and role-weighted readiness scores with versioned weights, coverage and separate practice. |
| 4. Classification | Implemented and tested | Trained Logistic Regression, Random Forest and CatBoost. Validated censoring and disjoint cohorts. Strict calendar-forward classification is infeasible with the dates provided. |
| 5. Regression and inference | Implemented and tested | Compared last score, Random Forest and CatBoost. Ran a secondary calendar-forward regression check. Tested artifact validation and authenticated prediction history. Artifacts serve only explicit synthetic demos. |
| 6. Question bank | Implemented and tested | Validated CSV/XLSX preview, duplicate and option checks, approval, editing, deactivation, and source attribution fields. Seeded 1,348 eligible practice questions. |
| 7. Python coding | Partially implemented | Supported both Python problem styles, public cases, authenticated submission storage and result-scoring contract tests. No verified worker was available, so execution and live grading are disabled. |
| 8. Adaptive practice | Implemented and tested | Weighted skill gap, role, difficulty and company signals. Tested selection records, duplicate avoidance and separation from standardized history. |
| 9. OpenAI roadmap | Partially implemented | Deterministic roadmap, task tracking and reassessment updates tested end to end. Official SDK structured response and grounding tested with a mock. Live API calls require backend credentials and a selected model. |
| 10. FastAPI | Implemented and tested | 51 versioned paths and 56 operations for auth, roles, students, standardized assessment, practice, coding, predictions, roadmaps, admin, trainer and placement analytics. Tested refresh rotation, ownership and staff role guards. |
| 11. React | Implemented and tested | Student overview, career, assessment, practice, Python and roadmap screens. Trainer assignment and reviews, placement reports, and administration. Passed TypeScript, Vite build, component tests and a Chromium student journey at desktop and mobile sizes. |
| 12. Placement analytics | Implemented and tested | Native PostgreSQL tests verified role-restricted cohort analysis, privacy suppression and role-weighted workshops. Synthetic and live cohorts are filtered separately. |
| 13. Research | Partially implemented | Reproducible synthetic evaluation and role-weight sensitivity completed. Real-student intervention and calibration studies are designed and remain unrun. |
| 14. Native local setup | Implemented and tested | Verified Linux with PostgreSQL, Alembic, Uvicorn and Vite without containers. Windows/macOS setup is documented and has no test result here. |
| 15. Test suite | Implemented and tested | PostgreSQL/API, scoring, OpenAI mocks, runner guard, simulation, feature leakage, model evaluation, frontend and browser smoke checks completed. |

## Verified counts and results

The source import inserted 100 students, 100 career profiles, 100 assessments, 700 topic scores, 2,100 subtopic scores, 291 source roadmap rows, 80 mentorship records, 1,600 questions and 6,400 options. It also created 15 roles, 29 skills, 435 versioned skill weights and 15 standardized blueprints. The 571 flagged date-like options affect 252 quarantined questions. Two separately authored coding exercises are included as local fixtures. All 15 stock blueprints have eligible questions at their requested difficulties.

With simulation persistence, the synthetic totals are 600 assessments, 4,200 topic scores, and 12,600 subtopic scores. Source score evidence and generated records are distinguished.

Random Forest won both selections. On the 15-student classification test, ROC-AUC was 0.768, average precision was 0.799 and Brier score was 0.213. The cutoff returned seven true positives, seven false positives, one true negative and zero false negatives. The held-out next-score RMSE was 2.82 and MAE was 2.33 over 75 outcomes. The stricter calendar-forward regression test had MAE 2.32 over 15 outcomes. Both selected pipelines and metadata are in `ml/artifacts/`. Role weighting changed the top-three gap list for 44 of 100 synthetic baselines.

## Verification commands and outcomes

- PostgreSQL 16.2 native migration and repeat workbook import passed. The database was initialized in the workspace without a system package install.
- `python -m pytest -q backend/tests ml/tests` with a native PostgreSQL test URL passed 12 tests.
- `ruff check` and `ruff format --check` passed for application code, migrations, tests and helper scripts.
- `npm --prefix frontend test` passed 4 tests. `npm --prefix frontend run build` passed TypeScript and Vite.
- A headless Chromium check exercised registration, role choice, eight-question assessment, deterministic roadmap and task completion, adaptive practice, and Python submission storage through the running React and FastAPI servers. Chromium also verified trainer access to an assigned student, the administrator model catalog, and the placement trend and workshop views. The 390 px viewport had no page-level horizontal overflow.
- The default ports documented in the README are 5173 and 8000. This environment already used port 8000, so the integrated smoke test used Vite 5174 and Uvicorn 8765.

## Outstanding dependencies and limits

| Item | State | Dependency |
| --- | --- | --- |
| Live Python grading | Blocked or not implemented | Requires a separately verified isolated execution worker. The API continues to accept and retain source submissions. |
| Live OpenAI verification | Implemented but untested | Requires backend API credentials and access to the selected model. The fallback path is verified. |
| Actual placement prediction / student pilot | Blocked or not implemented | Requires consented longitudinal data, independent outcomes and outcome validation. Synthetic metrics cannot be used for selection or exclusion. |

The original PowerPoint is present locally and ignored by Git because it includes student identifiers. See `source_audit.md`, `data_quality_report.md` and `migration_mapping.md` for data handling. See `research/limitations.md` for evidence limits.
