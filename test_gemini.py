import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"


def main() -> None:
    load_dotenv(ENV_PATH)

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the .env file."
        )

    if not model_name:
        raise RuntimeError(
            "GEMINI_MODEL is missing from the .env file."
        )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=(
            "Explain motor insurance fraud detection "
            "in one simple sentence."
        ),
    )

    print("Gemini connection successful")
    print("Model:", model_name)
    print("Response:", response.text)


if __name__ == "__main__":
    main()