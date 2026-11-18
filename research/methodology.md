# Research methodology

## Longitudinal simulation

The simulator preserves 100 source assessment IDs, dates and topic/subtopic percentages. Each student receives five additional attempts at a 14-day interval. The generator samples a student-level growth pattern and engagement level, maintains latent mastery per subtopic, and applies practice effects and separate measurement noise. The final readiness target is calculated after trajectories exist. The simulator label indicating the growth pattern is excluded from features.

The original scores and labels remain in the workbooks and the imported source records. The research computes a separate, consistent role-weighted score from baseline and simulated topic evidence. Relevance rules are a provisional implementation of the three-level weighting scheme described by the project deck.

## Prediction tasks and evaluation

Classification asks whether a learner currently below 75% first reaches the threshold within 60 days. A positive is observable as soon as a subsequent qualifying assessment occurs. A negative requires observed follow-up through the whole 60-day horizon. Incomplete negatives are censored. The benchmark uses complete follow-up for both classes to avoid learning the observation process. Here that limits eligibility to the first attempt.

Regression predicts the next observed standardized score at each earlier landmark. No target is assigned to the final assessment. Practice records may enter features only after they occurred. Role, prior progress, weighted gaps and historical topic changes use evidence available at the feature date. Student and assessment IDs are retained for provenance and isolation, outside the model input. Teams should keep the same policy for any future real outcomes.

We ordered cohorts by synthetic baseline date and split students 70/15/15 into training, validation and test. Different observations from the same learner never cross partitions. Candidate preprocessors and models fit on train only. Model and classification cutoff selection use validation only. The held-out test is used for final evaluation. The separate calendar-forward regression benchmark uses only outcomes observed strictly before its held-out landmark cutoff. The calendar-forward classification benchmark has no eligible training rows because enrollment dates are close together.

## Comparisons

- Classification selects maximum validation average precision, using Brier score to break ties. The threshold maximizes validation F1 on a fixed grid. The report includes precision, recall, F1, ROC-AUC, average precision, Brier score and confusion counts.
- Regression selects minimum validation MAE. Report MAE, RMSE and R², and subgroup errors only for groups with at least five distinct test students.
- No post-fit calibration or uncertainty interval is used. Three validation positives and the small test cohorts cannot support a reliable extra fitting step.
- Joblib pipelines include fitted transformations. Metadata records the feature contract, model ID, dependency versions, seed, test counts and digest. Only use artifacts produced by trusted local runs.

Reproduce from the repository root with `python -m ml.simulation.generate` and `python -m scripts.train_models`. See `temporal_validation.md` for split limitations.
