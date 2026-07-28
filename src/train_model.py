from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "fraud_oracle.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_model.joblib"

TARGET_COLUMN = "FraudFound_P"


def load_data() -> pd.DataFrame:
    """Load the main vehicle-claim fraud dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset was not found at: {DATA_PATH}"
        )

    dataframe = pd.read_csv(DATA_PATH)

    if TARGET_COLUMN not in dataframe.columns:
        raise ValueError(
            f"Target column '{TARGET_COLUMN}' is missing."
        )

    return dataframe


def prepare_features(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Separate features and target and remove identifier columns."""

    columns_to_drop = [
        TARGET_COLUMN,
        "PolicyNumber",
    ]

    existing_columns = [
        column
        for column in columns_to_drop
        if column in dataframe.columns
    ]

    features = dataframe.drop(columns=existing_columns)
    target = dataframe[TARGET_COLUMN]

    return features, target


def build_pipeline(features: pd.DataFrame) -> Pipeline:
    """Build preprocessing and logistic-regression pipeline."""

    categorical_columns = features.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()

    numerical_columns = features.select_dtypes(
        include=["number"]
    ).columns.tolist()

    numerical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "scaler",
                StandardScaler(),
            ),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="most_frequent"),
            ),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
            ),
        ]
    )

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numerical",
                numerical_pipeline,
                numerical_columns,
            ),
            (
                "categorical",
                categorical_pipeline,
                categorical_columns,
            ),
        ]
    )

    model = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    )

    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("model", model),
        ]
    )


def evaluate_model(
    pipeline: Pipeline,
    x_test: pd.DataFrame,
    y_test: pd.Series,
) -> None:
    """Print important fraud-model evaluation metrics."""

    predictions = pipeline.predict(x_test)
    fraud_probabilities = pipeline.predict_proba(x_test)[:, 1]

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            digits=4,
        )
    )

    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions))

    roc_auc = roc_auc_score(
        y_test,
        fraud_probabilities,
    )

    pr_auc = average_precision_score(
        y_test,
        fraud_probabilities,
    )

    print(f"\nROC-AUC: {roc_auc:.4f}")
    print(f"PR-AUC:  {pr_auc:.4f}")


def main() -> None:
    dataframe = load_data()

    print(f"Dataset shape: {dataframe.shape}")
    print("\nTarget distribution:")
    print(dataframe[TARGET_COLUMN].value_counts())
    print(
        dataframe[TARGET_COLUMN]
        .value_counts(normalize=True)
        .round(4)
    )

    features, target = prepare_features(dataframe)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.20,
        random_state=42,
        stratify=target,
    )

    pipeline = build_pipeline(x_train)

    print("\nTraining fraud-detection model...")
    pipeline.fit(x_train, y_train)

    evaluate_model(
        pipeline,
        x_test,
        y_test,
    )

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(pipeline, MODEL_PATH)

    print(f"\nModel saved at: {MODEL_PATH}")


if __name__ == "__main__":
    main()