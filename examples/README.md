# W-library manual test sample

Otter keeps one generated sample for hands-on testing:

`examples/generated/w-library-e2e/`

The sample copies the current Otter vulnerability knowledge database and creates
project findings from the approved `W-number` records. The Git version stops at
the project, procedure, and evidence stage; it does not include a PPT template or
generated presentation. The project contains:

- six library-linked findings: `W-05`, `W-08`, `W-11`, `W-16`, `W-24`, `W-28`;
- Confirmed, Accepted, and Resolved finding states;
- 1, 2, 3, 4, 5, and 7-step procedure cases;
- one- and two-screenshot procedure cases; every procedure and result includes evidence
  attached to one logical procedure;
- one final-result screenshot for every finding in this sample;
- one passed retest with its own retest evidence;
- enough varied targets, findings, procedures, and evidence to test an arbitrary
  company template manually in Otter.

All systems, accounts, orders, tokens, and responses are fictional and sanitized.

## Create or recreate the sample

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe .\examples\create_presentation_e2e_sample.py --force
```

The generator uses these defaults:

- knowledge DB: `%LOCALAPPDATA%\Otter\knowledge.db`;
- destination: `examples/generated/w-library-e2e/`.

Override any path when needed:

```powershell
.\.venv\Scripts\python.exe .\examples\create_presentation_e2e_sample.py `
  --knowledge-db D:\path\knowledge.db `
  --destination D:\path\manual-sample `
  --force
```

Generated projects and evidence PNGs remain under `examples/generated/` and are
never committed. Template registration, slide mapping, draft review, and PPT
generation are intentionally performed manually after this sample is opened.

The evidence renderer produces synthetic proxy request/response captures,
browser plus DevTools captures, decoded identity context, and correlated server
logs. It does not call external hosts or contain real credentials or customer
data.

## Open in Otter

```powershell
.\.venv\Scripts\python.exe .\examples\open_sample_gui.py
```

After generation, follow
`examples/generated/w-library-e2e/MANUAL-TEST-GUIDE.md` for the complete
library, procedure/evidence, template registration, draft review, autosave, and
final PowerPoint checklist.
