"""Create the canonical W-library project used for manual output testing.

The generator copies Otter's current vulnerability knowledge database, creates
six findings from W-series records, and renders one-or-more procedure screenshots
plus one final-result screenshot for every finding. It intentionally stops before
template registration, slide mapping, draft planning, and PowerPoint generation.

Run from the repository root:

    .\\.venv\\Scripts\\python.exe .\\examples\\create_presentation_e2e_sample.py --force
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from examples.manual_w_sample_data import (  # noqa: E402
    EVIDENCE_COUNT,
    FINDINGS,
    PROCEDURE_EVIDENCE_COUNT,
    RESULT_EVIDENCE_COUNT,
    iter_step_evidence_specs,
)
from examples.render_sample_evidence import render as render_evidence  # noqa: E402
from webpentestkit.knowledge import (  # noqa: E402
    KnowledgeService,
    default_knowledge_database_path,
)
from webpentestkit.models import (  # noqa: E402
    ProcedureStepInput,
    RetestInput,
    TechnicalDetailsInput,
)
from webpentestkit.reporting_core.validation import validate_project  # noqa: E402
from webpentestkit.services import ProjectService  # noqa: E402


PROJECT_ID = "NORTHSTAR-W-LIBRARY-E2E-2026"
DEFAULT_DESTINATION = REPOSITORY_ROOT / "examples" / "generated" / "w-library-e2e"


def _prepare_destination(destination: Path, force: bool) -> None:
    if not destination.exists():
        return
    marker = destination / "project" / "project.json"
    if not force:
        raise SystemExit(f"Destination already exists; use --force: {destination}")
    try:
        project = json.loads(marker.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Refusing to remove an unrecognized directory: {destination}") from exc
    if project.get("projectId") != PROJECT_ID:
        raise SystemExit(f"Refusing to remove a non-sample directory: {destination}")
    shutil.rmtree(destination)


def _copy_knowledge_database(source: Path, destination: Path) -> KnowledgeService:
    if not source.is_file():
        raise SystemExit(f"Knowledge database not found: {source}")
    shutil.copy2(source, destination)
    knowledge = KnowledgeService.open(destination, seed_path=None)
    w_templates = [
        item for item in knowledge.search_templates() if re.fullmatch(r"W-\d+", item.id)
    ]
    if len(w_templates) < 28:
        raise SystemExit(
            f"Knowledge database has only {len(w_templates)} W-series templates; expected at least 28"
        )
    return knowledge


def _add_evidence(
    service: ProjectService,
    finding_id: str,
    source_root: Path,
    spec: dict,
    *,
    use_in_finding: bool = False,
):
    source = source_root / f"{spec['slug']}.png"
    if not source.is_file():
        raise SystemExit(f"Missing rendered evidence: {source}")
    caption = str(spec.get("caption") or spec.get("observed") or spec["title"])
    return service.add_evidence(
        finding_id,
        source,
        str(spec["title"]),
        evidence_type="screenshot",
        caption=caption,
        classification="report-ready",
        use_in_finding=use_in_finding,
        finding_link_caption=caption,
    )


def create_project(
    destination: Path,
    knowledge_source: Path,
    evidence_root: Path,
) -> tuple[ProjectService, dict[str, str]]:
    knowledge = _copy_knowledge_database(knowledge_source, destination / "knowledge.db")
    service = ProjectService.create_project(
        destination / "project",
        PROJECT_ID,
        "Northstar 커머스 W 라이브러리 다양성 E2E",
        "Northstar Commerce",
    )
    service.update_report_config(
        report_title="Northstar 커머스 웹 취약점 진단 결과보고서",
        customer_name="Northstar Commerce",
        classification="Confidential",
        assessment_from="2026-07-01",
        assessment_to="2026-07-16",
        language="ko-KR",
        include_informational=True,
        include_passed_retest=True,
    )
    service.create_target(
        "WEB-01", "Customer Portal", "https://portal.northstar.test", "Staging"
    )
    service.create_target(
        "WEB-02", "Operations Admin", "https://admin.northstar.test", "Staging"
    )
    service.create_target(
        "WEB-03", "Public Payment API", "https://api.northstar.test", "Production-like"
    )

    finding_ids: dict[str, str] = {}
    for order, definition in enumerate(FINDINGS, start=1):
        template = knowledge.get_template(definition["library_id"])
        if template.name != definition["library_name"]:
            raise SystemExit(
                f"Knowledge template name mismatch for {template.id}: "
                f"{template.name!r} != {definition['library_name']!r}"
            )
        finding = knowledge.create_finding_from_template(
            service,
            template.id,
            definition["target_id"],
            title=definition["title"],
            severity=definition["severity"],
            status=definition["status"],
            category=definition.get("category", template.category),
            cvss_vector=definition["cvss_vector"],
            url=definition["url"],
            method=definition["method"],
            parameter=definition["parameter"],
            role=definition["role"],
            tester=definition["tester"],
            discovered_at=definition["discovered_at"],
            summary=definition["summary"],
            impact=definition["impact"],
            remediation=definition["remediation"],
            order=order * 10,
            technical_details=TechnicalDetailsInput(
                root_cause=definition["root_cause"],
                analysis=definition["analysis"],
            ),
        )
        finding_ids[definition["key"]] = finding.id

        step_inputs: list[ProcedureStepInput] = []
        for step in definition["steps"]:
            evidence_ids = tuple(
                _add_evidence(service, finding.id, evidence_root, spec).id
                for spec in iter_step_evidence_specs(step)
            )
            step_inputs.append(
                ProcedureStepInput(
                    title=step["title"],
                    action=step["action"],
                    expected_result=step["expected"],
                    observed_result=step["observed"],
                    evidence_ids=evidence_ids,
                )
            )
        service.save_procedure(
            finding.id,
            preconditions=definition["preconditions"],
            steps=step_inputs,
        )

        _add_evidence(
            service,
            finding.id,
            evidence_root,
            definition["result"],
            use_in_finding=True,
        )

        if definition.get("retest"):
            retest = definition["retest"]
            evidence = _add_evidence(service, finding.id, evidence_root, retest)
            service.create_retest(
                finding.id,
                RetestInput(
                    tested_at=retest["tested_at"],
                    tester=retest["tester"],
                    result=retest["result"],
                    remediation_summary=retest["remediation_summary"],
                    verification_details=retest["verification_details"],
                    evidence_ids=(evidence.id,),
                    notes=retest["notes"],
                ),
            )

    return service, finding_ids


def _validate_evidence_contract(
    service: ProjectService,
    finding_ids: dict[str, str],
) -> dict[str, dict[str, int]]:
    contract: dict[str, dict[str, int]] = {}
    for definition in FINDINGS:
        finding_id = finding_ids[definition["key"]]
        procedure = service.get_procedure(finding_id)
        expected_step_evidence = [
            sum(1 for _ in iter_step_evidence_specs(step))
            for step in definition["steps"]
        ]
        actual_step_evidence = [len(step.evidence_ids) for step in procedure.steps]
        if actual_step_evidence != expected_step_evidence:
            raise SystemExit(
                f"Procedure evidence contract failed for {definition['library_id']}: "
                f"{actual_step_evidence} != {expected_step_evidence}"
            )
        usages = service.list_evidence_usages(finding_id)
        result_evidence = [
            usage.evidence_id
            for usage in usages.values()
            if usage.finding_presentation
        ]
        if len(result_evidence) != 1:
            raise SystemExit(
                f"Result evidence contract failed for {definition['library_id']}: "
                f"{result_evidence}"
            )
        contract[definition["library_id"]] = {
            "procedureSteps": len(procedure.steps),
            "procedureImages": sum(actual_step_evidence),
            "stepsWithoutEvidence": actual_step_evidence.count(0),
            "stepsWithMultipleEvidence": sum(
                1 for count in actual_step_evidence if count > 1
            ),
            "resultImages": len(result_evidence),
            "totalEvidence": len(service.list_evidence(finding_id)),
        }
        contract[definition["library_id"]]["stepEvidenceCounts"] = actual_step_evidence
    all_step_counts = [
        count
        for finding in contract.values()
        for count in finding["stepEvidenceCounts"]
    ]
    if any(count < 1 for count in all_step_counts):
        raise SystemExit(
            "Every procedure must include at least one evidence image, got: "
            f"{sorted(set(all_step_counts))}"
        )
    if not {1, 2}.issubset(set(all_step_counts)):
        raise SystemExit(
            "Expected both one- and two-image procedure cases, got: "
            f"{sorted(set(all_step_counts))}"
        )
    return contract


def _write_manual_guide(
    destination: Path,
    summary: dict,
) -> None:
    library_ids = ", ".join(f"`{item['library_id']}`" for item in FINDINGS)
    matrix_lines = []
    for definition in FINDINGS:
        contract = summary["evidenceContract"][definition["library_id"]]
        matrix_lines.append(
            "| {id} | {name} | {status} | {steps} | `{evidence}` | {result} | {retest} |".format(
                id=definition["library_id"],
                name=definition["library_name"],
                status=definition["status"],
                steps=contract["procedureSteps"],
                evidence=" / ".join(
                    str(value) for value in contract["stepEvidenceCounts"]
                ),
                result=contract["resultImages"],
                retest="있음" if definition.get("retest") else "-",
            )
        )
    guide = f"""# W 라이브러리 수동 테스트 가이드

