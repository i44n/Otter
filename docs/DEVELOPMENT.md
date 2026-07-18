# Otter 개발 가이드

[English](DEVELOPMENT_EN.md) | **한국어**

## 계층 구조

```text
CLI / PySide6 GUI
        |
        v
ProjectService / KnowledgeService
        |
        +-- project_services/* -> 기능별 프로젝트 업무 규칙
        +-- ProjectRepository -> ProjectStorage -> 폴더 또는 암호화 컨테이너
        +-- CredentialVaultService -> 암호화 계정 금고
        +-- KnowledgeRepository -> SQLite 취약점 지식
        +-- reporting.py facade -> reporting_core/*
                                      +-- 검증
                                      +-- 공통 보고서 뷰
                                      +-- Markdown/CSV
                                      +-- PPT 번들
```

GUI는 JSON이나 SQLite를 직접 읽거나 쓰지 않습니다. `GuiController`를 통해 서비스 계층만 호출하며, 프로젝트 생성과 변경은 모두 `ProjectService`가 담당합니다.

## 주요 모듈

- `models.py`: 불변 데이터 모델 및 입력 모델
- `errors.py`: 코드, 필드, 경로를 포함하는 구조화된 `KitError`
- `localization.py`: UI·오류 언어팩 로딩, fallback과 안정적인 번역 키 처리
- `repository.py`: 프로젝트 파일 접근과 다중 JSON 롤백
- `storage.py`: 평문 디렉터리와 암호화 저장소가 공유하는 프로젝트 경계
- `encrypted_project.py`: `.wpkproj` 봉투 암호화, 잠금, 백업과 복원
- `credential_vault.py`: 계정 모델의 암호화 저장과 수명주기
- `security_crypto.py`: Argon2id 파라미터 검증과 복구키 공통 처리
- `services.py`: 기존 호출 경로를 유지하는 `ProjectService` facade
- `project_services/`: 수명주기, 보안, 대상, 취약점, 증적 연결, 절차, 재검증, 증적, 보관, 보고서와 프레젠테이션 업무 규칙
- `reporting.py`: 기존 보고서 함수 import를 유지하는 facade
- `reporting_core/`: 검증, 언어별 문구, 공통 보고서 뷰, Markdown/CSV, 기존 PPT 번들과 의미 기반 Presentation IR 생성
- `presentation_engine/`: 역할·슬롯 중앙 계약, v1/v2/v3/v4→v5 프로필 및 Plan v1→v2 마이그레이션, 레이아웃 세트·Variant·Story Recipe·다중 콘텐츠 검증, 템플릿 분석·변경 복구, 자동 페이지 계획, OOXML 렌더링과 결과 구조 검증
- `presentation_library.py`: 애플리케이션 공용 PPTX 템플릿·프로필 경로 레지스트리와 변경 상태 감지
- `locking.py`: 스레드·프로세스 간 프로젝트 단위 재진입 잠금
- `schema_versions.py`: 프로젝트 문서의 현재 스키마 버전 검사
- `archives.py`: 대상·취약점·증적 보관과 복구
- `knowledge.py`: 버전형 SQLite 취약점 템플릿
- `gui/controller.py`: Qt 화면과 서비스 계층 사이의 상태 경계
- `qt_gui/pages.py`, `qt_gui/dialogs.py`: 기존 GUI import를 유지하는 facade
- `qt_gui/page_views/`: 대시보드, 대상, 취약점, 증적, 라이브러리, 보고서, PPT 생성, 계정, 보관과 설정 화면
- `qt_gui/dialog_views/`: 프로젝트, 대상, 취약점, 증적, 절차·재검증, 라이브러리와 계정·보안 다이얼로그
- `qt_gui/window_workflows/`: `MainWindow`가 노출하는 기능별 사용자 작업 조정 로직
- `qt_gui/main_window.py`: 앱 셸, 탐색, 반응형 레이아웃과 공통 상태·오류 처리
- `qt_gui/models.py`, `qt_gui/widgets.py`, `qt_gui/theme.py`: 테이블 모델, 공통 위젯과 시각 정책

### Import 경계

- 외부 코드와 테스트는 `services.py`, `reporting.py`, `qt_gui/pages.py`,
  `qt_gui/dialogs.py`의 안정적인 facade를 사용합니다.
- 기능 구현은 facade를 역으로 import하지 않고 저장소 안쪽 계층 또는 같은 기능의
  하위 모듈에만 의존합니다.
- GUI workflow는 페이지와 다이얼로그를 조정하지만 파일, SQLite와 암호화
  컨테이너를 직접 수정하지 않습니다.
- 새 기능은 기존 대형 facade에 구현하지 않고 해당 기능 모듈에 추가합니다.

언어팩 형식과 UI/보고서 언어 분리 규칙은 [LOCALIZATION.md](LOCALIZATION.md)를 참고합니다.

