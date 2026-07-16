# Credential vault and encrypted project security design

**English** | [한국어](SECURE_PROJECTS.md)

## Protection goals

The credential vault and encrypted project protect the confidentiality and
integrity of customer information, assessment credentials, and evidence when a
locked laptop, removable drive, backup file, or project folder is lost or
disclosed.

These features do not defend against:

- malware, keyloggers, or memory dumps while a project is open;
- secret values displayed or copied to the clipboard by the user;
- plaintext reports, PPT material, or exported evidence copies; or
- an attacker with operating-system administrator privileges.

Full-disk encryption, screen locking, approved backup storage, and least
privilege remain necessary.

## Storage boundaries

- The finding knowledge database never stores customer credentials or secrets.
- Credential data in `secrets/credentials.vault` is always authenticated and
  encrypted, even in a plaintext project.
- A future credential association in `finding.json` stores only a reference
  such as `ACC-001`; it never copies usernames, passwords, tokens, or private
  keys.
- Reports, PPT exports, validation output, and error messages never expose
  secret values.

## Credential vault format v2

The vault has a random 256-bit data key and encrypts the complete credential
JSON payload with AES-256-GCM. A user password derives a 256-bit key-encryption
key with Argon2id and wraps only the data key. A separate random 256-bit
recovery-key slot wraps the same data key.

The public header stores only the format version, random container ID, KDF salt
and cost parameters, wrapped data key, payload nonce, and ciphertext. Credential
IDs, targets, usernames, and even the number of records remain inside the
encrypted payload.

The v2 payload also stores a monotonically increasing `nextCredentialNumber`.
Permanently deleting an archived credential never reissues an `ACC-###` ID.
When an existing v1 vault is unlocked, the next number is derived from the
largest current ID; the next mutation saves a v2 payload.

Archived credentials cannot be revealed, edited, or validated. Restore returns
them to their pre-archive status. Permanent deletion is allowed only for an
archived credential while the vault is unlocked.

Default Argon2id parameters are 64 MiB of memory, three iterations, parallelism
four, and a 16-byte salt. KDF costs loaded from a file are checked against
application limits before use to prevent resource-exhaustion attacks.

Every AES-GCM operation uses a new 96-bit nonce and authenticates the container
ID, slot ID, and format version as additional data. Incorrect passwords or
modified headers and ciphertext never return plaintext.

## Lifecycle

- Vault creation displays the recovery key once and requires confirmation that
  it was stored separately.
- Password changes rewrap the data key instead of re-encrypting all data.
- Saves complete a temporary file in the same directory and publish it with
  `os.replace()`.
- An older concurrently open session detects a file-fingerprint conflict and
  refuses to overwrite newer data.
- Locking releases key buffers and references to the decrypted payload.

Python and the operating system cannot guarantee immediate and complete erasure
of every string or memory copy. Auto-lock reduces exposure time but does not
replace secure memory or full-disk encryption.

## Encrypted project format v1

Under the `ProjectStorage` boundary, existing folder storage and `.wpkproj`
encrypted storage use the same `ProjectService`. A random 256-bit project data
key is wrapped in an Argon2id password slot and a separate 256-bit recovery-key
slot. The complete project archive is authenticated and encrypted with
streaming AES-256-GCM. The public header contains no customer name, project
name, target, or filename.

The internal archive is an uncompressed ZIP. Before extraction, Otter checks
file count, per-file and total size, duplicates and case collisions, absolute
and parent paths, and symbolic links. Encrypting a source folder also rejects
symbolic links and paths that point outside the project.

Mutations complete and synchronize a candidate file beside the encrypted
container, then publish it with `os.replace()`. A sidecar lock is held for the
entire session, and file-size and modification-time conflicts prevent
overwriting a container opened by another process. Backups are also copied to a
temporary file and published only after their SHA-256 digest matches.

## Project and vault binding

HKDF-SHA256 derives a vault-binding key from the encrypted project data key.
The vault data key is wrapped once more with this binding key, so changing the
project password does not require re-encrypting vault data. A project containing
an existing plaintext-project vault must be opened once with the vault password
or recovery key before the project key slot can be added.

## Locking and temporary workspaces

To retain compatibility with path-based services, an unlocked project decrypts
the complete working tree into an OS temporary directory with restricted
permissions. Mutations reseal immediately. Normal locking, application exit, or
the 15-minute idle auto-lock deletes the workspace and overwrites key buffers.

Complete erasure of temporary files, swap or page files, file-system journals,
and memory copies after a forced process termination cannot be guaranteed. This
format therefore does not replace BitLocker or FileVault, OS screen locking, or
EDR. Plaintext and report exports must also remain in approved storage.

## Implementation references

- Password-based key derivation: [RFC 9106 Argon2](https://www.rfc-editor.org/rfc/rfc9106)
- Authenticated encryption and Argon2id API: [cryptography documentation](https://cryptography.io/en/latest/)
- Desktop packaging: [Qt for Python pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)
