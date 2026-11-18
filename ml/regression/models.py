from catboost import CatBoostRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

from ml.preprocessing.pipelines import prediction_pipeline


class LastScore(DummyRegressor):
    """Scikit-learn estimator with a fitted-state check and an identity prediction."""

    def predict(self, X, return_std=False):
        super().predict(X, return_std=return_std)
        return X.to_numpy().reshape(-1)


def regressors(seed):
    return {
        "Last score": make_pipeline(
            FunctionTransformer(validate=False, feature_names_out="one-to-one"), LastScore()
        ),
        "Random Forest": prediction_pipeline(
            RandomForestRegressor(n_estimators=240, min_samples_leaf=5, random_state=seed, n_jobs=2)
        ),
        "CatBoost": prediction_pipeline(
            CatBoostRegressor(
                iterations=350,
                depth=5,
                learning_rate=0.045,
                verbose=False,
                random_seed=seed,
                thread_count=2,
                allow_writing_files=False,
            )
        ),
    }
