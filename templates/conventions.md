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
- RetestFailed
- RetestPassed

## Severity

- Critical
- High
- Medium
- Low
- Info

## Evidence

- 원본은 `evidence/raw`에 보관합니다.
- 보고서에 넣을 자료는 마스킹과 크롭을 완료한 뒤 `evidence/report`에 보관합니다.
- 비밀번호, 토큰, 쿠키, 개인정보는 `[REDACTED]`로 대체합니다.
- 원본 증적은 수정하지 않고 보고서용 사본을 별도로 만듭니다.

## PPT Text Limits

- 제목: 50자 이내
- 요약: 150자 이내
- 영향: 120자 이내
- 개선 방안: 150자 이내
- 증적 설명: 80자 이내
