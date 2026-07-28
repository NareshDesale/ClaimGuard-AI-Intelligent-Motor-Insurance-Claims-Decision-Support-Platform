import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "demo"


@dataclass(frozen=True)
class DemoDocument:
    document_type: str
    filename: str
    lines: list[str]
    output_format: str = "pdf"


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    title: str
    description: str
    claim: dict[str, Any]
    documents: list[DemoDocument]
    intentional_issues: list[str]


def currency(value: float) -> str:
    return f"INR {value:,.2f}"


def claim_form_lines(
    *,
    policy_number: str,
    claim_number: str,
    customer_name: str,
    vehicle_number: str,
    vehicle_make: str,
    vehicle_model: str,
    accident_date: str,
    accident_time: str,
    accident_location: str,
    policy_start_date: str,
    policy_expiry_date: str,
    claim_amount: float,
    driver_name: str,
    licence_number: str,
    police_report_number: str | None,
) -> list[str]:
    lines = [
        "CLAIMGUARD AI SYNTHETIC CLAIM FORM",
        "This is generated demo data. It is not a real claim.",
        f"Policy Number: {policy_number}",
        f"Claim Number: {claim_number}",
        f"Insured Name: {customer_name}",
        f"Customer Name: {customer_name}",
        f"Vehicle Registration Number: {vehicle_number}",
        f"Vehicle Make: {vehicle_make}",
        f"Vehicle Model: {vehicle_model}",
        f"Chassis Number: SYNCHS{claim_number[-4:]}ABCDE",
        f"Engine Number: SYNENG{claim_number[-4:]}",
        f"Accident Date: {accident_date}",
        f"Accident Time: {accident_time}",
        f"Accident Location: {accident_location}",
        f"Policy Start Date: {policy_start_date}",
        f"Policy Expiry Date: {policy_expiry_date}",
        f"Claim Amount: {currency(claim_amount)}",
        f"Driver Name: {driver_name}",
        f"Driving Licence Number: {licence_number}",
    ]

    if police_report_number:
        lines.append(
            f"Police Report Number: {police_report_number}"
        )

    return lines


def invoice_lines(
    *,
    invoice_number: str,
    invoice_date: str,
    customer_name: str,
    vehicle_number: str,
    garage_name: str,
    repair_amount: float,
) -> list[str]:
    return [
        "CLAIMGUARD AI SYNTHETIC REPAIR INVOICE",
        "This is generated demo data. It is not a real invoice.",
        f"Invoice Number: {invoice_number}",
        f"Invoice Date: {invoice_date}",
        f"Customer Name: {customer_name}",
        f"Vehicle Registration Number: {vehicle_number}",
        f"Garage Name: {garage_name}",
        f"Repair Amount: {currency(repair_amount)}",
    ]


def accident_report_lines(
    *,
    report_number: str,
    customer_name: str,
    vehicle_number: str,
    accident_date: str,
    accident_time: str,
    accident_location: str,
) -> list[str]:
    return [
        "CLAIMGUARD AI SYNTHETIC ACCIDENT REPORT",
        "This generated document contains no real police data.",
        f"Police Report Number: {report_number}",
        f"Driver Name: {customer_name}",
        f"Vehicle Registration Number: {vehicle_number}",
        f"Accident Date: {accident_date}",
        f"Accident Time: {accident_time}",
        f"Accident Location: {accident_location}",
    ]


def policy_metadata_lines(
    *,
    policy_number: str,
    customer_name: str,
    vehicle_number: str,
    start_date: str,
    expiry_date: str,
) -> list[str]:
    return [
        "CLAIMGUARD AI SYNTHETIC POLICY METADATA",
        "This generated document is not an insurance contract.",
        f"Policy Number: {policy_number}",
        f"Insured Name: {customer_name}",
        f"Customer Name: {customer_name}",
        f"Vehicle Registration Number: {vehicle_number}",
        f"Policy Start Date: {start_date}",
        f"Policy Expiry Date: {expiry_date}",
    ]


