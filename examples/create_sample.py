"""Create a complete, fictional Otter project.

Run from the repository root:
    python examples/create_sample.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from webpentestkit.knowledge import KnowledgeService  # noqa: E402
from webpentestkit.models import (  # noqa: E402
    FindingInput,
    ProcedureStepInput,
    RetestInput,
    RetestStepInput,
    TechnicalDetailsInput,
)
from webpentestkit.services import ProjectService  # noqa: E402


SAMPLE_PROJECT_ID = "ACME-SHOP-2026"


def _prepare_destination(destination: Path, force: bool) -> None:
    if not destination.exists():
        return
    if not force:
        raise SystemExit(f"Output already exists: {destination}\nUse --force to recreate it.")

    marker = destination / "project" / "project.json"
    try:
        project = json.loads(marker.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"Refusing to remove an unrecognized directory: {destination}"
        ) from exc
    if project.get("projectId") != SAMPLE_PROJECT_ID:
        raise SystemExit(f"Refusing to remove a non-sample directory: {destination}")
    shutil.rmtree(destination)


def create_sample(destination: Path, force: bool = False) -> tuple[Path, Path]:
    destination = destination.expanduser().resolve()
    _prepare_destination(destination, force)
    destination.mkdir(parents=True)

    service = ProjectService.create_project(
        destination / "project",
        SAMPLE_PROJECT_ID,
        "ACME Shop Web Assessment",
        "ACME Corporation",
    )
    project = service.root
    knowledge = KnowledgeService.open(destination / "knowledge.db")
    service.create_target(
        "WEB-01",
        "Customer Shop",
        "https://shop.example.test",
        "Staging",
    )
    service.create_target(
        "WEB-02",
        "Operations Console",
        "https://admin.example.test",
        "Staging",
    )

    order_template = knowledge.get_template("WPK-ACCESS-001")
    order = service.create_finding(
        FindingInput(
            target_id="WEB-01",
            title="Order details IDOR",
            severity="High",
            status="Confirmed",
            category=order_template.category,
            cwe="CWE-639",
            cvss_score=8.1,
            url="https://shop.example.test/api/orders/{orderId}",
            method="GET",
            parameter="orderId",
            role="Authenticated customer",
            summary="Changing an order ID exposes another customer's order details.",
            impact="Customer order and delivery information can be disclosed.",
            remediation="Verify order ownership on the server for every object request.",
            order=10,
            template_id=order_template.id,
            template_version=order_template.version,
            technical_details=TechnicalDetailsInput(
                root_cause="The server trusts an object identifier without checking ownership.",
                request="GET /api/orders/1002 HTTP/1.1\nHost: shop.example.test\nAuthorization: [REDACTED]",
                response='HTTP/1.1 200 OK\nContent-Type: application/json\n\n{"orderId": 1002, "owner": "bob", "total": 149000}',
                analyst_notes="The response contains a stable owner field that makes cross-account disclosure easy to verify.",
            ),
        )
    )
    login_template = knowledge.get_template("WPK-AUTH-001")
    login = service.create_finding(
        FindingInput(
            target_id="WEB-02",
            title="Login rate limiting missing",
            severity="Medium",
            status="Confirmed",
            category=login_template.category,
            cwe="CWE-307",
            cvss_score=5.3,
            url="https://admin.example.test/login",
            method="POST",
            parameter="password",
            role="Unauthenticated",
            summary="Repeated login failures are accepted without throttling or lockout.",
            impact="Attackers can perform sustained password guessing against operators.",
            remediation="Add account-aware throttling, monitoring, and step-up verification.",
            order=20,
            template_id=login_template.id,
            template_version=login_template.version,
            technical_details=TechnicalDetailsInput(
                root_cause="The authentication flow has no account-aware or source-aware attempt limiter.",
                request='POST /login HTTP/1.1\nHost: admin.example.test\nContent-Type: application/json\n\n{"username":"operator","password":"[REDACTED]"}',
                response='HTTP/1.1 401 Unauthorized\nContent-Type: application/json\n\n{"error": "invalid credentials"}',
                analyst_notes="Repeated requests returned with consistent latency and no retry or lockout metadata.",
            ),
        )
    )

    with tempfile.TemporaryDirectory() as temporary:
        evidence_source = Path(temporary)
        redacted_exchange = evidence_source / "order-response.http"
        redacted_exchange.write_text(
            "GET /api/orders/1002 HTTP/1.1\n"
            "Host: shop.example.test\n"
            "Authorization: [REDACTED]\n\n"
            "HTTP/1.1 200 OK\n"
            'Content-Type: application/json\n\n{"orderId":1002,"owner":"bob"}\n',
            encoding="utf-8",
        )
        order_evidence = service.add_evidence(
            "WEB-01-001",
            redacted_exchange,
            "Cross-account order response",
            evidence_type="http-exchange",
            caption="A redacted response shows another sample user's order.",
            include_in_report=True,
        )

        raw_notes = evidence_source / "tester-notes.txt"
        raw_notes.write_text(
            "Internal testing note. Sample credentials: [REDACTED]\n",
            encoding="utf-8",
        )
        service.add_evidence(
            "WEB-01-001",
            raw_notes,
            "Tester notes",
            evidence_type="notes",
            sensitive=True,
        )

        retest_exchange = evidence_source / "rate-limit-retest.http"
        retest_exchange.write_text(
            "POST /login HTTP/1.1\nHost: admin.example.test\n\n"
            "HTTP/1.1 429 Too Many Requests\nRetry-After: 60\n",
            encoding="utf-8",
        )
        login_evidence = service.add_evidence(
            "WEB-02-001",
            retest_exchange,
            "Rate-limit retest response",
            evidence_type="http-exchange",
            caption="The remediated endpoint returns HTTP 429 after repeated failures.",
            include_in_report=True,
        )

        service.save_procedure(
            "WEB-01-001",
            preconditions="Two authenticated sample accounts, alice and bob, have different orders.",
            steps=[
                ProcedureStepInput(
                    title="Sign in as Alice",
                    action="Sign in as alice and open one of Alice's order detail pages.",
                    expected_result="Only Alice's orders are accessible.",
                ),
                ProcedureStepInput(
                    title="Change the order ID",
                    action="Replace orderId with the identifier of Bob's order and send the request.",
                    expected_result="The server rejects access to an order owned by another account.",
                    observed_result="The server returns Bob's order and delivery information.",
                    evidence_ids=(order_evidence.id,),
                ),
            ],
        )
        service.save_procedure(
            "WEB-02-001",
            preconditions="A test operator account is available and the remediation is deployed.",
            steps=[
                ProcedureStepInput(
                    title="Repeat failed logins",
                    action="Submit invalid passwords repeatedly for the same operator account.",
                    expected_result="The service throttles repeated failures.",
                    observed_result="The endpoint returns HTTP 429 with Retry-After.",
                    evidence_ids=(login_evidence.id,),
                )
            ],
        )
        service.create_retest(
            "WEB-02-001",
            RetestInput(
                tested_at="2026-07-15",
                tester="Sample Tester",
                result="Passed",
                remediation_summary="Account-aware throttling now returns HTTP 429 with Retry-After.",
                steps=(
                    RetestStepInput(
                        procedure_step_id="STEP-001",
                        title="Repeat failed logins",
                        action="Submit invalid passwords repeatedly for the same operator account.",
                        result="Passed",
                        observed_result="The endpoint returns HTTP 429 with Retry-After.",
                        evidence_ids=(login_evidence.id,),
                    ),
                ),
                notes="The remediation was verified against the sample operator account.",
            ),
        )

    issues = service.validate()
    errors = [item for item in issues if item["level"] == "ERROR"]
    if errors:
        details = "\n".join(f"- {item['code']}: {item['message']}" for item in errors)
        raise RuntimeError(f"The generated sample did not validate:\n{details}")

    service.build_reports()
    export = service.export_ppt(destination / "ppt-export")
    return project, export


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "generated" / "acme-shop",
        help="Directory that will contain project/ and ppt-export/",
    )
    parser.add_argument("--force", action="store_true", help="Recreate this sample output")
    args = parser.parse_args()

    project, export = create_sample(args.output, args.force)
    print(f"Sample project: {project}")
    print(f"PPT-ready export: {export}")
    print("Validation: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
