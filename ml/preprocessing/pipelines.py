from app.ml.features import FEATURES
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def prediction_pipeline(model, scale=False):
    numeric = [column for column in FEATURES if column != "role"]
    transform = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    if scale:
        transform = make_pipeline(transform, StandardScaler())
    preprocessor = ColumnTransformer(
        [
            ("numeric", transform, numeric),
            ("roles", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["role"]),
        ]
    )
    return make_pipeline(preprocessor, model)
