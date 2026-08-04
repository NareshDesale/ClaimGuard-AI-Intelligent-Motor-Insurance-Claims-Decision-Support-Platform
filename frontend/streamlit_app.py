from __future__ import annotations

import json
import os
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "CLAIMGUARD_API_URL",
    "http://localhost:8000",
).rstrip("/")

DOCUMENT_TYPES = [
    "claim_form",
    "policy_document",
    "repair_invoice",
    "accident_report",
    "identity_document",
    "vehicle_image",
    "other",
]

REVIEW_DECISIONS = [
    "normal_review",
    "request_documents",
    "escalate_investigation",
    "data_correction",
    "policy_review",
    "closed_demo",
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --cg-ink: #172033;
            --cg-muted: #64748b;
            --cg-border: #dbe4ee;
            --cg-blue: #2563eb;
            --cg-teal: #0f766e;
            --cg-amber: #b45309;
            --cg-red: #dc2626;
            --cg-surface: #ffffff;
            --cg-soft: #f7fafc;
        }

        .stApp {
            background: #ffffff;
            color: var(--cg-ink);
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--cg-border);
        }

        [data-testid="stHeader"] {
            background: #ffffff;
        }

        [data-testid="stAppViewContainer"] {
            background: #ffffff;
        }

        [data-testid="stSidebar"] * {
            color: var(--cg-ink);
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            border-radius: 8px;
            padding: 0.45rem 0.55rem;
            margin-bottom: 0.25rem;
            transition: background 120ms ease, color 120ms ease;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: rgba(37, 99, 235, 0.08);
        }

        .block-container {
            max-width: 1220px;
            padding-top: 2.4rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            color: var(--cg-ink);
            letter-spacing: 0;
        }

        .cg-hero {
            background:
                linear-gradient(135deg, rgba(37, 99, 235, 0.96), rgba(15, 118, 110, 0.94)),
                linear-gradient(90deg, #2563eb, #0f766e);
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 8px;
            padding: 1.6rem 1.7rem;
            margin-bottom: 1.4rem;
            box-shadow: 0 18px 45px rgba(37, 99, 235, 0.18);
        }

        .cg-hero h1 {
            color: #ffffff;
            font-size: 2.15rem;
            line-height: 1.1;
            margin: 0 0 0.35rem;
        }

        .cg-hero p {
            color: rgba(255, 255, 255, 0.88);
            margin: 0;
            font-size: 0.98rem;
        }

        .cg-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 999px;
            color: #ffffff;
            font-size: 0.8rem;
            font-weight: 650;
            padding: 0.28rem 0.65rem;
            margin-bottom: 0.8rem;
        }

        .cg-page-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.4rem 0 1rem;
        }

        .cg-page-title h2 {
            font-size: 1.55rem;
            margin: 0;
        }

        .cg-page-title span {
            color: var(--cg-muted);
            font-size: 0.9rem;
        }

        .cg-panel {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid var(--cg-border);
            border-radius: 8px;
            padding: 1.1rem;
            box-shadow: 0 14px 36px rgba(23, 32, 51, 0.07);
            margin-bottom: 1rem;
        }

        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid var(--cg-border);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 12px 30px rgba(23, 32, 51, 0.06);
        }

        [data-testid="stMetricLabel"] {
            color: var(--cg-muted);
            font-weight: 700;
        }

        [data-testid="stMetricValue"] {
            color: var(--cg-ink);
        }

        .stButton > button,
        .stFormSubmitButton > button {
            border-radius: 8px;
            border: 1px solid #1d4ed8;
            background: linear-gradient(135deg, #2563eb, #0f766e);
            color: #ffffff;
            font-weight: 700;
            box-shadow: 0 10px 22px rgba(37, 99, 235, 0.18);
        }

        .stButton > button:hover,
        .stFormSubmitButton > button:hover {
            border-color: #0f766e;
            color: #ffffff;
            filter: brightness(1.03);
        }

        .stTextInput input,
        .stNumberInput input,
        .stTextArea textarea,
        .stSelectbox div[data-baseweb="select"] > div {
            background-color: #ffffff;
            border-color: var(--cg-border);
            color: var(--cg-ink);
            border-radius: 8px;
        }

        [data-testid="stDataFrame"],
        [data-testid="stJson"] {
            border: 1px solid var(--cg-border);
            border-radius: 8px;
            overflow: hidden;
        }

        hr {
            border-color: var(--cg-border);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        f"""
        <div class="cg-hero">
            <div class="cg-badge">Decision support platform</div>
            <h1>ClaimGuard AI</h1>
            <p>Motor insurance claims, document intelligence, policy retrieval, risk signals, and human review in one workspace.</p>
            <p style="margin-top:0.55rem;font-size:0.84rem;">Backend: {API_BASE_URL}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_title(
    title: str,
    subtitle: str,
) -> None:
    st.markdown(
        f"""
        <div class="cg-page-title">
            <div>
                <h2>{title}</h2>
                <span>{subtitle}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def request_api(
    method: str,
    path: str,
    **kwargs: Any,
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    url = f"{API_BASE_URL}{path}"

    try:
        response = requests.request(
            method=method,
            url=url,
            timeout=120,
            **kwargs,
        )
    except requests.RequestException as error:
        return None, str(error)

    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}

    if response.status_code >= 400:
        detail = payload.get("detail", payload)
        return None, str(detail)

    return payload, None


def render_api_error(error: str | None) -> None:
    if error:
        st.error(error)


def get_claims() -> list[dict[str, Any]]:
    payload, error = request_api("GET", "/claims")
    render_api_error(error)

    if not isinstance(payload, dict):
        return []

    return list(payload.get("claims", []))


def select_claim(
    label: str = "Claim",
) -> str | None:
    claims = get_claims()
    claim_ids = [
        str(claim["claim_id"])
        for claim in claims
    ]

    if not claim_ids:
        st.info("No claims found.")
        return None

    return st.selectbox(
        label,
        claim_ids,
    )


def get_claim_documents(
    claim_id: str,
) -> list[dict[str, Any]]:
    payload, error = request_api(
        "GET",
        f"/claims/{claim_id}/documents",
    )
    render_api_error(error)

    if not isinstance(payload, dict):
        return []

    return list(payload.get("documents", []))


def metric_row(
    claims: list[dict[str, Any]],
) -> None:
    total_claims = len(claims)
    incomplete_claims = 0
    high_risk_claims = 0

    for claim in claims:
        claim_id = str(claim.get("claim_id", ""))

        if not claim_id:
            continue

        completeness, _ = request_api(
            "GET",
            f"/claims/{claim_id}/completeness",
        )

        if (
            isinstance(completeness, dict)
            and completeness.get("status") == "incomplete"
        ):
            incomplete_claims += 1

        assessment, _ = request_api(
            "GET",
            f"/claims/{claim_id}/assessment",
        )

        if (
            isinstance(assessment, dict)
            and assessment.get("fraud_risk", {}).get("risk_level")
            == "HIGH"
        ):
            high_risk_claims += 1

    pending_reviews = sum(
        1
        for claim in claims
        if claim.get("status") in {"open", "pending_review"}
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total claims", total_claims)
    col2.metric("Incomplete claims", incomplete_claims)
    col3.metric("High-risk claims", high_risk_claims)
    col4.metric("Pending reviews", pending_reviews)


def overview_page() -> None:
    page_title(
        "Overview",
        "Monitor claim volume, document readiness, risk signals, and review workload.",
    )
    claims = get_claims()
    metric_row(claims)

    if claims:
        st.markdown('<div class="cg-panel">', unsafe_allow_html=True)
        st.markdown("**Claims register**")
        st.dataframe(
            claims,
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def new_claim_page() -> None:
    page_title(
        "New Claim",
        "Create claim metadata and attach supporting documents securely.",
    )

    with st.form("new_claim_form"):
        claim_id = st.text_input("Claim ID")
        policy_number = st.text_input("Policy number")
        customer_name = st.text_input("Customer name")
        vehicle_number = st.text_input("Vehicle number")
        accident_date = st.date_input(
            "Accident date",
            value=None,
        )
        reported_date = st.date_input(
            "Reported date",
            value=None,
        )
        claimed_amount = st.number_input(
            "Claimed amount",
            min_value=0.0,
            step=1000.0,
        )
        submitted = st.form_submit_button("Create claim")

    if submitted:
        body = {
            "claim_id": claim_id,
            "policy_number": policy_number or None,
            "customer_name": customer_name or None,
            "vehicle_number": vehicle_number or None,
            "accident_date": (
                accident_date.isoformat()
                if accident_date
                else None
            ),
            "reported_date": (
                reported_date.isoformat()
                if reported_date
                else None
            ),
            "claimed_amount": claimed_amount or None,
            "status": "open",
        }
        payload, error = request_api(
            "POST",
            "/claims",
            json=body,
        )
        render_api_error(error)

        if payload:
            st.success("Claim created.")
            st.json(payload)

    st.divider()
    st.markdown("### Upload Document")
    selected_claim_id = select_claim("Upload to claim")

    if selected_claim_id:
        document_type = st.selectbox(
            "Document type",
            DOCUMENT_TYPES,
        )
        uploaded_file = st.file_uploader(
            "Document file",
            type=["pdf", "png", "jpg", "jpeg"],
        )

        if st.button("Upload document", disabled=uploaded_file is None):
            assert uploaded_file is not None
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    uploaded_file.type,
                )
            }
            data = {"document_type": document_type}
            payload, error = request_api(
                "POST",
                f"/claims/{selected_claim_id}/documents",
                files=files,
                data=data,
            )
            render_api_error(error)

            if payload:
                st.success("Document uploaded.")
                st.json(payload)


def render_json_section(
    title: str,
    payload: Any,
) -> None:
    with st.expander(title, expanded=False):
        st.json(payload)


def claim_details_page() -> None:
    page_title(
        "Claim Details",
        "Run extraction, completeness checks, validation, assessment, and audit review.",
    )
    claim_id = select_claim()

    if not claim_id:
        return

    claim, error = request_api("GET", f"/claims/{claim_id}")
    render_api_error(error)

    if claim:
        st.markdown("**Claim metadata**")
        st.json(claim)

    documents = get_claim_documents(claim_id)
    st.markdown("**Uploaded documents**")
    st.dataframe(
        documents,
        use_container_width=True,
        hide_index=True,
    )

    col1, col2, col3, col4 = st.columns(4)

    if col1.button("Completeness"):
        payload, error = request_api(
            "GET",
            f"/claims/{claim_id}/completeness",
        )
        render_api_error(error)
        if payload:
            render_json_section("Completeness result", payload)

    if col2.button("Validate"):
        payload, error = request_api(
            "POST",
            f"/claims/{claim_id}/validate",
        )
        render_api_error(error)
        if payload:
            render_json_section("Validation result", payload)

    if col3.button("Assessment"):
        payload, error = request_api(
            "POST",
            f"/claims/{claim_id}/assessment",
            json={"manual_features": {}},
        )
        render_api_error(error)
        if payload:
            render_json_section("Assessment result", payload)

    if col4.button("Audit log"):
        payload, error = request_api(
            "GET",
            f"/claims/{claim_id}/audit-log",
        )
        render_api_error(error)
        if payload:
            render_json_section("Audit log", payload)

    if documents:
        st.divider()
        document_ids = [
            str(document["document_id"])
            for document in documents
        ]
        document_id = st.selectbox(
            "Document",
            document_ids,
        )
        action = st.segmented_control(
            "Document action",
            ["Extract text", "Extract fields", "View fields"],
        )

        if st.button("Run document action"):
            if action == "Extract text":
                payload, error = request_api(
                    "POST",
                    f"/claims/{claim_id}/documents/{document_id}/extract",
                )
            elif action == "Extract fields":
                payload, error = request_api(
                    "POST",
                    f"/claims/{claim_id}/documents/{document_id}/fields",
                )
            else:
                payload, error = request_api(
                    "GET",
                    f"/claims/{claim_id}/documents/{document_id}/fields",
                )

            render_api_error(error)
            if payload:
                render_json_section("Document result", payload)


def human_review_page() -> None:
    page_title(
        "Human Review",
        "Record reviewer decisions and correct extracted fields with audit history.",
    )
    claim_id = select_claim()

    if not claim_id:
        return

    with st.form("review_decision_form"):
        reviewer_name = st.text_input("Reviewer")
        decision = st.selectbox("Decision", REVIEW_DECISIONS)
        comment = st.text_area("Comment")
        submitted = st.form_submit_button("Submit review")

    if submitted:
        payload, error = request_api(
            "POST",
            f"/claims/{claim_id}/review",
            json={
                "reviewer_name": reviewer_name,
                "decision": decision,
                "comment": comment or None,
            },
        )
        render_api_error(error)
        if payload:
            st.success("Review recorded.")
            st.json(payload)

    reviews, error = request_api(
        "GET",
        f"/claims/{claim_id}/reviews",
    )
    render_api_error(error)

    if isinstance(reviews, dict):
        st.dataframe(
            reviews.get("reviews", []),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    documents = get_claim_documents(claim_id)

    if not documents:
        return

    document_id = st.selectbox(
        "Correction document",
        [
            str(document["document_id"])
            for document in documents
        ],
    )
    field_name = st.text_input("Field name")
    corrected_value = st.text_input("Corrected value")
    correction_reviewer = st.text_input(
        "Correction reviewer",
        key="correction_reviewer",
    )

    if st.button("Save correction"):
        payload, error = request_api(
            "PATCH",
            (
                f"/claims/{claim_id}/documents/{document_id}"
                f"/fields/{field_name}"
            ),
            json={
                "reviewer_name": correction_reviewer,
                "corrected_value": corrected_value,
            },
        )
        render_api_error(error)
        if payload:
            st.success("Correction saved.")
            st.json(payload)


def policy_assistant_page() -> None:
    page_title(
        "Policy Assistant",
        "Ask policy questions with source/page citations or retrieve supporting passages.",
    )
    claims = get_claims()
    claim_options = [""] + [
        str(claim["claim_id"])
        for claim in claims
    ]
    claim_id = st.selectbox(
        "Audit claim",
        claim_options,
    )
    question = st.text_area("Question")
    top_k = st.slider("Sources", min_value=1, max_value=8, value=4)
    threshold = st.slider(
        "Similarity threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.25,
        step=0.05,
    )
    mode = st.segmented_control(
        "Mode",
        ["Ask", "Retrieve"],
        default="Ask",
    )

    if st.button("Submit policy query"):
        body = {
            "question": question,
            "top_k": top_k,
            "min_similarity_score": threshold,
            "claim_id": claim_id or None,
        }
        endpoint = "/rag/ask" if mode == "Ask" else "/rag/retrieve"
        payload, error = request_api(
            "POST",
            endpoint,
            json=body,
        )
        render_api_error(error)

        if payload:
            if isinstance(payload, dict) and payload.get("answer"):
                st.markdown(payload["answer"])

            sources = payload.get("sources", []) if isinstance(
                payload,
                dict,
            ) else []

            if sources:
                st.dataframe(
                    sources,
                    use_container_width=True,
                    hide_index=True,
                )

            render_json_section("Policy response", payload)


def claim_ai_assistant_page() -> None:
    page_title(
        "Claim AI Assistant",
        "Ask claim-aware questions using metadata, extracted fields, validation, assessment, and optional policy RAG context.",
    )
    claim_id = select_claim("Assistant claim")

    if not claim_id:
        return

    question = st.text_area(
        "Question",
        value=(
            "What should the reviewer check next for this claim?"
        ),
        height=110,
    )

    col1, col2 = st.columns(2)
    use_llm = col1.toggle(
        "Use Gemini LLM",
        value=False,
        help=(
            "When off, ClaimGuard returns a deterministic reviewer "
            "briefing without calling Gemini."
        ),
    )
    include_policy_context = col2.toggle(
        "Include policy RAG context",
        value=False,
        help=(
            "Retrieve policy sources related to the question and include "
            "them in the assistant context."
        ),
    )

    top_k = 4
    threshold = 0.25

    if include_policy_context:
        rcol1, rcol2 = st.columns(2)
        top_k = rcol1.slider(
            "Policy sources",
            min_value=1,
            max_value=8,
            value=4,
        )
        threshold = rcol2.slider(
            "Similarity threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.25,
            step=0.05,
        )

    if st.button("Ask claim assistant"):
        payload, error = request_api(
            "POST",
            f"/claims/{claim_id}/assistant",
            json={
                "question": question,
                "use_llm": use_llm,
                "include_policy_context": include_policy_context,
                "top_k": top_k,
                "min_similarity_score": threshold,
            },
        )
        render_api_error(error)

        if isinstance(payload, dict):
            st.markdown("### Assistant Answer")
            st.markdown(payload.get("answer", "No answer returned."))

            summary = payload.get("context_summary", {})
            if summary:
                cols = st.columns(4)
                cols[0].metric(
                    "Documents",
                    summary.get("document_count", 0),
                )
                cols[1].metric(
                    "Fields",
                    summary.get("extracted_field_count", 0),
                )
                cols[2].metric(
                    "Failed rules",
                    summary.get("failed_validation_rule_count", 0),
                )
                cols[3].metric(
                    "Policy sources",
                    summary.get("policy_source_count", 0),
                )

            if payload.get("warnings"):
                st.warning("\n".join(payload["warnings"]))

            render_json_section("Assistant response", payload)


def main() -> None:
    st.set_page_config(
        page_title="ClaimGuard AI",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    render_header()

    page = st.sidebar.radio(
        "Page",
        [
            "Overview",
            "New Claim",
            "Claim Details",
            "Claim AI Assistant",
            "Human Review",
            "Policy Assistant",
        ],
    )

    if page == "Overview":
        overview_page()
    elif page == "New Claim":
        new_claim_page()
    elif page == "Claim Details":
        claim_details_page()
    elif page == "Claim AI Assistant":
        claim_ai_assistant_page()
    elif page == "Human Review":
        human_review_page()
    else:
        policy_assistant_page()


if __name__ == "__main__":
    main()
