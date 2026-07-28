from pathlib import Path

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_model.joblib"
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "fraud_oracle.csv"


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Model not found. Run src/train_model.py first."
        )

    pipeline = joblib.load(MODEL_PATH)

    dataframe = pd.read_csv(DATA_PATH)

    sample_claim = dataframe.drop(
        columns=["FraudFound_P", "PolicyNumber"]
    ).iloc[[0]]

    fraud_probability = pipeline.predict_proba(
        sample_claim
    )[0, 1]

    prediction = int(
        fraud_probability >= 0.50
    )

    print(f"Fraud probability: {fraud_probability:.4f}")
    print(
        "Prediction:",
        "Potential fraud" if prediction == 1 else "Normal claim",
    )


if __name__ == "__main__":
    main()