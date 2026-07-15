# Contributing to Otter

Thank you for helping improve Otter. Contributions should keep the application
safe for sensitive assessment data, predictable to operate, and easy to review.

## Before you start

- Search existing issues before opening a new one.
- Use an issue template for bugs and feature proposals.
- Discuss large data-model, encryption, or UI architecture changes before
  implementation.
- Never attach real customer data, credentials, targets, or unredacted evidence.
- Report security vulnerabilities privately as described in `SECURITY.md`.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\otter.py gui
```

Python 3.10+ is supported. Set `QT_QPA_PLATFORM=offscreen` when running Qt tests
without a display server.

## Architecture rules

- GUI code calls `GuiController`; it does not directly mutate JSON, SQLite, or
  evidence files.
- Project writes go through the repository/service boundary and remain atomic.
- Changes that touch multiple project records need rollback tests.
- Secrets must not appear in logs, exceptions, reports, screenshots, fixtures,
  or exported bundles.
- Generated reports and PPT bundles are outputs, not source records.
- User-facing changes must remain usable in both light and dark themes.

More detail is available in `docs/DEVELOPMENT.md` and `DESIGN.md`.

## Tests

Run before submitting a pull request:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q webpentestkit tests examples
python .\examples\create_sample.py --force
python .\otter.py validate --project .\examples\generated\acme-shop\project
```

Add tests for success, validation failure, persistence rollback, and relevant
archive/restore behavior. GUI work should include an offscreen interaction test
and a light/dark rendering check when visual behavior changes.

## Pull requests

1. Keep each pull request focused on one coherent change.
2. Explain the user problem and the chosen approach.
3. Link related issues and note security or data-format implications.
4. Include tests and update documentation or samples when behavior changes.
5. Confirm that fixtures and screenshots contain fictional data only.

Maintainers may ask for a change to be split when it mixes unrelated concerns.
By contributing, you agree that your contribution is licensed under the MIT
License used by this repository.
