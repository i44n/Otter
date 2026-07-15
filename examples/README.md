# End-to-end sample

`create_sample.py` uses the public Python API to create a fictional assessment with:

- two web targets;
- one confirmed finding and one passed retest;
- redacted report evidence and separate sensitive raw evidence;
- validation, CSV/Markdown reports, SVG charts, and a PPT-ready `slides.json` bundle.
- a versioned SQLite vulnerability knowledge database and template provenance snapshots.

From the repository root, run:

```powershell
python .\examples\create_sample.py
```

The generated files are written to `examples/generated/acme-shop/`:

```text
acme-shop/
|-- project/       # Canonical assessment records and generated reports
|-- knowledge.db   # Reusable non-customer vulnerability knowledge
`-- ppt-export/    # Portable bundle for a presentation renderer
```

To safely recreate only this known sample output:

```powershell
python .\examples\create_sample.py --force
```
