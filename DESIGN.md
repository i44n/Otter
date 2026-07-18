# 설계 개요

## 애플리케이션 계층

CLI와 PySide6 GUI는 동일한 `ProjectService`와 `KnowledgeService`를 사용합니다. 프로젝트 파일 접근은 `ProjectRepository`, 취약점 지식 DB 접근은 `KnowledgeRepository`가 담당하며 GUI에서 JSON 또는 SQLite를 직접 수정하지 않습니다.

`services.py`는 외부 호출이 의존하는 `ProjectService` facade만 제공하고 실제 업무
규칙은 `project_services/`의 프로젝트 수명주기, 보안, 대상, 취약점, 증적 연결,
절차, 재검증, 증적, 보관과 보고서 기능 모듈이 담당합니다. 같은 방식으로
`reporting.py`, `qt_gui/pages.py`, `qt_gui/dialogs.py`는 기존 import 경로를 유지하는
facade이며 실제 구현은 각각 `reporting_core/`, `qt_gui/page_views/`,
`qt_gui/dialog_views/`에 있습니다.

`MainWindow`는 애플리케이션 셸, 탐색과 공통 상태를 소유합니다. 프로젝트, 계정,
보안, 진단, 증적, 라이브러리, 보고서와 관리 작업의 조정 로직은
`qt_gui/window_workflows/`에 분리되어 있습니다. 기능 모듈은 facade를 역으로
import하지 않으며, 바깥 계층에서 안쪽 계층으로만 의존합니다.

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
  ┌──────────┴─────────────────────────┐
  ↓                                    ↓
CSV/Markdown                 semantic Report IR v2
                                      ↓
                         Template Profile + Render Plan
                                      ↓
                         owned OOXML presentation engine
                                      ↓
                         final PPTX + Render Manifest
```

## PPT 생성기와의 경계

공통 보고서 뷰는 특정 회사 레이아웃이나 페이지 수를 알지 못하는 의미 기반
`Report IR v2`를 만듭니다. 사용자는 프로젝트와 독립적인 **공용 라이브러리 > PPT 템플릿**에서
템플릿의 예시 슬라이드와 일반 도형을 의미 슬롯에 연결해 `Template Profile`을
만듭니다. 프로젝트의 **산출물 > PPT 생성·검토**에서 Planner가 실제
슬라이드 순서·레이아웃·증적 배치를 담은 `Render Plan`을 생성합니다. 사용자는
계획에서 슬라이드 순서, 포함 여부, 이미지 fit과 초점 위치를 조정할 수 있습니다.

`presentation_engine/`은 원본 PPTX의 마스터, 레이아웃과 미지원 패키지 부분을
보존하면서 매핑된 텍스트와 이미지 영역만 수정합니다. OLE, think-cell, SmartArt,
차트와 애니메이션은 초기 지원 범위에서 내부 값을 변경하지 않고 preserve-only로
분류합니다.

역할·의미 슬롯·바인딩 종류·이미지 맞춤 방식은
`presentation_engine/contracts.py`가 단일 계약으로 관리합니다. GUI, 프로필 검증,
플래너와 언어팩은 같은 계약을 사용하며 임의 역할이나 슬롯은 렌더 단계까지
전파되지 않습니다. Profile v5는 의미 역할과 페이지 분할 방식을 분리하고 각
레이아웃의 `composition.itemCapacity`와 `items.N.*` 슬롯으로 한 슬라이드에 들어갈
콘텐츠 영역을 1~12개로 명시합니다. 이 반복 영역 편집은 현재 여러 절차를 한 장에
배치하는 `finding-procedure`에서만 노출됩니다. 각 텍스트 바인딩의 `maxChars`는
도형 크기에서 자동 추정하고 Planner는 실제 슬롯 문자열 길이를 이 수치와 비교합니다.
`stepNumber`에는 선택적으로 안전한 sequence
`formatter`를 연결할 수 있으며, 같은 슬라이드 유형의 `items.N.stepNumber`에는 GUI가
동일 형식을 전파합니다. 내부 `STEP-###` ID와 정렬 값은 표시 형식과 분리됩니다.
과거 `textDensity`는 호환 필드로만 유지합니다.

