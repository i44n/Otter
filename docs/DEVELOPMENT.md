# Otter 개발 가이드

## 계층 구조

```text
CLI / PySide6 GUI
        |
        v
ProjectService / KnowledgeService
        |
        +-- ProjectRepository -> ProjectStorage -> 폴더 또는 암호화 컨테이너
        +-- CredentialVaultService -> 암호화 계정 금고
        +-- KnowledgeRepository -> SQLite 취약점 지식
        +-- reporting.py -> 검증/보고서/PPT 번들
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
- `services.py`: 프로젝트, 대상, 취약점, 증적, 보관, 보고서 업무 규칙
- `locking.py`: 스레드·프로세스 간 프로젝트 단위 재진입 잠금
- `schema_versions.py`: 프로젝트 문서의 현재 스키마 버전 검사
- `archives.py`: 대상·취약점·증적 보관과 복구
- `knowledge.py`: 버전형 SQLite 취약점 템플릿
- `gui/controller.py`: Qt 화면과 서비스 계층 사이의 상태 경계
- `qt_gui/`: PySide6 앱 셸, 화면, 다이얼로그, 테이블 모델, 테마와 작업 실행기

언어팩 형식과 UI/보고서 언어 분리 규칙은 [LOCALIZATION.md](LOCALIZATION.md)를 참고합니다.

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
python -m compileall -q webpentestkit tests examples
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
