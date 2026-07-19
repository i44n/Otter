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
| Dashboard | Review finding counts, severity distribution, deliverable findings without evidence, and recent changes |
| Assessment targets | Manage in-scope URLs, environments, and target status |
| Findings | Search and filter findings; manage details, procedures, retests, and linked evidence |
| Evidence | Review image, HTTP, and text assets together with every place each asset is used |
| Credentials and access | Store assessment accounts and secrets in an encrypted vault |
| Shared libraries > Finding library | Maintain reusable finding information shared by every project |
| Deliverables | Review readiness, generate Markdown/CSV data, and generate or review the project PowerPoint deck |
| Shared libraries > PowerPoint templates | Manage company PowerPoint content mappings and slide order independently from projects |
| Archive | Restore or permanently remove archived targets, findings, evidence, and credentials |
| Settings | Manage UI language, project metadata, and project protection |

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

Open **Settings**, select English or Korean as the UI language, save, and restart Otter. UI language and generated-copy language are separate settings; choose generated-copy language under **Deliverables > Details**. The top-bar dark-mode toggle is also remembered between launches.

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
5. Add reproducible steps and technical root-cause analysis. Result evidence on
   **Result and deliverables** belongs to the finding's final observed result, not to the
   last procedure step.
6. Register evidence once, classify its disclosure status, and link it to each
   result, technical detail, procedure step, or retest where it is used. Selecting
   a row shows its linked location. Choose show at linked location, evidence
   appendix, or attachment-only plus a caption and order for each link. The same
   evidence can have different settings at different linked locations.
7. Record remediation checks as finding-level retests and attach supporting evidence.
8. Resolve validation errors, review warnings, and generate the required deliverables.
9. Prepare a reusable company template in **Shared libraries > PowerPoint templates**.
   Under project **Deliverables > Generate and review PowerPoint**, select the
   registered template, review the deck plan and evidence placement, and generate
   the final `.pptx`.

## Generate PowerPoint from a company template

Template setup and project output are separate. In **PowerPoint templates**, complete
the guided sequence `1 Import PPTX → 2 Map content → 3 Slide order`.
That stepper is the only workspace navigation; a duplicate tab bar is not shown. The separate status
badge—In progress, Review needed, Save needed, or Ready to use—shows readiness.
Completed steps remain green, while the step currently being viewed has a separate blue fill.
In the open project's **Deliverables > Generate and review PowerPoint**, use
`Select template → Create PowerPoint draft → Adjust only what is needed → Generate PowerPoint`.

1. Select the company PPTX under **Template management**. Otter analyzes the file
   immediately and looks for an existing content mapping for the same template.
   If one exists, its first slide type appears automatically. Use **Start new
   content mapping** only when no mapping exists.
2. Under **Content mapping**, connect each source-slide area to a content field
   such as title, impact, procedure action, or evidence image. Slide types and
   content fields come from Otter's fixed lists; users do not create reserved words.
   The text or image data type follows the selected field automatically. Mapping
   **Finding number** or **Step number** exposes safe presets for decimal, padded decimal, Korean step
   suffix, `STEP N`, `STEP NN`, circled, and Korean alphabet sequences, plus a
   custom format containing exactly one `{number}` token. The preview updates
   immediately. Finding- and step-number formats are stored independently, while
   the step-number format propagates to repeated procedure regions in the slide type.
   Drag the horizontal divider between **Slide content regions** and **Selected
   region content mapping** to change their heights. Otter remembers the divider
   position, and the default shows at least six content rows.
3. An **Assessment procedure** slide can contain 1 to 12 procedure regions. Procedure
   evidence is optional and a step may link multiple items. PowerPoint output uses
   only report-ready images placed inline; map only as many evidence-image frames
   as the page should visibly hold. Model the
   finding result as a separate slide type; duplicate a content mapping when the
   procedure and result intentionally share the same physical design.
4. Text mapping estimates a numeric capacity from the shape geometry and font.
   Short/regular/long categories stay out of the default workflow; the draft step
   checks actual strings and image capacity again. Internal page-type conditions
   remain under **Advanced mapping settings**.
5. **Slide order** starts with a recommended sequence. Open **Edit order** and change document, finding,
   and appendix slide types only when the company format requires it, then choose
   **Save template** to make it reusable in every project.
