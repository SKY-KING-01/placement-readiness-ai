# Data provenance

The uploaded workbooks supply synthetic baseline scores, career profiles, source question variants and prior explanatory reports. SHA-256 values and worksheet types appear in the source audit. The presentation described the intended platform and weighting scheme. It remains local because it contains student identifiers.

The normalized PostgreSQL schema preserves the source keys. Workbook password hashes, contact phone numbers and student identifiers are excluded from training and OpenAI requests. The original question bank lacks evidence for prior company use. The import therefore seeds eligible questions as practice and quarantines 252 records requiring answer-option review.

The simulated history comes from the baseline scores and the seed-42 generator. Generator metadata appears in `data/synthetic/reassessments/metadata.json`. The assessment dates in these files are part of simulated evidence. Censored observations, cohorts and longitudinal targets are recorded in `synthetic_labels.csv`. The project contains no independently measured placement, hiring or student intervention outcomes.