def build_scenarios() -> list[DemoScenario]:
    base = {
        "vehicle_make": "Honda",
        "vehicle_model": "City ZX",
        "driver_name": "Demo Driver",
        "licence_number": "DL142026000001",
        "garage_name": "Demo Auto Works",
    }

    scenarios: list[DemoScenario] = []

    def scenario(
        scenario_id: str,
        title: str,
        description: str,
        claim_id: str,
        policy_number: str,
        customer_name: str,
        vehicle_number: str,
        accident_date: str,
        reported_date: str,
        policy_start_date: str,
        policy_expiry_date: str,
        claim_amount: float,
        repair_amount: float,
        invoice_number: str,
        invoice_date: str,
        intentional_issues: list[str],
        include_invoice: bool = True,
        invoice_vehicle_number: str | None = None,
        duplicate_invoice: bool = False,
        claim_form_format: str = "pdf",
    ) -> DemoScenario:
        claim_number = claim_id.replace("CLM-", "CLM2026-")
        report_number = f"FIR-{claim_id[-3:]}"
        accident_time = "19:30"
        accident_location = "Synthetic MG Road, Demo City"
        vehicle_for_invoice = invoice_vehicle_number or vehicle_number

        documents = [
            DemoDocument(
                document_type="claim_form",
                filename=f"{claim_id}_claim_form.{claim_form_format}",
                output_format=claim_form_format,
                lines=claim_form_lines(
                    policy_number=policy_number,
                    claim_number=claim_number,
                    customer_name=customer_name,
                    vehicle_number=vehicle_number,
                    vehicle_make=base["vehicle_make"],
                    vehicle_model=base["vehicle_model"],
                    accident_date=accident_date,
                    accident_time=accident_time,
                    accident_location=accident_location,
                    policy_start_date=policy_start_date,
                    policy_expiry_date=policy_expiry_date,
                    claim_amount=claim_amount,
                    driver_name=base["driver_name"],
                    licence_number=base["licence_number"],
                    police_report_number=report_number,
                ),
            ),
            DemoDocument(
                document_type="policy_document",
                filename=f"{claim_id}_policy_metadata.pdf",
                lines=policy_metadata_lines(
                    policy_number=policy_number,
                    customer_name=customer_name,
                    vehicle_number=vehicle_number,
                    start_date=policy_start_date,
                    expiry_date=policy_expiry_date,
                ),
            ),
            DemoDocument(
                document_type="accident_report",
                filename=f"{claim_id}_accident_report.pdf",
                lines=accident_report_lines(
                    report_number=report_number,
                    customer_name=customer_name,
                    vehicle_number=vehicle_number,
                    accident_date=accident_date,
                    accident_time=accident_time,
                    accident_location=accident_location,
                ),
            ),
        ]

        if include_invoice:
            documents.append(
                DemoDocument(
                    document_type="repair_invoice",
                    filename=f"{claim_id}_repair_invoice.pdf",
                    lines=invoice_lines(
                        invoice_number=invoice_number,
                        invoice_date=invoice_date,
                        customer_name=customer_name,
                        vehicle_number=vehicle_for_invoice,
                        garage_name=base["garage_name"],
                        repair_amount=repair_amount,
                    ),
                )
            )

        if duplicate_invoice:
            documents.append(
                DemoDocument(
                    document_type="repair_invoice",
                    filename=f"{claim_id}_repair_invoice_duplicate.pdf",
                    lines=invoice_lines(
                        invoice_number=invoice_number,
                        invoice_date=invoice_date,
                        customer_name=customer_name,
                        vehicle_number=vehicle_for_invoice,
                        garage_name="Demo Partner Garage",
                        repair_amount=repair_amount,
                    ),
                )
            )

        return DemoScenario(
            scenario_id=scenario_id,
            title=title,
            description=description,
            claim={
                "claim_id": claim_id,
                "policy_number": policy_number,
                "customer_name": customer_name,
                "vehicle_number": vehicle_number,
                "accident_date": accident_date,
                "reported_date": reported_date,
                "claimed_amount": claim_amount,
                "status": "open",
            },
            documents=documents,
            intentional_issues=intentional_issues,
        )

    scenarios.append(
        scenario(
            scenario_id="01_complete_low_risk",
            title="Complete low-risk claim",
            description="All required documents align.",
            claim_id="CLM-DEMO-001",
            policy_number="POL-DEMO-001",
            customer_name="Demo Asha Rao",
            vehicle_number="MH12AB1234",
            accident_date="2026-08-12",
            reported_date="2026-08-14",
            policy_start_date="2026-01-01",
            policy_expiry_date="2026-12-31",
            claim_amount=42500.0,
            repair_amount=39800.0,
            invoice_number="INV-DEMO-001",
            invoice_date="2026-08-15",
            intentional_issues=[],
        )
    )
    scenarios.append(
        scenario(
            scenario_id="02_missing_document",
            title="Missing-document claim",
            description="Repair invoice is intentionally omitted.",
            claim_id="CLM-DEMO-002",
            policy_number="POL-DEMO-002",
            customer_name="Demo Nisha Mehta",
            vehicle_number="KA03CD4455",
            accident_date="2026-09-03",
            reported_date="2026-09-04",
            policy_start_date="2026-01-01",
            policy_expiry_date="2026-12-31",
            claim_amount=18500.0,
            repair_amount=18000.0,
            invoice_number="INV-DEMO-002",
            invoice_date="2026-09-05",
            include_invoice=False,
            intentional_issues=["missing repair_invoice"],
        )
    )
    scenarios.append(
        scenario(
            scenario_id="03_expired_policy",
            title="Expired-policy claim",
            description="Accident date is after policy expiry.",
            claim_id="CLM-DEMO-003",
            policy_number="POL-DEMO-003",
            customer_name="Demo Rahul Sen",
            vehicle_number="DL04EF7788",
            accident_date="2026-07-20",
            reported_date="2026-07-22",
            policy_start_date="2025-01-01",
            policy_expiry_date="2026-06-30",
            claim_amount=64000.0,
            repair_amount=61200.0,
            invoice_number="INV-DEMO-003",
            invoice_date="2026-07-23",
            intentional_issues=["accident after policy expiry"],
        )
    )
    scenarios.append(
        scenario(
            scenario_id="04_vehicle_number_mismatch",
            title="Vehicle-number mismatch",
            description="Invoice vehicle number differs from claim form.",
            claim_id="CLM-DEMO-004",
            policy_number="POL-DEMO-004",
            customer_name="Demo Kiran Das",
            vehicle_number="TN09GH1122",
            invoice_vehicle_number="TN09GH2211",
            accident_date="2026-10-02",
            reported_date="2026-10-03",
            policy_start_date="2026-01-01",
            policy_expiry_date="2026-12-31",
            claim_amount=33000.0,
            repair_amount=31000.0,
            invoice_number="INV-DEMO-004",
            invoice_date="2026-10-04",
            intentional_issues=["vehicle registration mismatch"],
        )
    )
    scenarios.append(
        scenario(
            scenario_id="05_duplicate_invoice",
            title="Duplicate invoice",
            description="Two repair invoices use the same invoice number.",
            claim_id="CLM-DEMO-005",
            policy_number="POL-DEMO-005",
            customer_name="Demo Leela Iyer",
            vehicle_number="GJ01JK9090",
            accident_date="2026-11-05",
            reported_date="2026-11-06",
            policy_start_date="2026-01-01",
            policy_expiry_date="2026-12-31",
            claim_amount=73500.0,
            repair_amount=70500.0,
            invoice_number="INV-DEMO-DUP",
            invoice_date="2026-11-07",
            duplicate_invoice=True,
            intentional_issues=["duplicate invoice number"],
        )
    )
    scenarios.append(
        scenario(
            scenario_id="06_high_risk_claim",
            title="High-risk claim",
            description="Claim amount is intentionally unusually high.",
            claim_id="CLM-DEMO-006",
            policy_number="POL-DEMO-006",
            customer_name="Demo Vikram Jain",
            vehicle_number="MH14LM5566",
            accident_date="2026-12-01",
            reported_date="2026-12-10",
            policy_start_date="2026-01-01",
            policy_expiry_date="2026-12-31",
            claim_amount=825000.0,
            repair_amount=790000.0,
            invoice_number="INV-DEMO-006",
            invoice_date="2026-12-11",
            intentional_issues=["unusually high claimed amount"],
        )
    )
    scenarios.append(
        scenario(
            scenario_id="07_ocr_image_claim",
            title="OCR image claim",
            description="Claim form is generated as an image for OCR.",
            claim_id="CLM-DEMO-007",
            policy_number="POL-DEMO-007",
            customer_name="Demo Farah Khan",
            vehicle_number="UP16NP3344",
            accident_date="2026-08-18",
            reported_date="2026-08-19",
            policy_start_date="2026-01-01",
            policy_expiry_date="2026-12-31",
            claim_amount=28500.0,
            repair_amount=27000.0,
            invoice_number="INV-DEMO-007",
            invoice_date="2026-08-20",
            claim_form_format="png",
            intentional_issues=["claim form requires OCR"],
        )
    )

    return scenarios


