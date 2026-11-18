# Data quality report

| Core sheet | Raw records | Distinct keys | Exact duplicate rows | Missing cells | Recovered records |
| --- | ---: | ---: | ---: | ---: | ---: |
| Students | 125 | 100 | 10 | 22 | 100 |
| Authentication | 125 | 100 | 10 | 147 | 100 |
| Career_Profile | 125 | 100 | 10 | 22 | 100 |
| Assessments | 125 | 100 | 10 | 22 | 100 |
| Topic_Scores | 725 | 700 | 10 | 22 | 700 |
| Subtopic_Scores | 2,125 | 2,100 | 10 | 22 | 2,100 |
| AI_Roadmaps | 316 | 291 | 10 | 22 | 291 |
| Mentorship | 105 | 80 | 10 | 22 | 80 |
| Question_Bank | 1,625 | 1,600 | 10 | 22 | 1,600 |

The original pipeline recovered the raw workbook and matched normalized values and keys in the cleaned workbook. Student/assessment ownership, topic parents, score bounds and rollups passed the pipeline’s validation.

Blank first-login dates are permitted. Injected defects include missing values, out-of-range scores, invalid dates, whitespace and repeated rows. No restoration of ambiguous question fractions was attempted.

571 date-like answer options affect 252 of 1600 questions. The source marks 1348 as structurally usable. This check cannot establish factual correctness or company provenance.

The workbook has 15 distinct role names across profiles and assessments, 700 student-scoped topic records and repeated positional subtopic IDs. Normalize taxonomy by topic name and parent-plus-subtopic name while retaining the original scoped IDs.

Observed source readiness labels: {'Developing': 35, 'Near Ready': 64, 'Placement Ready': 1}. Every student has one baseline and no reassessment or item-level response records. Exclude future profiles, roadmaps, mentorship, identities, source readiness labels and held-out records from model fitting.
