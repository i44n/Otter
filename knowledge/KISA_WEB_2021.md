# KISA 2021 WEB vulnerability catalog

This catalog turns the 28 Web(Web) inspection items in the supplied 2021 KISA
guide into reusable Otter vulnerability templates.

- Source data: `knowledge/kisa-web-2021-templates.json`
- Builder: `tools/build_kisa_web_knowledge.py`
- Generated SQLite database: `examples/generated/kisa-web-2021/knowledge.db`
- UI import bundle: `examples/generated/kisa-web-2021/kisa-web-2021.knowledge.json`
- Build summary: `examples/generated/kisa-web-2021/catalog-summary.json`

Build from the repository root:

```powershell
.venv\Scripts\python.exe tools\build_kisa_web_knowledge.py
```

To add the catalog to an existing Otter installation, open **취약점 라이브러리**,
choose **DB 가져오기**, and select `kisa-web-2021.knowledge.json`. Importing the
same bundle again is safe and does not create duplicate versions.

## Content policy

- IDs are `WEB-01` through `WEB-28` in the exact guide order.
- Korean `name` and `title` preserve the guide wording exactly.
- The guide marks all 28 items as importance `상`; this is represented as the
  template default severity `High`.
- Generic weakness classes do not have enough target, privilege, scope, or
  impact context for an honest CVSS vector. `cvssVector` is therefore empty and
  must be calculated on the concrete project finding with Otter's CVSS 3.1
  calculator.
- Templates contain common knowledge only. Project procedures and evidence are
  added after a template is applied to a project.

## Sources

- [KISA 2021 detailed guide PDF](https://www.krcert.or.kr/common/cmm/fms/FileDown.do?atchFileId=FILE_000000000035988&fileSn=2736)
- [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [MITRE Common Weakness Enumeration](https://cwe.mitre.org/)
- [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html)
