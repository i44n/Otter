# 언어팩 개발

Otter의 UI 언어와 보고서 언어는 서로 독립적입니다.

- **UI 언어**는 `QSettings`의 `appearance/uiLanguage`에 저장되고 프로그램을 다시 시작할 때 적용됩니다.
- 새 설치의 기본 UI 언어는 영어(`en-US`)이며, 사용자가 선택한 언어 설정이 있으면 그 값을 우선합니다.
- **보고서 언어**는 프로젝트 `report-config.json`의 `presentation.language`이며 프로젝트와 함께 이동합니다. 현재 내장 Markdown 및 PPT 번들 출력은 영어(`en-US`)와 한국어(`ko-KR`)를 지원하고 새 프로젝트는 영어가 기본입니다.
- 심각도, 상태, 증적 분류 같은 저장 값은 번역하지 않습니다. 번역은 화면과 오류 출력 경계에서만 적용합니다.

## 언어팩 위치

내장 언어팩은 `webpentestkit/locales/*.json`에 둡니다. 사용자가 설치하는 언어팩은 Qt가 제공하는 앱 데이터 경로 아래 `languages` 폴더에서 검색합니다. 개발 중에는 `OTTER_LANGUAGE_PATHS` 환경 변수에 `os.pathsep`으로 구분한 추가 폴더를 지정할 수 있습니다.

Windows 배포 설정은 `webpentestkit/locales`를 실행 파일에 포함해야 합니다.

## 파일 형식

```json
{
  "schemaVersion": 1,
  "locale": "en-US",
  "name": "English",
  "fallback": "ko-KR",
  "messages": {
    "ui": {
      "nav.dashboard": "Dashboard",
      "sample.count": "Count: {count}"
    },
    "errors": {
      "PROJECT_NOT_OPEN": "Open a project first."
    }
  }
}
```

- 언어팩은 UTF-8 JSON이며 최대 크기는 1 MiB입니다.
- `schemaVersion`은 현재 `1`만 허용합니다.
- `locale`은 `ko-KR`, `en-US` 같은 정규화 가능한 식별자여야 합니다.
- `fallback`에 지정한 언어에 키가 없으면 최종적으로 내장 `ko-KR` 언어팩을 확인합니다.
- 메시지 매개변수는 `{count}`, `{item_id}`처럼 이름 기반으로 작성합니다.
- 번역 키는 문구가 바뀌어도 유지합니다. 화면 문장 자체를 키로 사용하지 않습니다.

## 코드에서 사용

```python
from webpentestkit.localization import tr

label = tr("nav.dashboard", "대시보드")
count = tr("sample.count", "개수: {count}", count=3)
```

업무 로직은 번역문을 비교하지 않습니다.

```python
combo.addItem(tr("status.confirmed", "확인됨"), "Confirmed")
status = combo.currentData()  # 항상 Confirmed
```

`KitError`는 기존 한국어 메시지를 fallback으로 유지하면서 코드와 매개변수를 제공합니다.

```python
raise KitError(
    "항목을 찾을 수 없습니다.",
    code="ITEM_UNKNOWN",
    params={"item_id": item_id},
)
```

GUI는 `localize_error()`를 사용하므로 언어팩의 `errors.ITEM_UNKNOWN`이 있으면 번역문을 표시합니다. CLI와 로그는 기존 오류 메시지를 계속 사용할 수 있습니다.

## 새 화면 개발 규칙

1. 사용자에게 보이는 새 문구는 안정적인 키와 한국어 fallback을 함께 `tr()`에 전달합니다.
2. JSON 필드, ID, enum과 필터 비교값은 번역하지 않습니다.
3. UI 언어와 보고서 언어를 한 설정으로 합치지 않습니다.
4. 실행 중 전체 위젯 재번역은 아직 지원하지 않으므로 UI 언어 변경 후 재시작을 안내합니다.
5. 언어팩에는 고객 데이터, 경로, 인증정보를 넣지 않습니다.

## 영어 번역 작업 흐름

영어 원문 번역은 `translations/en-US/*.json`에 기능 영역별로 나눠 관리하고,
실행 시 사용하는 안정적인 키 기반 파일은 빌드 명령으로 생성합니다.

```powershell
python tools/i18n.py wrap
python tools/i18n.py build
python tools/i18n.py audit
```

- `wrap`은 Qt GUI 파일에 남은 한국어 리터럴을 `tr()` 호출과 안정적인 생성 키로 전환합니다. 새 문구를 추가한 뒤 한 번만 실행합니다.
- `build`는 한국어 카탈로그와 `translations/en-US`의 원문 번역을 결합해 `webpentestkit/locales/en-US.json`을 생성합니다.
- `audit`은 미래핑 한국어 UI 문구, 양쪽 카탈로그의 키 차이, 영어 언어팩의 한글 잔존, 서식 치환 변수 불일치를 검사합니다.

생성 키는 문구의 해시를 사용하므로 이미 코드에 들어간 키를 번역문이나 문구 변경에 맞춰 임의로 바꾸지 않습니다. 자주 재사용되거나 도메인 의미가 중요한 문구는 `nav.dashboard`처럼 사람이 정한 의미 기반 키를 우선 사용합니다.

## 검증

```powershell
python tools/i18n.py audit
python -m unittest tests.test_localization -v
python -m unittest discover -s tests -v
```

새 언어팩에는 최소한 fallback, 매개변수 치환, 오류 코드 번역과 1024px 화면 렌더링 테스트를 추가합니다.
