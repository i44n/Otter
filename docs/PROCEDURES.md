# 재현 절차와 증적

[English](PROCEDURES_EN.md) | **한국어**

## 설계 원칙

재현 절차, 재검증 이력, 증적 파일과 증적 사용처는 수명주기가 다르므로 분리해서 저장합니다.

- `procedure.json`은 테스터가 수행한 단계와 순서를 관리합니다.
- `retests.json`은 취약점 단위 재검증 이력과 결과를 관리합니다.
- `evidence/evidence.json`은 파일 자산, 설명, 공개 분류와 파생 원본 관계를 관리합니다.
- `evidence/links.json`은 하나의 EVD가 취약점 본문, 기술 상세, 절차 단계 또는 재검증에서 어떻게 쓰이는지 관리합니다.
- 절차와 재검증 JSON은 파일 경로나 EVD 목록을 중복 저장하지 않습니다.
- Export에서는 같은 증적 파일을 한 번만 복사합니다.

## GUI 사용

1. 취약점 화면에서 항목을 선택하고 **수정**을 누릅니다.
2. **재현 절차** 탭에서 사전 조건과 단계를 추가합니다.
3. 단계 제목, 수행 내용, 예상 결과와 관찰 결과를 작성합니다.
4. 증적 목록에서 기존 EVD를 선택하거나 **+ 새 증적 등록 후 연결**을 사용합니다.
5. **기술 상세**에는 발생 원인과 분석을 작성하고 HTTP 요청·응답 원문은 증적으로 연결합니다.
6. **위**, **아래** 버튼으로 단계 순서를 정하고 전체 편집창을 저장합니다.

새 취약점을 작성할 때도 증적을 추가할 수 있습니다. 새 파일은 편집 세션 안에서 임시 상태로 유지되며 전체 저장에 성공해야 취약점, 절차, 증적과 연결이 함께 반영됩니다. 편집을 취소하거나 저장이 실패하면 임시 증적은 프로젝트에 남지 않습니다.

내부용 또는 민감 증적도 업무 기록을 위해 연결할 수 있지만 산출물에는 `report-ready` 증적만 출력됩니다. 검증기는 산출물에 표시되지 않는 연결을 경고로 알려줍니다.

## 저장 구조

`procedure.json`에는 절차 자체만 저장합니다.

```json
{
  "schemaVersion": 3,
  "findingId": "WEB-01-001",
  "preconditions": "권한이 다른 테스트 계정 2개가 준비되어 있습니다.",
  "nextStepNumber": 3,
  "steps": [
    {
      "id": "STEP-001",
      "order": 10,
      "title": "일반 사용자로 로그인",
      "action": "계정 A로 로그인합니다.",
      "expectedResult": "계정 A의 데이터만 조회됩니다.",
      "observedResult": ""
    },
    {
      "id": "STEP-002",
      "order": 20,
      "title": "객체 ID 변경",
      "action": "요청의 객체 ID를 계정 B의 값으로 바꿉니다.",
      "expectedResult": "요청이 거부됩니다.",
      "observedResult": "계정 B의 데이터가 반환됩니다."
    }
  ],
  "updatedAt": "2026-07-15T12:27:14+09:00"
}
```

증적 사용처는 `evidence/links.json`에 저장합니다.

```json
{
  "schemaVersion": 3,
  "findingId": "WEB-01-001",
  "items": [
    {
      "evidenceId": "EVD-001",
      "scopeType": "procedure",
      "scopeId": "STEP-002",
      "caption": "계정 B의 주문 정보가 반환된 응답",
      "placement": "inline",
      "order": 10
    },
    {
      "evidenceId": "EVD-001",
      "scopeType": "technical",
      "scopeId": "",
      "caption": "권한 검증 누락을 보여주는 HTTP 교환",
      "placement": "inline",
      "order": 10
    }
  ]
}
```

`STEP-###`와 `RT-###` ID는 순서를 바꾸어도 유지되고 삭제된 번호는 재사용하지 않습니다.

## 보관과 Export

증적을 보관하면 파일, 자산 메타데이터와 모든 Evidence Link가 함께 보관됩니다. 복원할 때 절차 단계나 재검증 기록이 여전히 존재하는 연결만 복원합니다.

Markdown 보고서와 PPT 번들은 동일한 Finding Report View를 사용합니다. 취약점 본문, 기술 상세, 절차와 재검증에 연결된 `report-ready` 증적이 같은 기준으로 선택되며 HTTP 텍스트 증적은 기술 상세에 자동 렌더링됩니다. 슬라이드당 표시 용량을 넘는 증적은 연속 슬라이드로 출력되고 파일은 한 번만 복사됩니다.

## 재검증 이력

재검증은 취약점 단위의 독립 이력입니다. 날짜, 담당자, 전체 결과, 적용 조치, 검증 내용과 증적을 기록합니다. 재검증 결과는 취약점의 업무 상태를 자동으로 변경하지 않습니다.

- 취약점 상태: `Draft`, `Confirmed`, `FalsePositive`, `Accepted`, `Resolved`
- 재검증 결과: `Pending`, `Passed`, `Failed`, `Partial`
- 화면에서 표시하는 최신 재검증 결과는 날짜·수정 시각·ID 순으로 계산합니다.
