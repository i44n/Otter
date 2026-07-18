from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webpentestkit.knowledge import KnowledgeService  # noqa: E402


DEFAULT_SOURCE = ROOT / "knowledge" / "kisa-web-2021-templates.json"
DEFAULT_OUTPUT_DIR = ROOT / "examples" / "generated" / "kisa-web-2021"
EXPECTED_IDS = tuple(f"WEB-{index:02d}" for index in range(1, 29))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the KISA 2021 WEB vulnerability library for Otter."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def _temporary_path(directory: Path, *, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix=".kisa-web-2021-",
        suffix=suffix,
        dir=directory,
        delete=False,
    )
    path = Path(handle.name)
    handle.close()
    return path


def _validate_catalog(service: KnowledgeService) -> list:
    templates = service.search_templates(status="Approved")
    by_id = {template.id: template for template in templates}
    if tuple(sorted(by_id)) != EXPECTED_IDS:
        raise RuntimeError(
            f"Expected {list(EXPECTED_IDS)}, got {sorted(by_id)}"
        )
    for template_id in EXPECTED_IDS:
        template = by_id[template_id]
        if template.version != 1:
            raise RuntimeError(f"{template_id} must be version 1")
        if template.name != template.title:
            raise RuntimeError(f"{template_id} must preserve the KISA name as title")
        if template.default_severity != "High":
            raise RuntimeError(f"{template_id} must preserve KISA importance High")
        if template.cvss_vector:
            raise RuntimeError(f"{template_id} must leave project-specific CVSS empty")
        if not template.summary or not template.impact or not template.remediation:
            raise RuntimeError(f"{template_id} is missing required report content")
        if len(template.remediation_detail) < 3:
            raise RuntimeError(f"{template_id} needs detailed remediation steps")
        if len(template.references) < 3:
            raise RuntimeError(f"{template_id} needs KISA and external references")
        if not any("krcert.or.kr" in item for item in template.references):
            raise RuntimeError(f"{template_id} is missing the KISA source")
        if not template.cwes:
            raise RuntimeError(f"{template_id} is missing a CWE mapping")
    return [by_id[template_id] for template_id in EXPECTED_IDS]


def build(source: Path, output_dir: Path) -> dict:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise FileNotFoundError(source)

    database = output_dir / "knowledge.db"
    bundle = output_dir / "kisa-web-2021.knowledge.json"
    summary_path = output_dir / "catalog-summary.json"
    temporary_database = _temporary_path(output_dir, suffix=".db")
    temporary_bundle = _temporary_path(output_dir, suffix=".json")
    try:
        service = KnowledgeService.open(temporary_database, seed_path=source)
        templates = _validate_catalog(service)
        service.export_bundle(temporary_bundle)
        os.replace(temporary_database, database)
        os.replace(temporary_bundle, bundle)
    finally:
        temporary_database.unlink(missing_ok=True)
        temporary_bundle.unlink(missing_ok=True)

    category_counts = Counter(template.category for template in templates)
    summary = {
        "catalog": "KISA 주요정보통신기반시설 상세가이드 2021 - Web(웹)",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(source),
        "database": str(database),
        "importBundle": str(bundle),
        "templateCount": len(templates),
        "approvedCount": sum(template.status == "Approved" for template in templates),
        "highImportanceCount": sum(
            template.default_severity == "High" for template in templates
        ),
        "projectSpecificCvssCount": sum(
            not template.cvss_vector for template in templates
        ),
        "categoryCounts": dict(sorted(category_counts.items())),
        "templates": [
            {
                "id": template.id,
                "name": template.name,
                "originalCode": next(
                    tag
                    for tag in template.tags
                    if len(tag) == 2 and tag.isupper()
                ),
                "category": template.category,
                "severity": template.default_severity,
                "cwes": list(template.cwes),
                "referenceCount": len(template.references),
            }
            for template in templates
        ],
        "cvssPolicy": (
            "Reusable weakness classes do not receive a fabricated CVSS vector. "
            "Calculate CVSS 3.1 from the concrete project finding."
        ),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = _parser().parse_args()
    summary = build(args.source, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
