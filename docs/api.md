# API workflows

Open `http://localhost:8000/docs` for the generated paths, methods, schemas and interactive request forms. Every business API uses `/api/v1`. Use an access token in the Authorization header. Use the refresh endpoint to rotate a refresh token. Registration grants only a student role.

| Group | Paths and actions |
| --- | --- |
| Authentication | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` |
| Student and careers | `/roles`, `/roles/{id}/skills`, `/students/me`, `/students/me/role`, `/students/me/progress` |
| Standardized assessments | `/assessments` and `/assessments/{id}`, with `/activate`, `/responses`, `/submit` and `/results` |
| Adaptive practice | `/practice/start` and `/practice/{id}/next-question` or `/responses` |
| Coding | `/coding/questions`, `/coding/submissions` and `/coding/submissions/{id}`, with `/run-samples` |
| Predictions | `/students/me/predictions`, `/students/me/prediction-history` |
| Roadmaps | `/students/me/roadmap` and `/students/me/roadmap/tasks/{id}` |
| Question administration | `/admin/catalog`, `/admin/questions`, `/admin/questions/import`, and per-question editing, approval and deactivation |
| Accounts and catalogs | `/admin/users`, `/admin/trainer-assignments`, `/companies`, `/admin/companies` and `/admin/companies/{id}`, `/admin/roles` and `/admin/roles/{id}`, `/admin/roles/{id}/weights`, `/admin/model-versions` |
| Trainer | `/trainers/students`, `/trainers/students/{id}/analytics`, `/trainers/questions`, `/trainers/questions/{id}/reviews` |
| Placement cell | `/placement/overview`, `/placement/skill-gaps`, `/placement/workshop-recommendations` |
| Readiness probe | `/health` |

Paginated listing APIs use `limit` and `offset` where shown in Swagger. The placement views suppress groups below `MIN_COHORT` and split synthetic data from real registrations. The aggregate support threshold prioritizes learning opportunities.

## Import questions

Use UTF-8 CSV or the active worksheet of an XLSX file. The required headers are:

```csv
text,category,difficulty,topic_id,subtopic_id,option_a,option_b,correct_option
```

Optional columns are `option_c`, `option_d`, `skill_id`, `role_id`, `company_id`, `year`, `placement_round`, `source_url`, `verification` and `explanation`. Use actual catalog IDs from the administration UI or API. Set the correct option to A, B, C or D. Use text for fractions in Excel. Each file is limited to 2 MB and 500 rows.

Preview identifies duplicates and malformed rows. Import saves valid rows as pending. An administrator must review provenance before approving a claimed previous-company question and must provide both a company and a source URL. For Python problems use the form or JSON API, supplying at least one public and one hidden test case.

## Score calculation

A standardized assessment assigns easy and medium questions to every topic in its versioned role blueprint. Points earned divided by points available give the subtopic percentage. Topic scores pool subtopics weighted by points available. The readiness percentage weights each assessed topic by role relevance. Out-of-blueprint topics are recorded as unassessed, and unanswered assigned questions count as zero. Adaptive practice has its own scoring and cannot overwrite readiness.
