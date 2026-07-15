# GUI design system

The desktop UI uses PySide6 and keeps all project and knowledge persistence
behind `GuiController`. Views must not read or write JSON, SQLite, or evidence
files directly.

## Information architecture

The main window has a persistent project header, a left navigation rail, and a
single page workspace. The primary workflow is:

1. Open or create a project.
2. Review project health on the dashboard.
3. Register targets before recording findings and evidence.
4. Filter findings and select one.
5. Read its impact, remediation, technical details, procedure, retest timeline,
   and evidence state in the detail panel.
6. Create, edit, retest, or archive it without losing list context.

Navigation is grouped by workspace, assessment resources, output, and
management. Targets are a first-class workspace page rather than a Settings tab.

## Visual tokens

- Spacing: 4, 8, 12, 16, 24, and 32 px.
- Radius: 8 px controls, 12 px cards, 16 px large surfaces.
- Light background: `#F4F6F8`; surface: `#FFFFFF`; border: `#DDE2E8`.
- Primary: `#2563EB`; text: `#172033`; muted text: `#667085`.
- Critical: `#7F1D1D`; High: `#DC2626`; Medium: `#D97706`;
  Low: `#2563EB`; Informational: `#667085`.
- Windows UI font fallback: `Pretendard`, `Segoe UI`, sans-serif.

Use object names and dynamic properties from `qt_gui.theme`; do not add
one-off inline styles in page code unless the value is data-dependent, such as
a severity badge.

## Interaction rules

- One primary action per page.
- Destructive actions require confirmation or an archive reason.
- Validation errors are shown in context and preserve entered values.
- Successful operations use a temporary toast; background operations use the
  shared busy indicator.
- Tables support keyboard selection, sorting, text search, and filters.
- Empty states explain the next useful action.
- Minimum supported viewport is 1280 by 720 at Windows display scaling.

## Migration result

The Tkinter implementation was removed after the Qt UI reached controller-level
parity, passed offscreen smoke tests and a real Windows rendering smoke test,
and preserved the CLI and project file regression suite. `webpentestkit.gui`
remains as a compatibility launch namespace and delegates to `qt_gui`.
