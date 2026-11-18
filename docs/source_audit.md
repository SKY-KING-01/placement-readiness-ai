# Source audit

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| unprocessed_pseudo_dataset (1).xlsx | 429,037 | `25cfd3bbd76a2ade5ae3ff4088352afe68a930d0e2a697629600eaf1024eaebb` |
| cleaned_pseudo_dataset (1).xlsx | 742,839 | `e8f22bfde56c5e738311ddbab9e8466d3b6fe77d69d5b9af0dba859e57466f2e` |
| placement_preprocessing_pipeline (1).py | 43,085 | `3070ff6bdecbe0e188025357301b0a8e5989ce4a32665f5a5ee6c20d60d9c67f` |
| AI_ML.pptx | 1,683,981 | `b40baf5738af2718881623497ca404923ca4271257b5c30c3f1a1c7073f18e2e` |

The 18-slide deck describes assessment, role-aware diagnosis, a personalized roadmap, mentorship and placement analytics. It proposes a 12-role × 39-skill matrix from high/medium/low relevance. The two workbooks lack that matrix. Use versioned prototype weights and record their provenance.

Baseline assessment example: `ASM0001` is a Baseline Assessment.
Topic example: `T0001-01` represents Quantitative Aptitude. Its first subtopic is `S01-01` (Percentages & Ratios).
Question example: `Q0001` has category Aptitude and difficulty Medium.

The deck is available separately and contains student names and roll numbers. Keep it out of Git.

The Python pipeline validates the nine source schemas, parses typed fields, collapses exact and consistent same-key records, verifies scores and foreign keys, and fits demonstration transforms on training students only. Its reports and feature sheets are outputs. The import uses its validation and keeps the original values separately.
