# Reproduction procedures and evidence

**English** | [한국어](PROCEDURES.md)

## Design principles

Reproduction procedures, retest history, evidence assets, and evidence usage
have different lifecycles and are stored separately.

- `procedure.json` records the steps performed by the tester and their order.
- `retests.json` records finding-level retest history and results.
- `evidence/evidence.json` records file assets, descriptions, disclosure
  classifications, and derived-original relationships.
- `evidence/links.json` records how an EVD is used in the finding body,
  technical details, a procedure step, or a retest.
- Procedure and retest JSON do not duplicate file paths or EVD lists.
- Export copies each evidence file only once.

## Using the GUI

1. Select an item on the Findings page and choose **Edit**.
2. Add prerequisites and steps on the **Reproduction procedure** tab.
3. Enter the step title, action, expected result, and observed result.
4. Select an existing EVD or choose **+ Register and link new evidence**.
5. Record the cause and analysis under **Technical details**, and link raw HTTP
   requests and responses as evidence.
6. Reorder steps with **Up** and **Down**, then save the complete editor.

You can also add evidence while drafting a new finding. New files remain staged
inside the edit session and are committed together with the finding, procedure,
and links only after the complete save succeeds. Canceling the editor or a
failed save leaves no staged evidence in the project.

Internal or sensitive evidence can be linked for work records, but only
`report-ready` evidence appears in deliverables. Validation warns about links
that will not appear in output.

## Storage structure

`procedure.json` stores only the procedure itself.

```json
{
  "schemaVersion": 3,
  "findingId": "WEB-01-001",
  "preconditions": "Two test accounts with different privileges are ready.",
  "nextStepNumber": 3,
  "steps": [
    {
      "id": "STEP-001",
      "order": 10,
      "title": "Sign in as a standard user",
      "action": "Sign in with account A.",
      "expectedResult": "Only account A's data is returned.",
      "observedResult": ""
    },
    {
      "id": "STEP-002",
      "order": 20,
      "title": "Change the object ID",
      "action": "Replace the object ID in the request with account B's value.",
      "expectedResult": "The request is rejected.",
      "observedResult": "Account B's data is returned."
    }
  ],
  "updatedAt": "2026-07-15T12:27:14+09:00"
}
```

Evidence usage is stored in `evidence/links.json`.

```json
{
  "schemaVersion": 3,
  "findingId": "WEB-01-001",
  "items": [
    {
      "evidenceId": "EVD-001",
      "scopeType": "procedure",
      "scopeId": "STEP-002",
      "caption": "Response containing account B's order data",
      "placement": "inline",
      "order": 10
    },
    {
      "evidenceId": "EVD-001",
      "scopeType": "technical",
      "scopeId": "",
      "caption": "HTTP exchange showing missing authorization",
      "placement": "inline",
      "order": 10
    }
  ]
}
```

`STEP-###` and `RT-###` IDs remain stable when entries are reordered, and
deleted numbers are not reused.

## Archive and export

Archiving evidence stores the file, asset metadata, and all Evidence Links
together. Restore reinstates only links whose procedure step or retest record
still exists.

Markdown reports and PPT bundles use the same Finding Report View.
`report-ready` evidence linked to the finding body, technical details,
procedures, and retests is selected by the same policy. HTTP text evidence is
rendered automatically in technical details. Evidence beyond the capacity of
one slide continues on additional slides, while each file is copied only once.

## Retest history

A retest is an independent history entry scoped to one finding. It records the
date, tester, overall result, applied fix, validation notes, and evidence. A
retest result does not automatically change the finding workflow status.

- Finding status: `Draft`, `Confirmed`, `FalsePositive`, `Accepted`, `Resolved`
- Retest result: `Pending`, `Passed`, `Failed`, `Partial`
- The latest result displayed in the UI is selected by date, update time, and
  ID, in that order.
