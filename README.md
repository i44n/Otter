<div align="center">
  <img src="docs/assets/otter-logo.png" width="128" alt="Otter logo">
  <h1>Otter</h1>
  <p><strong>From finding to report, without copying evidence between tools.</strong></p>
  <p>A local-first desktop workspace for authorized web security assessments.</p>
  <p>
    <img alt="Beta version" src="https://img.shields.io/badge/version-0.1.0b1%20beta-F59E0B">
    <a href="https://github.com/Insu-Cho/Otter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Insu-Cho/Otter/actions/workflows/ci.yml/badge.svg"></a>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
    <img alt="Qt for Python" src="https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white">
    <img alt="Platforms" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey">
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green"></a>
  </p>
</div>

> [!WARNING]
> Otter is in public beta. Back up important work and expect project formats and
> workflows to change before 1.0. Pre-beta projects are not migrated automatically.

![Otter dashboard showing assessment metrics, severity distribution, and recent findings](docs/assets/screenshots/otter-dashboard.png)

Otter keeps targets, findings, reproduction procedures, evidence, finding-level
retests, reusable vulnerability guidance, and report outputs in one structured
workspace. Data stays local by default and a project can be sealed into an
encrypted `.wpkproj` container.

Otter organizes assessment work. It does **not** scan targets or run attacks.

## Why Otter?

- **One structured finding record** — affected request, impact, remediation,
  technical analysis, reproduction procedure, retest history, and linked evidence.
- **Evidence with traceable purpose** — classify an asset once, then link it to a
  finding body, technical details, a procedure step, or a retest without copying it.
- **Delivery confidence** — validate project data and evidence policy before
  generating Markdown, CSV, and a presentation-ready data bundle.
- **Local-first security** — work without a server, encrypt project containers,
  and keep assessment credentials in a separate authenticated vault.
- **Reusable knowledge** — search, review, update, archive, and transfer a
  versioned vulnerability library.

## See the workflow

### Keep the complete finding in one place

Capture the affected request, business impact, remediation, root cause, analysis,
and reproduction procedure as structured data instead of scattering notes across
documents.

![Structured finding details with technical analysis and reproduction steps](docs/assets/screenshots/otter-finding-workspace.png)

### Retest at finding level and keep the evidence trail

Record each remediation check against the finding, preserve the verification
history, and see exactly where every linked evidence item is used.

![Finding-level retest history and linked evidence table](docs/assets/screenshots/otter-retest-evidence.png)

### Reuse evidence without duplicating request and response text

HTTP exchanges and other evidence remain independent assets. Otter shows their
disclosure status, linked finding, and output settings for every usage.

![Sanitized HTTP evidence with disclosure status and usage traceability](docs/assets/screenshots/otter-evidence-traceability.png)

### Turn reviewed guidance into new findings

Maintain reusable vulnerability summaries, impact statements, remediation advice,
CWE references, tags, review metadata, and history in the finding library.

![Reviewed finding-library template ready to create a project finding](docs/assets/screenshots/otter-finding-library.png)

### Validate before delivery

Review data-quality and evidence-policy findings, confirm report readiness, generate
Markdown and CSV outputs, and export structured content for presentation creation.

![Validation and report readiness overview](docs/assets/screenshots/otter-validation-reports.png)

### Protect local assessment data

Create an encrypted project copy, rotate its password, and create verified backups
from the project settings. Exported report files are intentionally treated as
separate deliverables and are not protected by the project container.

![Project settings with plaintext status and encrypted-copy action](docs/assets/screenshots/otter-project-protection.png)

## Quick start

Requirements:

- Python 3.10 or newer
- Windows or macOS

### Windows

```powershell
git clone https://github.com/Insu-Cho/Otter.git
cd Otter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\otter.py gui
```

### macOS

```bash
git clone https://github.com/Insu-Cho/Otter.git
cd Otter
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 ./otter.py gui
```

### Explore the fictional sample

The generated ACME project uses only `example.test` hosts and fictional evidence.

```powershell
python .\examples\create_sample.py --force
python .\examples\open_sample_gui.py
```

## Typical assessment flow

1. Create a project and register assessment targets.
2. Add findings directly or start from the finding library.
3. Record technical analysis and reproducible steps.
4. Add evidence once and link it to the scopes where it is used.
5. Record finding-level retests with supporting evidence.
6. Validate the project and review security or content recommendations.
7. Generate Markdown/CSV reports and export the PPT-ready bundle.

## Outputs

Otter currently generates:

- final and summary Markdown reports;
- target and finding summaries;
- findings CSV;
- a localized validation report;
- a presentation-ready folder with `slides.json`, SVG charts, finding content,
  and curated report-ready evidence.

The beta does not render a finished `.pptx` file. The exported bundle is designed
for a separate presentation-production step.

## Project and security model

Project source files are readable JSON and evidence files so they remain auditable.
The current internal project schema is version 3; this is independent of the Otter
application version.

Only linked evidence classified as report-ready is emitted to deliverables.
Automated secret detection is a safeguard, not a replacement for human review.
Keep recovery keys offline, use full-disk encryption, and never commit customer
projects, credentials, target URLs, or raw evidence.

Please report suspected vulnerabilities privately according to
[SECURITY.md](SECURITY.md). Do not open a public issue for a security vulnerability.

<details>
<summary>Project layout</summary>

```text
project/
├─ project.json
├─ report-config.json
├─ targets/
│  └─ WEB-01-.../
│     ├─ target.json
│     └─ findings/
│        └─ WEB-01-001-.../
│           ├─ finding.json
│           ├─ procedure.json
│           ├─ retests.json
│           └─ evidence/
│              ├─ evidence.json
│              ├─ links.json
│              └─ files/
└─ archive/
```

</details>

## Beta status

The current public development version is `0.1.0b1`.

- Project schemas and workflows may change before 1.0.
- Pre-beta project migrations are intentionally not provided.
- Human review is required before sharing generated deliverables.
- Packaging, signed installers, and automatic updates are not yet part of the beta.

## Documentation

- [Documentation index / 문서 목록](docs/README.md)

| Topic | English | Korean |
|---|---|---|
| User guide | [English](docs/USER_GUIDE_EN.md) | [한국어](docs/USER_GUIDE.md) |
| GUI design system | [English](docs/GUI_DESIGN_EN.md) | [한국어](docs/GUI_DESIGN.md) |
| Secure projects and threat model | [English](docs/SECURE_PROJECTS_EN.md) | [한국어](docs/SECURE_PROJECTS.md) |
| Procedure and retest model | [English](docs/PROCEDURES_EN.md) | [한국어](docs/PROCEDURES.md) |
| Localization | [English](docs/LOCALIZATION_EN.md) | [한국어](docs/LOCALIZATION.md) |
| Development guide | [English](docs/DEVELOPMENT_EN.md) | [한국어](docs/DEVELOPMENT.md) |

- [Architecture](DESIGN.md)
- [Changelog](CHANGELOG.md)

## Development

```powershell
python -m unittest discover -s tests -v
python -m compileall -q webpentestkit tests examples tools
python .\examples\create_sample.py --force
python .\tools\capture_readme_screenshots.py
python .\otter.py validate --project .\examples\generated\acme-shop\project
```

The GUI uses the same service layer as the CLI. Views do not write JSON, SQLite,
or evidence files directly. See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting
a change.

## Community

- Use GitHub Issues for reproducible bugs and focused feature requests.
- Use fictional data in public issues and pull requests.
- Include tests for behavior changes.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Otter is released under the [MIT License](LICENSE).

---

Use Otter only on systems you own or are explicitly authorized to assess.
