# 설계 개요

## 애플리케이션 계층

CLI와 PySide6 GUI는 동일한 `ProjectService`와 `KnowledgeService`를 사용합니다. 프로젝트 파일 접근은 `ProjectRepository`, 취약점 지식 DB 접근은 `KnowledgeRepository`가 담당하며 GUI에서 JSON 또는 SQLite를 직접 수정하지 않습니다.

프로젝트 변경은 프로젝트 단위 잠금 안에서 수행됩니다. 취약점 편집은 `finding.json`, `procedure.json`, 증적 manifest와 연결을 하나의 편집 단위로 취급하며 실패 시 이전 내용을 복구합니다. 편집창에서 새로 고른 증적은 저장 전까지 임시 상태로 유지됩니다. 재검증 결과는 `retests.json`의 독립 이력이며 취약점 업무 상태를 자동으로 덮어쓰지 않습니다. 삭제가 필요한 업무는 `archive/` 보관과 복구로 처리합니다.

SQLite 지식 DB는 버전형 템플릿만 저장합니다. 템플릿을 프로젝트 취약점에 적용하면 문구를 복사하고 `template.id`와 `template.version`을 기록해 과거 보고서가 이후 템플릿 변경에 영향을 받지 않게 합니다.

## 목표

한 프로젝트 안에서 여러 웹사이트를 분리하여 관리하고, 웹별 취약점과 증적을 일관된 형식으로 기록한 뒤 보고서와 PPT 작성용 자료를 재생성할 수 있도록 설계했습니다.

## 기준 데이터

- `project.json`: 프로젝트 식별 정보
- `report-config.json`: 보고서 및 PPT 정책
- `target.json`: 웹사이트별 정형 정보
- `finding.json`: 취약점, 업무 상태, 심각도, 보고서 문구 및 원인·분석
- `procedure.json`: 재현 단계, 순서와 예상·관찰 결과
- `retests.json`: 취약점 단위 재검증 이력과 전체 결과·검증 내용
- `evidence/evidence.json`: 증적 파일 자산, 설명, 분류와 파생 원본 관계
- `evidence/links.json`: 취약점 본문·기술 상세·절차·재검증의 EVD 사용처, 문맥과 배치

증적 파일은 취약점에 한 번 등록하고 `links.json`에서 사용처를 연결합니다. `classification`은 `internal`, `report-ready`, `sensitive` 중 하나이며 파일 위치와 독립적입니다. 분류를 변경해도 파일을 이동하지 않습니다. 보고서 생성기는 `report-ready` 증적만 공통 Finding Report View에 올리고 Markdown과 PPT가 같은 뷰를 사용합니다. HTTP 요청·응답 원문은 기술 상세에 복사하지 않고 `technical` 사용처로 연결한 증적에서 읽습니다.

CSV, Markdown 현황표와 PPT Export 결과는 파생 데이터입니다. 파생 데이터는 직접 수정하지 않고 기준 데이터에서 다시 생성합니다.

## 데이터 흐름

```text
프로젝트 원본
  ├─ target.json
  ├─ finding.json + procedure.json + retests.json
  └─ evidence.json + links.json + evidence/files
             ↓
     common report view
             ↓
          validate/render
             ↓
  ┌──────────┴──────────┐
  ↓                     ↓
CSV/Markdown       PPT-ready bundle
                   ├─ slides.json
                   ├─ SVG charts
                   └─ curated evidence
```

## PPT 생성기와의 경계

키트 본체는 특정 회사 PPT 레이아웃을 알지 못합니다. `slides.json`이 표준 중간 규격 역할을 하며, 별도 PPT 생성기가 슬라이드 타입에 맞는 회사 템플릿 레이아웃을 선택합니다.

기본 슬라이드 타입:

- `cover`
- `project-overview`
- `severity-summary`
- `target-summary`
- `finding-detail`
- `finding-technical`
- `finding-evidence`
- `finding-procedure`
- `finding-procedure-evidence`
- `finding-retest`
- `finding-retest-evidence`

이 경계를 유지하면 PowerPoint COM, AppleScript, `python-pptx` 또는 웹 기반 문서 생성기를 교체해도 점검 프로젝트 구조는 바뀌지 않습니다.

## 호환성

- Python 3.9 이상
- Windows, macOS
- Python 표준 라이브러리만 사용
- 경로는 내부적으로 `pathlib`로 처리
- JSON과 Markdown은 UTF-8
- Excel 호환을 위해 CSV는 UTF-8 BOM으로 생성
- Export 내부 참조 경로는 운영체제와 무관한 `/` 형식