이 폴더 하나로 취약점 라이브러리 연결부터 절차·증적 편집, 대상 범위 선택,
사용자 템플릿의 PPT 생성까지 수동으로 확인할 수 있습니다. Git 샘플 자체는 PPT 직전
단계까지만 만들며 템플릿과 PPTX를 포함하지 않습니다. 모든 시스템·계정·응답은 가상
데이터이며 실제 서비스나 자격정보를 포함하지 않습니다.

## 1. 프로젝트 열기

저장소 루트에서 다음 명령을 실행합니다.

```powershell
.\\.venv\\Scripts\\python.exe .\\examples\\open_sample_gui.py
```

또는 Otter의 **프로젝트 열기**에서 다음 폴더를 선택합니다.

`{summary['project']}`

## 2. 취약점 DB 연결 확인

1. **취약점 라이브러리**에서 {library_ids}을 각각 검색합니다.
2. 프로젝트 **취약점**에서 각 항목을 열어 라이브러리 ID와 버전이 유지되는지 확인합니다.
3. 제목·URL·CVSS·상태는 프로젝트별 값으로 바뀌었지만 라이브러리 원본 이름은 유지되어야 합니다.

## 3. 절차·증적 확인

모든 절차에는 증적이 1장 이상 연결됩니다. W-05에는 증적이 2장인 절차가
들어 있고, 나머지는 일반적인 1장 연결 사례입니다. 한 절차의 여러 증적은
절차를 복제하지 않고 같은 절차의 이미지 슬롯에 순서대로 배치되어야 합니다.
모든 취약점의 **결과**에는 증적이 1장 이상 있고, W-28은 별도의 재진단 증적도 포함합니다.

