# Writing and Management Conventions

## Identifiers

- 웹사이트: `WEB-01`, `WEB-02`
- 취약점: `WEB-01-001`, `WEB-02-001`
- 증적: `EVD-001`, `EVD-002`

## Finding Status

- Draft
- Confirmed
- FalsePositive
- Accepted
- Resolved

## Target Status

- Testing
- Paused
- Completed

## Severity

- Critical
- High
- Medium
- Low
- Info

## Evidence

- 모든 증적 파일은 `evidence/files`에 보관하고 공개 상태는 `classification`으로 관리합니다.
- 보고서에 넣을 자료는 마스킹과 크롭을 완료한 뒤 `report-ready`로 분류합니다.
- 비밀번호, 토큰, 쿠키, 개인정보는 `[REDACTED]`로 대체합니다.
- 원본 증적은 수정하지 않고 보고서용 사본을 별도 EVD로 만들고 `derivedFrom`으로 연결합니다.

## PPT Text Limits

- 제목: 50자 이내
- 요약: 150자 이내
- 영향: 120자 이내
- 개선 방안: 150자 이내
- 증적 설명: 80자 이내
