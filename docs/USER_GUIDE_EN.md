# Otter User Guide

**English** | [한국어](USER_GUIDE.md)

> [!WARNING]
> Otter `0.1.0b1` is the first public beta. Keep separate backups of important
> projects and review every generated deliverable before sending it to a customer.

Otter is a local-first desktop workspace for managing authorized web security assessments. Customer projects and evidence stay in the project folder. Only reusable, non-customer finding guidance is stored in a separate SQLite knowledge database.

Otter organizes assessment records and deliverables. It does not scan targets or run attacks.

## Install and launch

Otter requires Python 3.10 or newer. Use a virtual environment to keep its dependencies isolated.

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

After the dependencies are installed, launch Otter from the repository root with:

```powershell
python otter.py gui
```

You can open a project and select a knowledge database at launch:

```powershell
python otter.py gui `
  --project .\examples\generated\acme-shop\project `
  --knowledge-db .\my-knowledge.db
```

The default knowledge database is `%LOCALAPPDATA%\Otter\knowledge.db` on Windows and `~/.otter/knowledge.db` on macOS and other platforms.

## Understand the workspace

| Area | What it is for |
| --- | --- |
| Dashboard | Review finding counts, severity distribution, missing evidence, and recent changes |
| Assessment targets | Manage in-scope URLs, environments, and target status |
| Findings | Search and filter findings; manage details, procedures, retests, and linked evidence |
| Evidence | Review image, HTTP, and text assets together with every place each asset is used |
| Credentials and access | Store assessment accounts and secrets in an encrypted vault |
| Finding library | Maintain reusable finding drafts that are independent of customer projects |
| Validation and reports | Check data quality and generate Markdown, CSV, and presentation-ready bundles |
| Archive | Restore or permanently remove archived targets, findings, evidence, and credentials |
| Settings | Manage UI language, project metadata, report settings, and project protection |

The Findings and Evidence pages use searchable, sortable tables. Double-click a row to open its full detail view. **Back to list**, Esc, or Alt+Left returns to the previous table with its search, sort, selection, and scroll position preserved. You can also drag files onto the Evidence page.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O` | Open a plaintext project |
| `Ctrl+Shift+O` | Open an encrypted project |
| `Ctrl+Shift+N` | Add a finding |
| `Ctrl+K` | Focus finding search |
| `Ctrl+L` | Lock the open encrypted project |
| `Esc` or `Alt+Left` | Return from a detail view to its previous list |

### Change language and theme

Open **Settings**, select English or Korean as the UI language, save, and restart Otter. UI language and report language are separate settings; choose the report language in the project's report settings. The top-bar dark-mode toggle is also remembered between launches.

## Explore the fictional sample

Generate the ACME sample to explore the complete workflow without customer data. It uses only `example.test` hosts and fictional, redacted evidence.

```powershell
python .\examples\create_sample.py --force
python .\examples\open_sample_gui.py
```

The sample output is written below `examples/generated/acme-shop/` and is ignored by Git.

## Recommended assessment workflow

1. Create a project and enter its project ID, name, and customer.
2. Add every in-scope application on **Assessment targets**.
3. Create findings directly or start from a reviewed item in the **Finding library**.
4. Tailor severity, affected URL, role, business impact, and remediation to the assessed system.
5. Add reproducible steps and technical root-cause analysis.
6. Register evidence once, classify its disclosure status, and link it to every place where it is used.
7. Record remediation checks as finding-level retests and attach supporting evidence.
8. Resolve validation errors, review warnings, and generate the required deliverables.

## Create and manage a project

Use **New project** in the top bar, select an empty folder, and enter a stable project ID and display name. Customer data is stored inside that project; the reusable finding library remains separate.

Add a target before creating findings. A target records an ID such as `WEB-01`, a name, base URL, environment, and workflow status. Update its status from the target edit dialog as the assessment progresses.

Otter writes auditable JSON and evidence files under the project root. Do not rename generated target or finding directories manually while the project is open.

## Findings

The Findings page provides full-width search and filters. Double-click a row to view the complete finding, including its affected request, summary, impact, remediation, technical details, reproduction procedure, retest history, and linked evidence.

When creating or editing a finding:

1. Select its target and enter the title, severity, category, and status.
2. Record the affected URL, method, parameter, role, tester, and discovery date where applicable.
3. Write a concise summary, concrete impact, and actionable remediation.
4. Use **Technical details** for root cause and analysis. Keep raw HTTP request and response text in linked evidence instead of duplicating it here.
5. Use **Reproduction procedure** for prerequisites, ordered actions, expected results, and observed results.
6. Review whether the finding should be included in deliverables, then save the complete editor.

New evidence created inside the finding editor remains temporary until the parent finding is saved. Cancelling the editor does not leave orphaned evidence in the project.

## Finding library

A library item is a reusable draft containing a summary, default impact, remediation, severity, CWE references, tags, and review metadata. Applying one copies its current text into the project finding and records template provenance:

```json
"template": {
  "id": "WPK-ACCESS-001",
  "version": 1
}
```

Project findings are independent copies. Editing, archiving, or deleting the library item later does not rewrite findings already created from it.

- **Edit** updates the current library item instead of creating a duplicate current version.
- **Create finding from this template** opens a new project finding populated with the draft.
- **Archive** hides the item from the active list; use the Archived filter to restore it.
- **Delete** permanently removes the item after you re-enter its template ID.

Use **Export database** to create a JSON transfer bundle containing reusable guidance only. It does not include customer names, target URLs, project findings, credentials, or evidence. **Import database** merges a trusted bundle transactionally: identical versions are kept, conflicting content aborts the import, and the original database remains unchanged on failure.

## Evidence and evidence links

Evidence is an independent asset. Register a file once, then link it to one or more scopes without copying it:

- the finding body;
- technical details;
- a reproduction step;
- a finding-level retest.

The evidence editor contains only asset properties such as file, title, type, disclosure status, and derivation. Usage captions and placement belong to the separate **Usages and linked items** area.

Disclosure status controls delivery:

| Status | Intended use | Exported to reports |
| --- | --- | --- |
| `internal` | Working notes and internal references | No |
| `report-ready` | Reviewed and redacted customer deliverable | Yes, when linked |
| `sensitive` | Raw or sensitive source material | No |

Changing status does not move the underlying file. When keeping raw and sanitized copies, set the sanitized item's `derivedFrom` relationship to the original evidence ID.

For HTTP traffic, use `http-exchange`, `http-request`, or `http-response` evidence. Link it to Technical details and let the common report view render it instead of pasting the same packet text into multiple fields.

Archiving evidence removes its active file metadata and all usage links together. Restoring it returns links only when their referenced procedure step or retest still exists.

## Reproduction procedures and retests

A procedure describes how the original issue was reproduced. Each step has a stable `STEP-###` ID, title, action, expected result, and observed result. Reordering steps does not change their IDs.