내부 `Layout Family`는 같은 시각 양식의 레이아웃 세트입니다. 일반 매핑 화면에서는
별도 편집 항목으로 노출하지 않고 역할별 기본 세트를 자동 생성합니다. `Story Recipe`
노드의 선택적 `familyId`만 특정 세트로 자동 선택 범위를 제한하며, 지정하지 않으면
해당 역할의 모든 레이아웃을 비교합니다. 각 레이아웃의 `Variant`는
기본·연속·원본 고정 페이지와 영역별 증적 용량·선택 조건을 표현합니다. `Story Recipe`는 고정
역할을 문서·취약점·부록 그룹에서 어떤 순서와 반복 규칙으로 전개할지 정의합니다.
사용자는 전개 순서와 자동 선택 세트는 구성할 수 있지만 역할·슬롯·Variant·반복·조건
코드는 예약된 계약 값만 선택합니다.

`finding-result`는 절차의 마지막 단계가 아니라 취약점의 최종 관찰 결과와 결과
증적을 담는 독립 역할입니다. 절차 단계 수와 증적 수는 데이터에 따라 늘어나며,
Planner는 연속 절차 블록의 텍스트와 증적이 각 영역에 맞는지 검사해 가장 큰
묶음을 선택하므로 페이지 전개는 `2·1·1·2·1`처럼 데이터에 따라 달라집니다.
Render Plan v2의 `blocks`가 한 페이지에 배치된 절차와 각 증적을 보존하며, 남는
증적만 연속 페이지로 분할합니다. 같은 물리적 디자인을 절차와 결과에
재사용하려면 같은 Family 안에서 매핑을 복제한 뒤 역할만 바꿉니다.

v1/v2/v3/v4 프로필은 알려진 역할을 v5 역할·Variant·콘텐츠 구성·선택 세트 계약으로
자동 변환하며 지원하지 않는 매핑은 `legacyCompatibility`에 격리합니다.

템플릿과 프로필의 SHA-256이 다르면 바로 렌더하지 않고 이전 도형 지문과 새
템플릿의 도형 이름·유형·문구·좌표를 비교해 자동 복구, 사용자 검토, 누락으로
분류합니다. 검토 또는 누락 항목이 남은 프로필은 계획 및 렌더를 차단합니다.
공용 템플릿 라이브러리는 애플리케이션 데이터 영역에 템플릿·프로필 경로만
등록하고 프로젝트별 Render Plan과 결과 PPTX는 프로젝트 보고서 영역에 둡니다.

기존 `slides.json formatVersion: 1` PPT-ready bundle은 외부 연동 호환성을 위해
계속 지원합니다.

v5 기본 슬라이드 역할:

- `cover`
- `section-divider`
- `executive-summary`
- `project-overview`
- `scope-methodology`
- `severity-summary`
- `target-summary`
- `finding-overview`
- `finding-technical`
- `finding-procedure`
- `finding-result`
- `finding-remediation`
- `finding-retest`
- `evidence-appendix`
- `template-static`

과거 `finding-detail`과 `*-evidence` 값은 기존 외부 PPT 자료 묶음과 v1/v2 Profile
입력 호환성에만 남습니다. v3에서 증적 연속 페이지는 별도 의미 역할이 아니라
동일 역할의 `continuation` Variant입니다.

이 경계를 유지하면 렌더러 구현을 교체해도 점검 프로젝트 구조와 Report IR은
바뀌지 않습니다.

## 호환성

- Python 3.10 이상
- Windows, macOS
- 데스크톱 UI는 PySide6, 암호화는 cryptography를 사용
- 경로는 내부적으로 `pathlib`로 처리
- JSON과 Markdown은 UTF-8
- Excel 호환을 위해 CSV는 UTF-8 BOM으로 생성
- Export 내부 참조 경로는 운영체제와 무관한 `/` 형식
