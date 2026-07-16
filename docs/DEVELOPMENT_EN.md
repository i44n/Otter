# Otter development guide

**English** | [한국어](DEVELOPMENT.md)

## Architecture layers

```text
CLI / PySide6 GUI
        |
        v
ProjectService / KnowledgeService
        |
        +-- project_services/* -> feature-oriented project rules
        +-- ProjectRepository -> ProjectStorage -> folder or encrypted container
        +-- CredentialVaultService -> encrypted credential vault
        +-- KnowledgeRepository -> SQLite finding knowledge
        +-- reporting.py facade -> reporting_core/*
                                      +-- validation
                                      +-- shared report view
                                      +-- Markdown/CSV
                                      +-- PPT bundle
```

The GUI never reads or writes JSON or SQLite directly. It calls the service
layer through `GuiController`, and `ProjectService` owns all project creation
and mutation.

## Main modules

- `models.py`: immutable data and input models
- `errors.py`: structured `KitError` values with codes, fields, and paths
- `localization.py`: UI and error language packs, fallback, and stable keys
- `repository.py`: project file access and multi-JSON rollback
- `storage.py`: shared boundary for plaintext folders and encrypted storage
- `encrypted_project.py`: `.wpkproj` envelope encryption, locking, backup, and restore
- `credential_vault.py`: encrypted credential storage and lifecycle
- `security_crypto.py`: Argon2id parameter validation and recovery-key utilities
- `services.py`: stable `ProjectService` compatibility facade
- `project_services/`: lifecycle, security, targets, findings, evidence links,
  procedures, retests, evidence, archive, and reporting rules
- `reporting.py`: stable compatibility facade for report functions
- `reporting_core/`: validation, localized report text, shared report views,
  Markdown/CSV, and PPT bundle generation
- `locking.py`: reentrant project lock across threads and processes
- `schema_versions.py`: current project document schema checks
- `archives.py`: target, finding, and evidence archive and restore
- `knowledge.py`: versioned SQLite finding templates
- `gui/controller.py`: state boundary between Qt views and services
- `qt_gui/pages.py`, `qt_gui/dialogs.py`: stable GUI compatibility facades
- `qt_gui/page_views/`: dashboard, targets, findings, evidence, knowledge,
  reports, credentials, archive, and settings pages
- `qt_gui/dialog_views/`: project, target, finding, evidence, procedure/retest,
  knowledge, credential, and security dialogs
- `qt_gui/window_workflows/`: feature-specific user-action orchestration exposed
  by `MainWindow`
- `qt_gui/main_window.py`: application shell, navigation, responsive layout,
  and shared state and error handling
- `qt_gui/models.py`, `qt_gui/widgets.py`, `qt_gui/theme.py`: table models,
  shared widgets, and visual policy

### Import boundaries

- External code and tests use the stable facades in `services.py`,
  `reporting.py`, `qt_gui/pages.py`, and `qt_gui/dialogs.py`.
- Feature implementations do not import their own facade in reverse. They depend
  only on inner storage layers or modules in the same feature package.
- GUI workflows coordinate pages and dialogs but never mutate files, SQLite,
  or encrypted containers directly.
- Add new behavior to the corresponding feature module, not to a large facade.

See [LOCALIZATION_EN.md](LOCALIZATION_EN.md) for language-pack format and the
separation between UI and report languages.

## Storage rules

Individual text and JSON files are completed in a temporary file in the same
directory and then replaced with `os.replace()`. Multi-JSON changes retain the
previous contents and restore the entire set when any write fails.

Project mutations and report generation use `.otter.lock`. The lock is
reentrant on the same thread and reports `PROJECT_LOCK_TIMEOUT` when another
thread or process holds it.

## Schema changes

When the project JSON structure changes, update `CURRENT_SCHEMA_VERSION`,
`schemas/*.schema.json`, generation code, and tests together. Development data
currently supports only the current version; older and unknown future versions
are rejected without modification. Add explicit migrations when compatibility
with real user data becomes necessary.

Changes to the knowledge database require an updated
`KNOWLEDGE_SCHEMA_VERSION` and a separate database migration. Normal library
edits update the current record in place, while findings already applied to a
project retain a copied snapshot. Version tables remain for compatibility with
existing import and export bundles.

## Knowledge database boundary

SQLite stores only template IDs and versions, titles, descriptions, impact,
remediation, CWE, tags, references, and review metadata. Do not add customer
names, target URLs, actual findings, HTTP evidence, credentials, or personal
data.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m compileall -q webpentestkit tests examples tools
python examples\create_sample.py --force
python otter.py validate --project examples\generated\acme-shop\project
```

## Windows packaging

`pysidedeploy.spec` packages `desktop.py` as a single executable and includes
the configuration, schemas, and templates required to create and validate a
project.

```powershell
python -m pip install -r requirements.txt
pyside6-deploy -c pysidedeploy.spec
```

Build output is written to `dist/`. Before release, use a clean Windows
environment to test new project creation, encrypted-copy reopening, vault
creation and unlocking, backup restore, and report generation. Build macOS
packages on a macOS host and repeat the same smoke tests. `cryptography`
provides statically linked wheels for Windows and macOS, but verify Argon2id and
AES-GCM in the final executable.

New service behavior needs tests for the success path, validation errors,
write-failure rollback, archive and restore, and preservation of unknown
extension fields.

## GUI development rules

- Do not run long file, database, or reporting work on the Qt event thread.
- Validation, reporting, and export use `TaskManager` and `QThreadPool`.
- Dialogs display the `code` and `field` from structured errors.
- Do not mutate the project until the user saves the complete input.
- Findings and evidence use archive actions instead of direct deletion.
- Follow [GUI_DESIGN_EN.md](GUI_DESIGN_EN.md) and `qt_gui/theme.py` for color,
  spacing, and widget styling.