def render_pdf(
    path: Path,
    lines: list[str],
) -> None:
    try:
        import fitz
    except ModuleNotFoundError:
        render_image_pdf(path, lines)
        return

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    y = 64

    for line in lines:
        page.insert_text(
            (54, y),
            line,
            fontsize=11,
            fontname="helv",
        )
        y += 22

        if y > 790:
            page = document.new_page(width=595, height=842)
            y = 64

    document.save(path)
    document.close()


def build_text_image(
    lines: list[str],
) -> Any:
    from PIL import Image, ImageDraw

    width = 1200
    height = max(900, 80 + len(lines) * 44)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    y = 40

    for line in lines:
        draw.text(
            (40, y),
            line,
            fill="black",
        )
        y += 42

    return image


def render_image_pdf(
    path: Path,
    lines: list[str],
) -> None:
    image = build_text_image(lines)
    image.save(path, "PDF", resolution=150.0)


def render_image(
    path: Path,
    lines: list[str],
) -> None:
    image = build_text_image(lines)
    image.save(path)


def write_document(
    scenario_dir: Path,
    document: DemoDocument,
) -> Path:
    path = scenario_dir / document.filename

    if document.output_format == "pdf":
        render_pdf(path, document.lines)
    elif document.output_format in {"png", "jpg", "jpeg"}:
        render_image(path, document.lines)
    else:
        raise ValueError(
            f"Unsupported demo output format: {document.output_format}"
        )

    return path


