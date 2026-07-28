import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "fraud_oracle.csv"
OUTPUT_PATH = PROJECT_ROOT / "test_claim.json"


def main() -> None:
    dataframe = pd.read_csv(DATA_PATH)

    columns_to_remove = [
        "FraudFound_P",
        "PolicyNumber",
    ]

    sample_claim = dataframe.drop(
        columns=[
            column
            for column in columns_to_remove
            if column in dataframe.columns
        ]
    ).iloc[0]

    request_body = {
        "claim": sample_claim.to_dict()
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            request_body,
            file,
            indent=4,
            default=str,
        )

    print(f"Test request created: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()