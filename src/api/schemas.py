from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClaimRequest(BaseModel):
    claim: dict[str, Any] = Field(
        ...,
        description="Vehicle-insurance claim attributes",
    )


class PredictionResponse(BaseModel):
    prediction: int
    prediction_label: str
    fraud_probability: float
    risk_level: str
    threshold: float


class PolicyQuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Question about the indexed motor policy",
        examples=[
            "What third-party liabilities are covered?",
        ],
    )
    top_k: int = Field(
        default=4,
        ge=1,
        le=8,
        description="Number of policy chunks to retrieve",
    )
    min_similarity_score: float = Field(
        default=0.25,
        ge=-1.0,
        le=1.0,
        description=(
            "Minimum semantic similarity required for a retrieved "
            "policy chunk."
        ),
    )
    claim_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="Optional claim ID for audit logging a policy RAG query.",
    )


class ClaimCreateRequest(BaseModel):
    claim_id: str = Field(..., min_length=3, max_length=50)
    policy_number: str | None = None
    customer_name: str | None = None
    vehicle_number: str | None = None
    accident_date: str | None = None
    reported_date: str | None = None
    claimed_amount: float | None = None
    status: str = "open"


class ClaimUpdateRequest(BaseModel):
    policy_number: str | None = None
    customer_name: str | None = None
    vehicle_number: str | None = None
    accident_date: str | None = None
    reported_date: str | None = None
    claimed_amount: float | None = None
    status: str | None = None


class RiskAssessmentRequest(BaseModel):
    manual_features: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional manually supplied Oracle fraud-model features.",
    )


class AssessmentRequest(BaseModel):
    manual_features: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional manually supplied Oracle fraud-model features used "
            "when generating fraud risk."
        ),
    )
    policy_findings: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional policy RAG result or manually supplied policy "
            "findings to include in the assessment."
        ),
    )


class ClaimAssistantRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=800,
        description=(
            "Reviewer question about the claim, extracted data, "
            "validation, assessment, or policy context."
        ),
    )
    use_llm: bool = Field(
        default=False,
        description=(
            "When true, Gemini is used to generate a grounded answer. "
            "When false, the API returns a deterministic briefing."
        ),
    )
    include_policy_context: bool = Field(
        default=False,
        description=(
            "Retrieve relevant policy sources and include them in "
            "assistant context without approving or rejecting claims."
        ),
    )
    top_k: int = Field(default=4, ge=1, le=8)
    min_similarity_score: float = Field(
        default=0.25,
        ge=-1.0,
        le=1.0,
    )


class ReviewDecisionRequest(BaseModel):
    reviewer_name: str = Field(..., min_length=1, max_length=200)
    decision: str = Field(..., min_length=1, max_length=50)
    comment: str | None = Field(default=None, max_length=2000)


class FieldCorrectionRequest(BaseModel):
    reviewer_name: str = Field(..., min_length=1, max_length=200)
    corrected_value: str = Field(..., min_length=1, max_length=500)


ALLOWED_REVIEW_DECISIONS = {
    "normal_review",
    "request_documents",
    "escalate_investigation",
    "data_correction",
    "policy_review",
    "closed_demo",
}
