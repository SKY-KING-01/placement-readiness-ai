# Readiness classification

Selected **Random Forest** by validation average precision, using validation Brier score as the tie-breaker. The decision threshold was chosen by validation F1. Cohorts: train 68 (30 positive), validation 15 (3 positive), test 15 (7 positive). Metrics in the CSV are from held-out students. Probabilities were not recalibrated because the validation sample was small. Complete 60-day follow-up is available for first attempts only. The deployed demonstration therefore limits readiness probabilities to that landmark; it does not estimate real placement outcomes.
