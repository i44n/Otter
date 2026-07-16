from __future__ import annotations

import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.common import write_json
from webpentestkit.credential_vault import (
    KDF_MEMORY_MAX_KIB,
    VAULT_RELATIVE_PATH,
    CredentialVaultService,
    _encrypt_payload,
)
from webpentestkit.errors import KitError
from webpentestkit.models import CredentialInput
from webpentestkit.services import ProjectService


PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another correct horse battery staple"


class CredentialVaultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        service = ProjectService.create_project(
            self.root / "project",
            "VAULT-TEST",
            "Credential Vault Test",
            "Sensitive Customer",
        )
        self.project = service.root
        service.create_target(
            "WEB-01",
            "Portal",
            "https://portal.example.test",
            "Staging",
        )
        service.close()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _credential(self, *, name: str = "Low privilege customer") -> CredentialInput:
        return CredentialInput(
            name=name,
            credential_type="password",
            target_ids=("WEB-01",),
            environment="Staging",
            role="Customer",
            username="customer.one@example.test",
            purpose="Horizontal authorization testing",
            scope="Portal only",
            owner="Customer security team",
            expires_at="2026-08-31",
            notes="Do not change profile data.",
            status="Active",
            mfa_enabled=True,
            secret_values={
                "password": "SuperSecret!234",
                "totpSecret": "JBSWY3DPEHPK3PXP",
            },
        )

    def test_create_manage_and_lock_vault_without_plaintext_leakage(self) -> None:
        recovery_key = CredentialVaultService.create(self.project, PASSWORD)
        self.assertTrue(recovery_key.startswith("WPK-RK1-"))
        vault_path = self.project / VAULT_RELATIVE_PATH
        self.assertTrue(vault_path.is_file())

        vault = CredentialVaultService.unlock_with_password(self.project, PASSWORD)
        credential = vault.add_credential(self._credential())
        self.assertEqual(credential.id, "ACC-001")
        self.assertEqual(credential.target_ids, ("WEB-01",))
        self.assertEqual(credential.secret_keys, ("password", "totpSecret"))
        self.assertFalse(hasattr(credential, "secret_values"))
        self.assertEqual(
            vault.reveal_secrets(credential.id),
            {
                "password": "SuperSecret!234",
                "totpSecret": "JBSWY3DPEHPK3PXP",
            },
        )
        self.assertEqual(vault.mark_verified(credential.id).id, credential.id)

        file_text = vault_path.read_text(encoding="utf-8")
        for sensitive in (
            "Low privilege customer",
            "customer.one@example.test",
            "SuperSecret!234",
            "JBSWY3DPEHPK3PXP",
            "WEB-01",
        ):
            self.assertNotIn(sensitive, file_text)

        ProjectService.open(self.project).build_reports()
        generated_text = "\n".join(
            path.read_text(encoding="utf-8-sig", errors="ignore")
            for path in (self.project / "reports").rglob("*")
            if path.is_file()
        )
        self.assertNotIn("SuperSecret!234", generated_text)
        self.assertNotIn("customer.one@example.test", generated_text)

        archived = vault.archive_credential(credential.id, "Engagement account retired")
        self.assertEqual(archived.status, "Archived")
        self.assertEqual(archived.archived_reason, "Engagement account retired")
        self.assertEqual(vault.list_credentials(), [])
        self.assertEqual(len(vault.list_credentials(include_archived=True)), 1)
        with self.assertRaises(KitError) as archived_secret:
            vault.reveal_secrets(credential.id)
        self.assertEqual(archived_secret.exception.code, "CREDENTIAL_ARCHIVED")

        restored = vault.restore_credential(credential.id)
        self.assertEqual(restored.status, "Active")
        self.assertEqual(restored.archived_at, "")
        self.assertEqual(
            vault.reveal_secrets(credential.id)["password"],
            "SuperSecret!234",
        )
        vault.archive_credential(credential.id, "Permanent removal test")
        purged = vault.purge_credential(credential.id)
        self.assertEqual(purged.id, "ACC-001")
        self.assertEqual(vault.list_credentials(include_archived=True), [])
        replacement = vault.add_credential(self._credential(name="Replacement account"))
        self.assertEqual(replacement.id, "ACC-002")
        vault.lock()
        self.assertTrue(vault.is_locked)
        with self.assertRaises(KitError) as locked:
            vault.list_credentials()
        self.assertEqual(locked.exception.code, "VAULT_LOCKED")

    def test_outdated_payload_is_rejected(self) -> None:
        CredentialVaultService.create(self.project, PASSWORD)
        vault = CredentialVaultService.unlock_with_password(self.project, PASSWORD)
        first = vault.add_credential(self._credential())
        self.assertEqual(first.id, "ACC-001")

        outdated_payload = copy.deepcopy(vault._payload)
        outdated_payload["schemaVersion"] = 1
        outdated_payload.pop("nextCredentialNumber")
        outdated_envelope = copy.deepcopy(vault._envelope)
        outdated_envelope["payload"] = _encrypt_payload(
            outdated_payload,
            bytes(vault._data_key),
            str(outdated_envelope["containerId"]),
        )
        vault.lock()
        write_json(self.project / VAULT_RELATIVE_PATH, outdated_envelope)

        with self.assertRaises(KitError) as raised:
            CredentialVaultService.unlock_with_password(self.project, PASSWORD)
        self.assertEqual(raised.exception.code, "VAULT_CORRUPT")

    def test_project_archive_view_restores_and_purges_credentials(self) -> None:
        service = ProjectService.open(self.project)
        service.create_credential_vault(PASSWORD)
        first = service.add_credential(self._credential())
        with self.assertRaises(KitError) as active_purge:
            service.purge_credential(first.id)
        self.assertEqual(active_purge.exception.code, "CREDENTIAL_NOT_ARCHIVED")
        service.archive_credential(first.id, "No longer required")
        entries = service.list_archives()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].archive_id, "credential:ACC-001")
        self.assertEqual(entries[0].reason, "No longer required")

        restored = service.restore_archive(entries[0].archive_id)
        self.assertEqual(restored.entity_type, "credential")
        self.assertEqual(service.get_credential(first.id).status, "Active")
        self.assertEqual(service.list_archives(), [])

        service.archive_credential(first.id, "Permanent cleanup")
        purged = service.purge_archive("credential:ACC-001")
        self.assertEqual(purged.entity_id, "ACC-001")
        self.assertEqual(service.list_credentials(include_archived=True), [])
        second = service.add_credential(self._credential(name="Second account"))
        self.assertEqual(second.id, "ACC-002")
        service.close()

    def test_wrong_password_tamper_and_kdf_resource_attack_fail_closed(self) -> None:
        recovery_key = CredentialVaultService.create(self.project, PASSWORD)
        with self.assertRaises(KitError) as wrong:
            CredentialVaultService.unlock_with_password(self.project, "wrong password value")
        self.assertEqual(wrong.exception.code, "VAULT_UNLOCK_FAILED")

        vault = CredentialVaultService.unlock_with_recovery_key(
            self.project, recovery_key
        )
        vault.add_credential(self._credential())
        vault.lock()

        vault_path = self.project / VAULT_RELATIVE_PATH
        envelope = json.loads(vault_path.read_text(encoding="utf-8"))
        encoded = envelope["payload"]["ciphertext"]
        padding = "=" * (-len(encoded) % 4)
        ciphertext = bytearray(base64.urlsafe_b64decode(encoded + padding))
        ciphertext[len(ciphertext) // 2] ^= 1
        envelope["payload"]["ciphertext"] = (
            base64.urlsafe_b64encode(ciphertext).decode("ascii").rstrip("=")
        )
        write_json(vault_path, envelope)
        with self.assertRaises(KitError) as tampered:
            CredentialVaultService.unlock_with_recovery_key(self.project, recovery_key)
        self.assertEqual(tampered.exception.code, "VAULT_CORRUPT")

        clean_service = ProjectService.create_project(
            self.root / "kdf-project", "KDF-TEST", "KDF Test"
        )
        clean_project = clean_service.root
        clean_service.close()
        CredentialVaultService.create(clean_project, PASSWORD)
        clean_path = clean_project / VAULT_RELATIVE_PATH
        envelope = json.loads(clean_path.read_text(encoding="utf-8"))
        password_slot = next(
            slot for slot in envelope["keySlots"] if slot["type"] == "password"
        )
        password_slot["kdf"]["memoryKiB"] = KDF_MEMORY_MAX_KIB + 1
        write_json(clean_path, envelope)
        with self.assertRaises(KitError) as oversized:
            CredentialVaultService.unlock_with_password(clean_project, PASSWORD)
        self.assertEqual(oversized.exception.code, "VAULT_KDF_INVALID")

    def test_recovery_password_change_and_concurrent_session_conflict(self) -> None:
        recovery_key = CredentialVaultService.create(self.project, PASSWORD)
        first = CredentialVaultService.unlock_with_password(self.project, PASSWORD)
        stale = CredentialVaultService.unlock_with_password(self.project, PASSWORD)
        first.add_credential(self._credential())
        with self.assertRaises(KitError) as conflict:
            stale.add_credential(self._credential(name="Stale session account"))
        self.assertEqual(conflict.exception.code, "VAULT_CONFLICT")
        stale.lock()

        first.change_password(NEW_PASSWORD, current_password=PASSWORD)
        first.lock()
        with self.assertRaises(KitError) as old_password:
            CredentialVaultService.unlock_with_password(self.project, PASSWORD)
        self.assertEqual(old_password.exception.code, "VAULT_UNLOCK_FAILED")

        with CredentialVaultService.unlock_with_password(
            self.project, NEW_PASSWORD
        ) as changed:
            self.assertEqual([item.id for item in changed.list_credentials()], ["ACC-001"])
        with CredentialVaultService.unlock_with_recovery_key(
            self.project, recovery_key
        ) as recovered:
            self.assertEqual(
                recovered.reveal_secrets("ACC-001")["password"],
                "SuperSecret!234",
            )

    def test_credential_validation_rejects_unknown_targets_and_weak_passwords(self) -> None:
        with self.assertRaises(KitError) as weak:
            CredentialVaultService.create(self.project, "short")
        self.assertEqual(weak.exception.code, "VAULT_PASSWORD_WEAK")

        CredentialVaultService.create(self.project, PASSWORD)
        with CredentialVaultService.unlock_with_password(self.project, PASSWORD) as vault:
            invalid = CredentialInput(
                name="Unknown target",
                credential_type="api-token",
                target_ids=("WEB-99",),
                secret_values={"token": "opaque-token"},
            )
            with self.assertRaises(KitError) as unknown:
                vault.add_credential(invalid)
            self.assertEqual(unknown.exception.code, "TARGET_NOT_FOUND")
            self.assertEqual(vault.list_credentials(), [])


if __name__ == "__main__":
    unittest.main()
