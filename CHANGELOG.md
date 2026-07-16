# Changelog

This file records public Otter releases. Internal pre-public development numbers
were consolidated into the first beta because no release tags were published.

## Unreleased

## 0.1.0b1 - 2026-07-16

First public beta.

### Assessment workflow

- Added structured targets, findings, affected requests, technical analysis,
  reproduction procedures, and finding-level retest history.
- Added searchable full-width finding and evidence tables with dedicated detail
  views, keyboard return behavior, and linked-evidence navigation.
- Added evidence assets with independent disclosure classification and explicit
  links to finding, technical, procedure, and retest scopes.
- Added archive, restore, and confirmed permanent deletion for project records.

### Knowledge and reporting

- Added a versioned SQLite finding library with review metadata, atomic import and
  export, in-place editing, archive, restore, deletion, and finding creation.
- Added categorized validation results with English and Korean output.
- Added Markdown and CSV reports plus a PPT-ready bundle containing `slides.json`,
  SVG charts, structured finding content, and curated evidence.
- Added report settings, output tracking, and background validation/export jobs.

### Security

- Added AES-256-GCM encrypted `.wpkproj` containers with Argon2id password
  derivation, recovery keys, password rotation, backups, tamper detection, and
  atomic resealing.
- Added a separately encrypted credential vault, idle locking, clipboard clearing,
  and archive-aware credential handling.
- Added path traversal, malicious archive, KDF resource, concurrent modification,
  and partial-write defenses.
- Added evidence secret checks and report-ready disclosure enforcement.

### Desktop and localization

- Added a PySide6 desktop interface with English as the default language, a Korean
  language pack, light/dark themes, screen-aware sizing, and hierarchical navigation.
- Added dashboards, editors, previews, filters, detail views, project protection,
  and validation/report screens.
- Added a fictional ACME sample and reproducible English README screenshots.

### Engineering

- Unified GUI and CLI behavior behind `ProjectService` and transactional repository
  boundaries.
- Fixed the active project document contract at internal schema version 3 for the
  beta; pre-beta migrations are intentionally unsupported.
- Added cross-platform CI, offscreen GUI tests, localization audits, encrypted
  storage tests, rollback tests, and end-to-end workflow coverage.