6. In **Deliverables > Generate and review PowerPoint**, select a template and
   review the **Output scope** summary. Choose **Change targets** to select target
   membership with checkboxes; selecting every target normalizes the scope back to
   all targets. Only included targets' findings, evidence, and summaries enter the deck. Changing the
   scope requires a new draft, which prevents content from an earlier scope from
   leaking into the final file. Then choose **Create PowerPoint draft**. Otter checks procedure text and eligible
   evidence images against each region's capacity, then packs consecutive
   procedures. Seven steps are not forced into `2·2·2·1`; another template or data
   set may produce `2·1·1·2·1`.
7. The slide list and **Selected slide** summary appear only after a draft exists.
   Open **Fine-tune** only for a slide that should differ from automatic placement.
   Alternative layouts appear only when available, image controls only when evidence
   exists, and crop position only for Fill area. Changes save automatically.
8. Review the preflight summary and generate the PowerPoint file. A render manifest
   is written next to the final `.pptx`. Use **Import another PowerPoint layout** or
   **Export a PowerPoint layout copy** when continuing another layout or sharing a copy.
   Selecting a procedure slide exposes contextual actions on the right to split its
   procedures into individual slides or merge it with the next procedure slide.

You do not map every evidence image to a final slide manually. Link zero or more
items to the relevant procedure step and link result evidence to the finding result once.
The planner selects a capacity-matched slide type, creates continuation pages only
when needed, and places the independent result after all procedure steps. Reusing
an asset in several locations does not duplicate its source file.

Use `Ctrl` or `Shift` plus click to select multiple rows in management tables.
Targets, findings, evidence, credentials, vulnerability templates, and archive
entries expose a selected count and batch actions. The shared vulnerability library
does not use the project archive: delete one or more selected templates with one
confirmation. Findings already copied into projects are unchanged.
The finding library and credential tables do not auto-select the first row. Because
evidence IDs restart at `EVD-001` for each finding, the all-evidence table displays
`finding ID / evidence ID` as its unambiguous reference.

If the linked template changes, its library status becomes **Template changed**.
**Recover mappings for changed template** compares previous shape fingerprints
with the new slide geometry and classifies each mapping as automatic, review, or
missing. Rendering remains blocked until review and missing items are resolved
in **Content mapping** and the template is saved.

Profile v1/v2/v3/v4 files are upgraded to v5 automatically. Legacy `finding-detail`
becomes `finding-overview`, while `*-evidence` roles become continuation variants
of their semantic role. Unsupported legacy values are quarantined for review
instead of being discarded.

Finding- and step-number formatters are optional v5 binding properties, so existing
v5 profiles load unchanged. Legacy `findingNumber` and `stepNumber` bindings
without a formatter keep the original plain numeric output.

The same engine is available from the CLI:

```powershell
python otter.py presentation analyze-template --project PROJECT --template TEMPLATE.pptx --output ANALYSIS.json
python otter.py presentation create-profile --project PROJECT --template TEMPLATE.pptx --output PROFILE.json
python otter.py presentation plan --project PROJECT --profile PROFILE.json --output PLAN.json
python otter.py presentation render --project PROJECT --template TEMPLATE.pptx --profile PROFILE.json --plan PLAN.json --output REPORT.pptx
```

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

Project findings are independent copies. Editing or deleting the library item later does not rewrite findings already created from it.

- **Edit** updates the current library item instead of creating a duplicate current version.
- **Create finding from this template** opens a new project finding populated with the draft.
- **Delete** removes an item after one confirmation; multi-row selection supports the same action.
- Items archived by an older Otter version are restored to the active list during migration.
- Default templates are seeded only once, so deleting every item does not recreate them on restart.

Use **Export library** to create a JSON transfer bundle containing reusable guidance only. It does not include customer names, target URLs, project findings, credentials, or evidence. **Import library** merges a trusted bundle transactionally: identical versions are kept, conflicting content aborts the import, and the original database remains unchanged on failure. Legacy `archived` flags are normalized to active entries.

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

Otter creates final and summary Markdown reports, target and finding summaries,
findings CSV, a localized validation report, and the legacy presentation-ready
bundle. The global Template workspace can analyze a company PPTX and map source
shapes to semantic slots. The project Deliverables page customizes slide order
and evidence placement and renders a final `.pptx` with an auditable manifest.

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
