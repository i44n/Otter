# GUI design system

**English** | [한국어](GUI_DESIGN.md)

The desktop UI uses PySide6 and keeps all project and knowledge persistence
behind `GuiController`. Views must not read or write JSON, SQLite, or evidence
files directly.

## Information architecture

The main window has a persistent project header, a left navigation rail, and a
single page workspace. The primary workflow is:

1. Open or create a project.
2. Review project health on the dashboard.
3. Register targets before recording findings and evidence.
4. Filter the full-width findings table and open one in the same page stack.
5. Read its impact, remediation, technical details, procedure, retest timeline,
   and evidence state in a full-width detail view, then return without losing
   list filters, sorting, selection, or scroll context.
6. Create, edit, retest, or archive it without losing list context.

Navigation is grouped by workspace, assessment resources, output, and
management. Targets are a first-class workspace page rather than a Settings tab.
Group labels use a compact tinted Level 1 treatment; clickable Level 2 items use
larger indented text and reserve the primary background for the active page.

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
- Evidence classification controls contain asset properties only. Finding,
  technical-detail, procedure, and retest associations live in a separate
  usage section with per-link caption and placement controls.
- The evidence workspace uses a sortable, searchable full-width table and a
  full-width detail view with bounded image or text preview. It must not use a
  finding combo box that visually resembles an evidence classification field;
  finding selection appears only when creating or dropping an asset globally.
- Finding and evidence pages use list-to-detail page stacks rather than narrow
  master-detail splitters. Escape and Alt+Left return to the preserved list.
- Evidence selectors inside finding, procedure, and retest editors stage link
  caption and placement changes until the parent editor is saved.
- Minimum supported logical viewport is 1024 by 600. Below 1280 pixels wide the
  shell uses compact navigation and top-bar labels while preserving every action.
- Hide low-priority table columns in compact mode instead of shrinking primary
  content below its usable width.

## Qt application boundary

The Tkinter implementation was removed after the Qt UI reached controller-level
parity, passed offscreen smoke tests and a real Windows rendering smoke test,
and preserved the CLI and project file regression suite. The CLI launches
`webpentestkit.qt_gui` directly, while `webpentestkit.gui` contains only the
toolkit-independent `GuiController` service boundary.
