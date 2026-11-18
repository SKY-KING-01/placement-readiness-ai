from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from ml.preprocessing.pipelines import prediction_pipeline


def classifiers(seed):
    return {
        "Logistic Regression": prediction_pipeline(
            LogisticRegression(max_iter=1500, C=0.5, random_state=seed), scale=True
        ),
        "Random Forest": prediction_pipeline(
            RandomForestClassifier(n_estimators=240, min_samples_leaf=5, random_state=seed, n_jobs=2)
        ),
        "CatBoost": prediction_pipeline(
            CatBoostClassifier(
                iterations=220,
                depth=4,
                learning_rate=0.035,
                random_seed=seed,
                verbose=False,
                thread_count=2,
                allow_writing_files=False,
            )
        ),
    }