A retest is a finding-level verification event, not a procedure-step result. Use **Add retest record** from the finding detail view to record the date, tester, overall result, applied fix, verification notes, and supporting evidence.

Retest results are `Pending`, `Passed`, `Failed`, or `Partial`. Recording a retest does not automatically change the finding's workflow status; update the finding status separately after review.

## Credentials and access vault

Use **Credentials and access** to store assessment passwords, API tokens, session cookies, client certificates, and SSH keys. Credential IDs are allocated as `ACC-001`, `ACC-002`, and so on.

- The complete vault payload, including usernames and metadata, is encrypted.
- Secret values are excluded from reports, presentation exports, validation output, and error messages.
- A copied secret is cleared from the clipboard after 30 seconds if the clipboard still contains that value.
- The recovery key is shown once when the vault is created. Store it offline and separately from the project.
- A plaintext project still uses an encrypted credential vault.
- The vault automatically locks after 15 minutes of inactivity.
- In an encrypted project, the vault can be bound to the project key and unlock with the project.

If a pre-existing standalone vault is moved into an encrypted project, unlock it once with its old vault password or recovery key. Otter then binds it to the current encrypted project.

## Encrypted projects and backups

From **Settings**, create an encrypted `.wpkproj` copy of a plaintext project. This operation does not delete or modify the original folder. Save the recovery key separately, verify the new container opens, and then handle the original according to your organization's retention policy.

Open an encrypted project from the top-bar project menu using its password or recovery key. Changes are resealed immediately. The project locks after 15 minutes of inactivity or when you press `Ctrl+L`, and Otter cleans up its temporary workspace during a normal lock or exit.

An encrypted backup reseals the current state and creates a new `.wpkproj` only after verifying its SHA-256 copy integrity. Restore a backup to a new path, then open the restored file with the existing password or recovery key to verify it.

While an encrypted project is unlocked, a plaintext working tree exists in an application-specific OS temporary directory. Forced termination, page files, privileged malware, and plaintext report exports are outside the container's protection boundary. Continue using BitLocker or FileVault, OS screen lock, endpoint protection, and an approved backup location.

## Archive, restore, and delete

Use archive instead of immediate deletion during active work. Archiving a target also hides the findings and evidence below it. The Archive page can restore an item to its original location and status.

Permanent deletion requires re-entering the item ID and cannot be undone. Create and verify an encrypted backup first when the selected target or finding may contain child evidence. Archived credentials are visible only while the vault is unlocked, and permanently deleted credential IDs are never reused.

## Validation and reports

Open **Validation and reports** before delivery.

- Errors stop report and presentation-bundle generation.
- Warnings do not stop generation, but they require review before delivery.
- Validation, report generation, and presentation export run in the background; Otter does not run two such jobs at the same time.
- Only linked `report-ready` evidence is emitted to deliverables.

Otter currently creates final and summary Markdown reports, target and finding summaries, findings CSV, a localized validation report, and a presentation-ready folder with structured content, SVG charts, and curated evidence. The beta does not render a finished `.pptx` file.

The canonical sources are `finding.json` for finding text, `procedure.json` for reproduction steps, `retests.json` for retest history, and `evidence/evidence.json` plus `evidence/links.json` for evidence and its usages. Generated Markdown views should not be edited as source records.

## Back up your data

Back up each complete customer project folder and any organization-maintained SQLite knowledge database. A library JSON export is an interchange format for reusable guidance; it is not a complete operational backup of the SQLite file.

Do not commit customer projects, real target URLs, credentials, tokens, or raw evidence to Git. Keep recovery keys offline and separate from their encrypted containers.

## Troubleshooting

- If Python reports `ModuleNotFoundError`, activate the virtual environment and rerun `python -m pip install -r requirements.txt`.
- If a project will not open, select the project root containing `project.json`.
- If you forget an encrypted-project password, use the recovery key saved at creation. The project cannot be recovered if both are lost.
- If report generation stops, resolve errors on **Validation and reports** first.
- If evidence is missing from a report, confirm that it is linked to the intended scope and classified as `report-ready`.
- Never attach customer data or raw evidence to a public issue. Follow [SECURITY.md](../SECURITY.md) for private vulnerability reporting.

For deeper implementation and threat-model details, see [Secure projects](SECURE_PROJECTS.md) and [Procedures and evidence](PROCEDURES.md).
