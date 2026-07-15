# Security policy

Otter stores sensitive assessment evidence and credentials. We welcome careful,
coordinated reports that help keep users and their data safe.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.7.x | Yes |
| Earlier development snapshots | No |

Until the project publishes a stable release line, security fixes are made on
the latest version only.

## Reporting a vulnerability

Please use **GitHub Private Vulnerability Reporting** from the repository's
Security tab. If that feature is unavailable, contact the repository owner
through a private channel listed on their GitHub profile.

Do not open a public issue, discussion, or pull request for an undisclosed
vulnerability.

Include only what is necessary:

- affected version and operating system;
- impact and realistic attack conditions;
- minimal reproduction steps or proof of concept;
- suggested mitigation, if known;
- whether the issue has been disclosed elsewhere.

Do not send real customer projects, credentials, recovery keys, raw evidence,
or other third-party data. Use a fictional project and redact secrets.

## What to expect

Maintainers aim to acknowledge a report within five business days, confirm
scope and severity, and coordinate a fix and disclosure timeline with the
reporter. Response time may vary because the project is community maintained.

Good-faith research that avoids privacy violations, data destruction, service
disruption, and unauthorized access will be treated respectfully. This policy
does not authorize testing against systems you do not own or have permission to
assess.

## Security boundaries

- Otter is not a scanner and does not authorize or execute attacks.
- Sensitive evidence cannot be selected for report output, but automatic secret
  detection is not complete and does not replace manual review.
- `.otter.lock` prevents concurrent writes; it is not an authentication or
  encryption mechanism.
- An unlocked encrypted project exists temporarily as plaintext in an
  application-controlled OS temporary directory.
- Full-disk encryption, OS access controls, secure backups, and offline recovery
  key storage remain the user's responsibility.

See `docs/SECURE_PROJECTS.md` for the encryption design and threat model.
