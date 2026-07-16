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
    TechnicalDetailsInput,
    VulnerabilityTemplateInput,
)
from webpentestkit.services import ProjectService  # noqa: E402


SAMPLE_PROJECT_ID = "ACME-SHOP-2026"

EXTRA_FINDINGS = (
    {
        "target_id": "WEB-01",
        "title": "Stored XSS in product reviews",
        "severity": "High",
        "status": "Confirmed",
        "category": "Client-Side",
        "cwe": "CWE-79",
        "url": "https://shop.example.test/api/reviews",
        "method": "POST",
        "parameter": "comment",
        "role": "Authenticated customer",
        "summary": "Review comments are rendered without context-aware output encoding.",
        "impact": "An attacker can execute script in another customer's browser.",
        "remediation": "Encode untrusted output and sanitize the supported review markup.",
        "cvss_score": 8.0,
    },
    {
        "target_id": "WEB-01",
        "title": "Coupon reuse bypasses redemption limit",
        "severity": "Medium",
        "status": "Confirmed",
        "category": "Business Logic",
        "cwe": "CWE-840",
        "url": "https://shop.example.test/api/checkout/coupon",
        "method": "POST",
        "parameter": "couponCode",
        "role": "Authenticated customer",
        "summary": "Concurrent checkout requests can redeem a single-use coupon repeatedly.",
        "impact": "A customer can obtain discounts beyond the configured campaign limit.",
        "remediation": "Enforce redemption atomically in the authoritative order transaction.",
        "cvss_score": 6.5,
    },
    {
        "target_id": "WEB-01",
        "title": "Content Security Policy is missing",
        "severity": "Low",
        "status": "Accepted",
        "category": "Security Misconfiguration",
        "cwe": "CWE-693",
        "url": "https://shop.example.test/",
        "method": "GET",
        "parameter": "",
        "role": "Public user",
        "summary": "HTML responses do not define a Content-Security-Policy header.",
        "impact": "A future injection flaw would have fewer browser-side restrictions.",
        "remediation": "Deploy a restrictive nonce-based Content Security Policy.",
        "cvss_score": 3.1,
    },
    {
        "target_id": "WEB-01",
        "title": "Checkout return URL open redirect",
        "severity": "Low",
        "status": "FalsePositive",
        "category": "Input Validation",
        "cwe": "CWE-601",
        "url": "https://shop.example.test/checkout/complete",
        "method": "GET",
        "parameter": "returnUrl",
        "role": "Public user",
        "summary": "Initial testing suggested an external redirect through returnUrl.",
        "impact": "No exploitable redirect remained after the allow-list behavior was verified.",
        "remediation": "Retain the existing origin allow-list and regression tests.",
        "cvss_score": 0.0,
    },
    {
        "target_id": "WEB-01",
        "title": "Password change does not revoke sessions",
        "severity": "Medium",
        "status": "Resolved",
        "category": "Session Management",
        "cwe": "CWE-613",
        "url": "https://shop.example.test/api/account/password",
        "method": "PUT",
        "parameter": "newPassword",
        "role": "Authenticated customer",
        "summary": "Existing sessions remained valid after an account password change.",
        "impact": "A stolen session could remain usable after the account owner responds.",
        "remediation": "Revoke other sessions and rotate refresh tokens after credential changes.",
        "cvss_score": 6.4,
    },
    {
        "target_id": "WEB-02",
        "title": "SQL injection in audit search",
        "severity": "Critical",
        "status": "Confirmed",
        "category": "Injection",
        "cwe": "CWE-89",
        "url": "https://admin.example.test/api/audit/search",
        "method": "GET",
        "parameter": "query",
        "role": "Support operator",
        "summary": "The audit search expression is concatenated into a database query.",
        "impact": "An operator account can read or modify sensitive administrative data.",
        "remediation": "Use parameterized queries and a read-only database identity.",
        "cvss_score": 9.6,
    },
    {
        "target_id": "WEB-02",
        "title": "Weak operator password policy",
        "severity": "Medium",
        "status": "Confirmed",
        "category": "Authentication",
        "cwe": "CWE-521",
        "url": "https://admin.example.test/account/password",
        "method": "POST",
        "parameter": "password",
        "role": "Operator",
        "summary": "Short and commonly used passwords are accepted for operator accounts.",
        "impact": "Password guessing and credential stuffing are more likely to succeed.",
        "remediation": "Require long passwords and screen them against breached-password data.",
        "cvss_score": 5.9,
    },
    {
        "target_id": "WEB-02",
        "title": "Verbose stack trace disclosure",
        "severity": "Low",
        "status": "Confirmed",
        "category": "Information Disclosure",
        "cwe": "CWE-209",
        "url": "https://admin.example.test/api/reports/export",
        "method": "POST",
        "parameter": "format",
        "role": "Operator",
        "summary": "Invalid export formats return framework stack traces and local paths.",
        "impact": "Implementation details can help an attacker refine later attacks.",
        "remediation": "Return generic errors and retain diagnostic details only in protected logs.",
        "cvss_score": 3.7,
    },
    {
        "target_id": "WEB-02",
        "title": "Access tokens written to audit log",
        "severity": "Medium",
        "status": "Resolved",
        "category": "Information Disclosure",
        "cwe": "CWE-532",
        "url": "https://admin.example.test/api/audit",
        "method": "GET",
        "parameter": "",
        "role": "Security administrator",
        "summary": "Bearer tokens were stored in request audit records.",
        "impact": "Log readers could reuse an unexpired operator token.",
        "remediation": "Redact authorization material before log serialization.",
        "cvss_score": 6.8,
    },
    {
        "target_id": "WEB-03",
        "title": "Server-side request forgery in webhook tester",
        "severity": "Critical",
        "status": "Confirmed",
        "category": "Input Validation",
        "cwe": "CWE-918",
        "url": "https://api.example.test/v1/webhooks/test",
        "method": "POST",
        "parameter": "callbackUrl",
        "role": "Integration administrator",
        "summary": "The webhook tester requests arbitrary URLs from the internal network.",
        "impact": "An attacker can reach metadata services and internal administration endpoints.",
        "remediation": "Resolve and allow-list destinations while blocking private and link-local ranges.",
        "cvss_score": 9.1,
    },
    {
        "target_id": "WEB-03",
        "title": "Credentialed CORS origin reflection",
        "severity": "High",
        "status": "Confirmed",
        "category": "Security Misconfiguration",
        "cwe": "CWE-942",
        "url": "https://api.example.test/v1/profile",
        "method": "GET",
        "parameter": "Origin",
        "role": "Authenticated API user",
        "summary": "Arbitrary Origin values are reflected with credentialed CORS enabled.",
        "impact": "A malicious site can read authenticated API responses from a victim browser.",
        "remediation": "Allow only explicitly trusted origins and disable credentials otherwise.",
        "cvss_score": 8.1,
    },
    {
        "target_id": "WEB-03",
        "title": "JWT signature verification bypass",
        "severity": "Critical",
        "status": "Resolved",
        "category": "Authentication",
        "cwe": "CWE-347",
        "url": "https://api.example.test/v1/token/verify",
        "method": "POST",
        "parameter": "token",
        "role": "API client",
        "summary": "A legacy verifier accepted tokens using an attacker-controlled algorithm.",
        "impact": "An attacker could forge privileged API identities.",
        "remediation": "Pin the expected algorithm and key for each trusted token issuer.",
        "cvss_score": 9.8,
    },
    {
        "target_id": "WEB-03",
        "title": "GraphQL introspection enabled in production",
        "severity": "Info",
        "status": "Accepted",
        "category": "Information Disclosure",
        "cwe": "CWE-200",
        "url": "https://api.example.test/graphql",
        "method": "POST",
        "parameter": "query",
        "role": "Public API client",
        "summary": "The production GraphQL endpoint exposes its complete schema.",
        "impact": "Attackers can enumerate operations and types more efficiently.",
        "remediation": "Restrict introspection where it is not operationally required.",
        "cvss_score": 0.0,
    },
    {
        "target_id": "WEB-03",
        "title": "API key rate limit can be bypassed",
        "severity": "Medium",
        "status": "Draft",
        "category": "Business Logic",
        "cwe": "CWE-770",
        "url": "https://api.example.test/v1/search",
        "method": "GET",
        "parameter": "X-Forwarded-For",
        "role": "API client",
        "summary": "Preliminary testing indicates the client IP rate limit trusts a request header.",
        "impact": "A client may exceed search quotas and cause excess resource consumption.",
        "remediation": "Use a trusted proxy-derived client identity and enforce API-key quotas.",
        "cvss_score": 5.3,
    },
    {
        "target_id": "WEB-04",
        "title": "Unrestricted document upload",
        "severity": "High",
        "status": "Confirmed",
        "category": "Input Validation",
        "cwe": "CWE-434",
        "url": "https://partner.example.test/api/documents",
        "method": "POST",
        "parameter": "file",
        "role": "Partner user",
        "summary": "The document endpoint accepts active content with a trusted public URL.",
        "impact": "Uploaded content can be used for phishing or stored client-side attacks.",
        "remediation": "Allow-list formats, inspect content, and serve files from an isolated origin.",
        "cvss_score": 8.0,
    },
    {
        "target_id": "WEB-04",
        "title": "Partner user can access admin endpoint",
        "severity": "High",
        "status": "Confirmed",
        "category": "Authorization",
        "cwe": "CWE-862",
        "url": "https://partner.example.test/api/admin/tenants",
        "method": "GET",
        "parameter": "",
        "role": "Partner user",
        "summary": "A partner role can invoke an endpoint intended for platform administrators.",
        "impact": "Tenant metadata and administrative operations are exposed across roles.",
        "remediation": "Enforce server-side authorization policies for every administrative route.",
        "cvss_score": 8.7,
    },
    {
        "target_id": "WEB-04",
        "title": "HTTP Strict Transport Security missing",
        "severity": "Low",
        "status": "Confirmed",
        "category": "Security Misconfiguration",
        "cwe": "CWE-319",
        "url": "https://partner.example.test/",
        "method": "GET",
        "parameter": "",
        "role": "Public user",
        "summary": "The partner portal does not advertise an HSTS policy.",
        "impact": "A first connection may be more exposed to protocol downgrade attacks.",
        "remediation": "Enable HSTS after confirming complete HTTPS coverage.",
        "cvss_score": 3.1,
    },
)


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
    service.update_report_config(
        report_title="ACME Shop Web Security Assessment",
        customer_name="ACME Corporation",
        classification="Confidential",
        assessment_from="2026-07-01",
        assessment_to="2026-07-15",
        language="en-US",
    )
    project = service.root
    knowledge = KnowledgeService.open(destination / "knowledge.db")
    demo_template = knowledge.add_template_version(
        VulnerabilityTemplateInput(
            id="WPK-DEMO-API-001",
            name="API mass assignment sample",
            english_name="API mass assignment sample",
            title="API mass assignment permits role modification",
            category="Input Validation",
            default_severity="High",
            summary="Unexpected JSON properties are accepted by the sample profile API.",
            impact="A customer can assign a privileged role to their own account.",
            remediation="Bind only explicitly allowed request properties and reject unknown fields.",
            cwes=("CWE-915",),
            tags=("API", "Mass Assignment", "Sample"),
            status="Approved",
            reviewed_by="Sample Security Reviewer",
            reviewed_at="2026-07-16",
        )
    )
    demo_template = knowledge.update_template(
        demo_template.id,
        remediation=(
            "Bind only explicitly allowed request properties, reject unknown fields, "
            "and verify authorization for privileged attributes."
        ),
    )
    archived_template = knowledge.add_template_version(
        VulnerabilityTemplateInput(
            id="WPK-DEMO-ARCHIVED-001",
            name="Archived TLS configuration sample",
            english_name="Archived TLS configuration sample",
            title="Legacy TLS protocol is enabled",
            category="Cryptography",
            default_severity="Low",
            summary="A legacy TLS configuration example retained for UI demonstration.",
            impact="Legacy clients may negotiate an outdated transport protocol.",
            remediation="Disable legacy protocol versions and weak cipher suites.",
            cwes=("CWE-326",),
            tags=("TLS", "Archived", "Sample"),
            status="Reviewed",
        )
    )
    knowledge.archive_template(archived_template.id)
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
    service.create_target(
        "WEB-03",
        "Public API Gateway",
        "https://api.example.test",
        "Production-like",
    )
    service.create_target(
        "WEB-04",
        "Partner Portal",
        "https://partner.example.test",
        "Staging",
    )

    profile = knowledge.create_finding_from_template(
        service,
        demo_template.id,
        "WEB-02",
        title="Profile API mass assignment",
        status="Confirmed",
        url="https://admin.example.test/api/profile",
        method="PATCH",
        parameter="role",
        role="Authenticated operator",
        tester="Sample Tester",
    )
    service.update_finding(
        profile.id,
        technical_root_cause=(
            "The profile endpoint binds untrusted JSON properties directly "
            "to an authorization-sensitive account model."
        ),
        technical_analysis=(
            "A fictional operator request demonstrated that an unexpected "
            "role property was accepted by the sample API."
        ),
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
                analysis="The response contains a stable owner field that makes cross-account disclosure easy to verify.",
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
                analysis="Repeated requests returned with consistent latency and no retry or lockout metadata.",
            ),
        )
    )

    extra_findings = []
    for index, values in enumerate(EXTRA_FINDINGS, 1):
        extra_findings.append(
            service.create_finding(
                FindingInput(
                    **values,
                    order=100 + index * 10,
                    tester="Sample Tester",
                    technical_details=TechnicalDetailsInput(
                        root_cause=(
                            "The sample implementation does not enforce the required "
                            "security control at the authoritative server boundary."
                        ),
                        analysis=(
                            "The issue was reproduced with fictional accounts and sanitized "
                            "requests in the generated demonstration environment."
                        ),
                    ),
                )
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
            order.id,
            redacted_exchange,
            "Cross-account order response",
            evidence_type="http-exchange",
            caption="A redacted response shows another sample user's order.",
            classification="report-ready",
            use_in_finding=True,
        )
        service.set_scope_evidence(
            order.id, "technical", "", (order_evidence.id,)
        )

        raw_notes = evidence_source / "tester-notes.txt"
        raw_notes.write_text(
            "Internal testing note. Sample credentials: [REDACTED]\n",
            encoding="utf-8",
        )
        service.add_evidence(
            order.id,
            raw_notes,
            "Tester notes",
            evidence_type="notes",
            classification="sensitive",
        )

        retest_exchange = evidence_source / "rate-limit-retest.http"
        retest_exchange.write_text(
            "POST /login HTTP/1.1\nHost: admin.example.test\n\n"
            "HTTP/1.1 429 Too Many Requests\nRetry-After: 60\n",
            encoding="utf-8",
        )
        login_evidence = service.add_evidence(
            login.id,
            retest_exchange,
            "Rate-limit retest response",
            evidence_type="http-exchange",
            caption="The remediated endpoint returns HTTP 429 after repeated failures.",
            classification="report-ready",
        )
        service.set_scope_evidence(
            login.id, "technical", "", (login_evidence.id,)
        )

        service.save_procedure(
            order.id,
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
            login.id,
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
            login.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Sample Tester",
                result="Passed",
                remediation_summary="Account-aware throttling now returns HTTP 429 with Retry-After.",
                verification_details="Repeated failed logins return HTTP 429 with Retry-After.",
                evidence_ids=(login_evidence.id,),
                notes="The remediation was verified against the sample operator account.",
            ),
        )

        for index, finding in enumerate(extra_findings, 1):
            if not (
                finding.severity in {"Critical", "High"}
                or finding.status == "Resolved"
                or index % 4 == 0
            ):
                continue
            exchange = evidence_source / f"{finding.id.lower()}-sample.http"
            exchange.write_text(
                f"{finding.affected.method or 'GET'} {finding.affected.url} HTTP/1.1\n"
                "Host: example.test\n"
                "Authorization: [REDACTED]\n\n"
                "HTTP/1.1 200 OK\n"
                "Content-Type: application/json\n\n"
                f'{{"sampleFinding":"{finding.id}","sanitized":true}}\n',
                encoding="utf-8",
            )
            evidence = service.add_evidence(
                finding.id,
                exchange,
                f"Sanitized reproduction for {finding.id}",
                evidence_type="http-exchange",
                caption="A fictional, redacted exchange demonstrating the sample issue.",
                classification="report-ready",
                use_in_finding=True,
            )
            service.set_scope_evidence(
                finding.id,
                "technical",
                "",
                (evidence.id,),
            )
            if finding.severity == "Critical" or index % 3 == 0:
                service.save_procedure(
                    finding.id,
                    preconditions=(
                        "Use the fictional sample account and only the generated example.test host."
                    ),
                    steps=[
                        ProcedureStepInput(
                            title="Send the baseline request",
                            action="Send the normal request and record the expected authorization boundary.",
                            expected_result="The server enforces the documented security control.",
                        ),
                        ProcedureStepInput(
                            title="Modify the security-relevant input",
                            action=f"Change {finding.affected.parameter or 'the request context'} and resend the request.",
                            expected_result="The modified request is rejected or safely handled.",
                            observed_result="The generated sample response demonstrates the documented issue.",
                            evidence_ids=(evidence.id,),
                        ),
                    ],
                )
            if finding.status == "Resolved":
                service.create_retest(
                    finding.id,
                    RetestInput(
                        tested_at="2026-07-16",
                        tester="Sample Retest Analyst",
                        result="Passed",
                        remediation_summary="The fictional remediation was applied in the sample environment.",
                        verification_details="The original reproduction no longer succeeds after remediation.",
                        evidence_ids=(evidence.id,),
                        notes="Generated retest data for UI and report demonstration.",
                    ),
                )

    issues = service.validate()
    errors = [item for item in issues if item["level"] == "ERROR"]
    if errors:
        details = "\n".join(f"- {item['code']}: {item['message']}" for item in errors)
        raise RuntimeError(f"The generated sample did not validate:\n{details}")

    service.build_reports()
    export = service.export_ppt(destination / "ppt-export")
    (destination / "OPEN_SAMPLE.md").write_text(
        """# Otter sample workspace

From the repository root, open this sample with its dedicated knowledge database:

```powershell
python examples/open_sample_gui.py
```

Things to review:

1. Open **Finding library** and search for `WPK-DEMO-API-001`.
2. Double-click it to review **Edit**, **Add finding from this template**, **Archive**, and **Delete**.
3. In the status filter, choose **Archived** to find `WPK-DEMO-ARCHIVED-001` and test **Restore**.
4. Open **Finding** and review `Profile API mass assignment`, which was copied from the active demo template.
5. Review the dashboard and filters across 4 targets and 20 findings with varied severity and workflow status.
6. The project also contains 14 evidence records, 7 procedures, 4 retests, reports, and PPT-ready export data.

This is fictional data. Recreate it at any time with:

```powershell
python examples/create_sample.py --force
```
""",
        encoding="utf-8",
    )
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