| DB ID | 라이브러리 이름 | 상태 | 절차 수 | 절차별 증적 수 | 결과 증적 | 재진단 |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(matrix_lines)}

## 4. 사용자 템플릿으로 PPT 수동 테스트

1. 왼쪽 **PPT 템플릿**을 엽니다.
2. **파일 불러오기**에서 직접 준비한 PPTX를 선택하고 콘텐츠를 연결합니다.
3. **산출물 > PPT 생성·검토**에서 템플릿을 선택하고 초안을 만듭니다.
4. 모든 절차와 결과에 증적이 1장 이상 표시되는지 확인합니다.
5. W-05의 복수 증적 절차가 하나의 절차 안에서 두 이미지 영역에 순서대로 배치되는지 확인합니다.
6. 전체 대상과 Operations Admin(`WEB-02`) 선택 범위를 각각 확인합니다.
"""
    (destination / "MANUAL-TEST-GUIDE.md").write_text(guide, encoding="utf-8")


def create_sample(
    destination: Path,
    knowledge_database: Path,
    *,
    force: bool = False,
) -> dict:
    destination = destination.expanduser().resolve()
    knowledge_database = knowledge_database.expanduser().resolve()

    _prepare_destination(destination, force)
    destination.mkdir(parents=True)
    evidence_root = destination / "evidence-source"
    rendered = render_evidence(evidence_root, force=True)
    if len(rendered) != EVIDENCE_COUNT:
        raise SystemExit(
            f"Rendered {len(rendered)} evidence images; expected {EVIDENCE_COUNT}"
        )

    service, finding_ids = create_project(
        destination,
        knowledge_database,
        evidence_root,
    )
    evidence_contract = _validate_evidence_contract(service, finding_ids)

    selected_scope = {"mode": "selected-targets", "targetIds": ["WEB-02"]}
    selected_ir = service.build_presentation_ir(scope=selected_scope)
    expected_selected = {
        finding_ids[item["key"]]
        for item in FINDINGS
        if item["target_id"] == "WEB-02"
    }
    actual_selected = {
        str(item["id"]) for item in selected_ir.get("findings", [])
    }
    if actual_selected != expected_selected:
        raise SystemExit(
            f"Selected-target scope mismatch: {actual_selected} != {expected_selected}"
        )

    issues = validate_project(service.root, encrypted=False)
    errors = [item for item in issues if item.get("level") == "ERROR"]
    if errors:
        raise SystemExit(f"Project validation failed: {errors}")

    with sqlite3.connect(destination / "knowledge.db") as connection:
        w_template_count = connection.execute(
            "SELECT COUNT(*) FROM vulnerability_templates WHERE id GLOB 'W-[0-9]*'"
        ).fetchone()[0]

    status_counts = Counter(str(item["status"]) for item in FINDINGS)
    summary = {
        "sample": str(destination),
        "project": str(service.root),
        "knowledgeDatabase": str(destination / "knowledge.db"),
        "knowledgeSource": str(knowledge_database),
        "wTemplateCount": w_template_count,
        "presentationGenerated": False,
        "selectedScope": selected_scope,
        "selectedFindingIds": sorted(actual_selected),
        "findingIds": finding_ids,
        "findingCount": len(FINDINGS),
        "libraryTemplateIds": [item["library_id"] for item in FINDINGS],
        "statusCounts": dict(status_counts),
        "procedureStepCounts": {
            item["library_id"]: len(item["steps"]) for item in FINDINGS
        },
        "evidenceContract": evidence_contract,
        "evidenceCount": EVIDENCE_COUNT,
        "procedureEvidenceCount": PROCEDURE_EVIDENCE_COUNT,
        "resultEvidenceCount": RESULT_EVIDENCE_COUNT,
        "validationIssueCount": len(issues),
    }
    (destination / "sample-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_manual_guide(destination, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--knowledge-db",
        type=Path,
        default=default_knowledge_database_path(),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    create_sample(
        args.destination,
        args.knowledge_db,
        force=args.force,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