def write_manifest(
    output_root: Path,
    scenarios: list[DemoScenario],
    generated_documents: dict[str, list[dict[str, str]]],
) -> Path:
    manifest = {
        "notice": (
            "Synthetic demo data only. No real people, policies, "
            "vehicles, invoices, or police reports are represented."
        ),
        "scenario_count": len(scenarios),
        "scenarios": [
            {
                "scenario_id": scenario.scenario_id,
                "title": scenario.title,
                "description": scenario.description,
                "claim": scenario.claim,
                "intentional_issues": scenario.intentional_issues,
                "documents": generated_documents[scenario.scenario_id],
            }
            for scenario in scenarios
        ],
    }
    manifest_path = output_root / "manifest.json"

    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        json.dump(
            manifest,
            manifest_file,
            indent=2,
            ensure_ascii=False,
        )

    return manifest_path


def generate_demo_data(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios()
    generated_documents: dict[str, list[dict[str, str]]] = {}

    for scenario in scenarios:
        scenario_dir = output_root / scenario.scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        generated_documents[scenario.scenario_id] = []

        for document in scenario.documents:
            document_path = write_document(
                scenario_dir=scenario_dir,
                document=document,
            )
            generated_documents[scenario.scenario_id].append(
                {
                    "document_type": document.document_type,
                    "filename": document_path.name,
                    "path": str(
                        document_path.relative_to(PROJECT_ROOT)
                    ).replace("\\", "/"),
                }
            )

    return write_manifest(
        output_root=output_root,
        scenarios=scenarios,
        generated_documents=generated_documents,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate safe synthetic ClaimGuard AI demo documents."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where demo scenarios will be written.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = generate_demo_data(
        output_root=args.output_root,
    )
    print(f"Synthetic demo data manifest: {manifest_path}")


if __name__ == "__main__":
    main()