PPT Profile v5는 `presentation_engine/contracts.py`의 역할·슬롯·Variant·반복·조건
예약어만 허용합니다. Layout Family와 레이아웃 ID는 프로필별 내부 식별자이며 Story
Recipe는 고정 역할을 순서화하고 선택적 `familyId`로 Planner 후보 세트를 제한합니다.
의미 역할을 증적 페이지 수와 결합하지 말고,
기본/연속 분할은 Variant로 표현합니다. 다중 절차 페이지는
`composition.itemCapacity`와 연속된 `items.N.*` 슬롯으로 표현하고, Plan v2의
`blocks` 순서는 원본 절차 순서를 유지해야 합니다. 일반 역할의 레이아웃 선택은
모호한 짧음/보통/김 UI가 아니라 바인딩별 `maxChars`와 실제 문자열 길이로 판단합니다.
`stepNumber` 텍스트 바인딩은 선택적 `formatter` 객체를 가질 수 있습니다. 포맷터는
`presentation_engine/formatters.py`에서 검증·변환하며 임의 코드 실행 없이 선언된
sequence 스타일과 단일 `{number}` 토큰만 허용합니다. Planner와 Renderer는 같은
변환 함수를 사용해야 하므로 수용량 판단과 실제 출력 문자열이 달라지지 않습니다.
계약을 바꿀 때는
`schemas/presentation-profile.schema.json`, 한국어·영어 역할 및 슬롯 표시명,
마이그레이션 테스트를 함께 갱신해야 합니다. Profile v1/v2/v3/v4 입력은 로드 시 v5로
변환되며 지원하지 않는 항목을 조용히 삭제하지 않습니다.

## 저장 규칙

개별 텍스트와 JSON 파일은 같은 폴더의 임시 파일에 기록한 뒤 `os.replace()`로 교체합니다. 여러 JSON을 함께 수정할 때는 이전 내용을 저장하고 하나라도 실패하면 전체를 복구합니다.

프로젝트 변경과 보고서 생성은 `.otter.lock`을 사용합니다. 잠금은 같은 스레드에서 재진입할 수 있고 다른 스레드 또는 프로세스와 충돌하면 `PROJECT_LOCK_TIMEOUT` 오류를 반환합니다.

## 스키마 변경

프로젝트 JSON 구조를 바꾸려면 `CURRENT_SCHEMA_VERSION`, `schemas/*.schema.json`, 생성 코드와 테스트를 함께 수정합니다. 현재 개발 데이터는 현재 버전만 지원하며 이전 버전과 알 수 없는 미래 버전은 수정하지 않고 열기를 거부합니다. 실제 사용자 데이터에 대한 호환이 필요해지는 시점부터 명시적인 마이그레이션을 추가합니다.

지식 DB 구조를 변경할 때는 `KNOWLEDGE_SCHEMA_VERSION`과 별도의 DB 마이그레이션을 추가해야 합니다. 라이브러리의 일반 수정은 현재 항목을 제자리에서 갱신하고, 프로젝트에 적용된 취약점은 복사된 스냅샷을 유지합니다. 버전 테이블은 기존 내보내기·가져오기 번들 호환을 위해 남겨 둡니다.

## 지식 DB 경계

SQLite에는 템플릿 ID와 버전, 제목, 설명, 영향, 조치방안, CWE, 태그, 참고자료와 검토 정보만 저장합니다. 고객명, 대상 URL, 실제 취약점, HTTP 증적, 계정정보와 개인정보 필드는 추가하지 않습니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
python -m compileall -q webpentestkit tests examples tools
python examples\create_sample.py --force
python otter.py validate --project examples\generated\acme-shop\project
```

## Windows 배포

`pysidedeploy.spec`는 `desktop.py`를 단일 실행 파일로 패키징하고 프로젝트
생성 및 검증에 필요한 설정·스키마·템플릿 디렉터리를 포함합니다.

```powershell
python -m pip install -r requirements.txt
pyside6-deploy -c pysidedeploy.spec
```

생성 결과는 `dist/`에 기록됩니다. 배포 전 깨끗한 Windows 환경에서 새
프로젝트 생성, 암호화 복사·재열기, 금고 생성·잠금 해제, 백업 복원과 보고서
생성을 다시 확인합니다. macOS 패키지는 macOS 호스트에서 별도로 빌드하고
동일한 스모크 테스트를 수행합니다. `cryptography`는 Windows와 macOS용
정적 링크 wheel을 제공하지만 최종 실행 파일에서 Argon2id와 AES-GCM 동작을
반드시 확인합니다.

새로운 서비스 작업에는 성공 경로뿐 아니라 유효성 오류, 저장 실패 롤백, 보관·복구와 기존 확장 필드 보존 테스트를 추가해야 합니다.

## GUI 작업 규칙

- Qt 이벤트 스레드에서 파일·DB·보고서 장기 작업을 실행하지 않습니다.
- 검증, 보고서와 Export는 `TaskManager`와 `QThreadPool`을 사용합니다.
- 다이얼로그는 구조화된 오류의 `code`와 `field`를 표시합니다.
- 저장 전까지 사용자 입력을 프로젝트에 반영하지 않습니다.
- 취약점과 증적은 삭제 버튼 대신 보관 기능을 제공합니다.
- 색상, 간격과 위젯 스타일은 `docs/GUI_DESIGN.md`와 `qt_gui/theme.py`를 따릅니다.
