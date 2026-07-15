from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from webpentestkit.core import add_target, init_project
from webpentestkit.encrypted_project import (
    EncryptedProjectStorage,
    _safe_extract_archive,
    is_encrypted_project,
    read_encrypted_project_header,
    restore_encrypted_project_backup,
)
from webpentestkit.errors import KitError
from webpentestkit.models import CredentialInput
from webpentestkit.services import ProjectService


PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "new correct horse battery staple"


class EncryptedProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = init_project(
            str(self.root / "plain-project"),
            "ENCRYPTED-TEST",
            "Highly Sensitive Assessment",
            "Sensitive Customer Name",
        )
        add_target(
            str(self.project),
            "WEB-01",
            "Sensitive Portal",
            "https://sensitive.example.test",
            "Staging",
        )
        self.container = self.root / "assessment.wpkproj"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create(self):
        return EncryptedProjectStorage.create_from_directory(
            self.project,
            self.container,
            PASSWORD,
        )

    def test_encrypted_copy_round_trip_and_service_commit(self) -> None:
        creation = self._create()
        self.assertEqual(creation.container, self.container.resolve())
        self.assertTrue(is_encrypted_project(self.container))
        header = read_encrypted_project_header(self.container)
        self.assertEqual(header["formatVersion"], 1)
        self.assertEqual(header["revision"], 0)
        raw = self.container.read_bytes()
        for sensitive in (
            b"Sensitive Customer Name",
            b"Highly Sensitive Assessment",
            b"Sensitive Portal",
            b"sensitive.example.test",
        ):
            self.assertNotIn(sensitive, raw)

        storage = EncryptedProjectStorage.unlock_with_password(
            self.container, PASSWORD
        )
        service = ProjectService.open(storage)
        self.assertTrue(service.encrypted)
        self.assertEqual(service.reference, self.container.resolve())
        self.assertEqual(service.get_project().customer_name, "Sensitive Customer Name")
        service.update_target("WEB-01", name="Updated encrypted portal")
        service.close()

        reopened = EncryptedProjectStorage.unlock_with_password(
            self.container, PASSWORD
        )
        reopened_service = ProjectService.open(reopened)
        try:
            self.assertEqual(
                reopened_service.get_target("WEB-01").name,
                "Updated encrypted portal",
            )
            exported = reopened.export_plain_copy(self.root / "explicit-plain-export")
            self.assertTrue((exported / "project.json").is_file())
        finally:
            reopened_service.close()

        original = ProjectService.open(self.project)
        self.assertEqual(original.get_target("WEB-01").name, "Sensitive Portal")

    def test_wrong_password_recovery_change_and_session_lock(self) -> None:
        creation = self._create()
        with self.assertRaises(KitError) as wrong:
            EncryptedProjectStorage.unlock_with_password(
                self.container, "wrong password value"
            )
        self.assertEqual(wrong.exception.code, "PROJECT_UNLOCK_FAILED")

        storage = EncryptedProjectStorage.unlock_with_recovery_key(
            self.container,
            creation.recovery_key,
        )
        with self.assertRaises(KitError) as locked:
            EncryptedProjectStorage.unlock_with_recovery_key(
                self.container,
                creation.recovery_key,
                timeout=0.01,
            )
        self.assertEqual(locked.exception.code, "ENCRYPTED_PROJECT_LOCK_TIMEOUT")
        storage.change_password(NEW_PASSWORD)
        storage.close()

        with self.assertRaises(KitError) as old:
            EncryptedProjectStorage.unlock_with_password(self.container, PASSWORD)
        self.assertEqual(old.exception.code, "PROJECT_UNLOCK_FAILED")
        changed = EncryptedProjectStorage.unlock_with_password(
            self.container, NEW_PASSWORD
        )
        changed.close()
        recovered = EncryptedProjectStorage.unlock_with_recovery_key(
            self.container,
            creation.recovery_key,
        )
        recovered.close()

    def test_ciphertext_tamper_is_detected(self) -> None:
        creation = self._create()
        raw = bytearray(self.container.read_bytes())
        raw[-1] ^= 1
        self.container.write_bytes(raw)
        with self.assertRaises(KitError) as tampered:
            EncryptedProjectStorage.unlock_with_recovery_key(
                self.container,
                creation.recovery_key,
            )
        self.assertEqual(tampered.exception.code, "ENCRYPTED_PROJECT_CORRUPT")

    def test_failed_seal_preserves_previous_container(self) -> None:
        self._create()
        original = self.container.read_bytes()
        storage = EncryptedProjectStorage.unlock_with_password(
            self.container, PASSWORD
        )
        service = ProjectService.open(storage)
        with mock.patch(
            "webpentestkit.encrypted_project._write_encrypted_container",
            side_effect=OSError("simulated container write failure"),
        ):
            with self.assertRaises(OSError):
                service.update_target("WEB-01", name="Unsealed update")
        self.assertEqual(self.container.read_bytes(), original)
        storage.discard_and_close()

        reopened = EncryptedProjectStorage.unlock_with_password(
            self.container, PASSWORD
        )
        reopened_service = ProjectService.open(reopened)
        try:
            self.assertEqual(reopened_service.get_target("WEB-01").name, "Sensitive Portal")
        finally:
            reopened_service.close()

    def test_archive_extraction_rejects_parent_traversal(self) -> None:
        archive = self.root / "malicious.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as value:
            value.writestr("../escape.txt", "must not escape")
        destination = self.root / "extract"
        destination.mkdir()
        with self.assertRaises(KitError) as escaped:
            _safe_extract_archive(archive, destination)
        self.assertEqual(escaped.exception.code, "ENCRYPTED_PROJECT_PATH_ESCAPE")
        self.assertFalse((self.root / "escape.txt").exists())

    def test_encrypted_project_unlocks_bound_credential_vault_once(self) -> None:
        self._create()
        service = ProjectService.open_encrypted(
            self.container,
            password=PASSWORD,
        )
        vault_recovery = service.create_credential_vault(PASSWORD)
        self.assertTrue(vault_recovery.startswith("WPK-RK1-"))
        credential = service.add_credential(
            CredentialInput(
                name="Encrypted project account",
                credential_type="api-token",
                target_ids=("WEB-01",),
                username="encrypted-user",
                secret_values={"token": "project-bound-secret-token"},
            )
        )
        self.assertEqual(credential.id, "ACC-001")
        service.change_encryption_password(
            NEW_PASSWORD,
            current_password=PASSWORD,
        )
        service.close()

        raw = self.container.read_bytes()
        self.assertNotIn(b"encrypted-user", raw)
        self.assertNotIn(b"project-bound-secret-token", raw)
        reopened = ProjectService.open_encrypted(
            self.container,
            password=NEW_PASSWORD,
        )
        try:
            self.assertTrue(reopened.credential_vault_unlocked)
            self.assertEqual(
                reopened.reveal_credential_secrets("ACC-001")["token"],
                "project-bound-secret-token",
            )
        finally:
            reopened.close()

    def test_existing_vault_can_be_bound_after_project_conversion(self) -> None:
        plain = ProjectService.open(self.project)
        plain.create_credential_vault(PASSWORD)
        plain.add_credential(
            CredentialInput(
                name="Converted account",
                credential_type="password",
                target_ids=("WEB-01",),
                secret_values={"password": "converted-secret"},
            )
        )
        plain.close()
        self._create()

        converted = ProjectService.open_encrypted(
            self.container,
            password=PASSWORD,
        )
        self.assertFalse(converted.credential_vault_unlocked)
        self.assertIsNotNone(converted.credential_vault_error)
        self.assertEqual(
            converted.credential_vault_error.code,
            "VAULT_KEY_SLOT_MISSING",
        )
        converted.unlock_credential_vault(password=PASSWORD)
        converted.bind_credential_vault_to_project()
        converted.close()

        reopened = ProjectService.open_encrypted(
            self.container,
            password=PASSWORD,
        )
        try:
            self.assertTrue(reopened.credential_vault_unlocked)
            self.assertEqual(
                reopened.reveal_credential_secrets("ACC-001")["password"],
                "converted-secret",
            )
        finally:
            reopened.close()

    def test_encrypted_backup_and_restore_remain_unlockable(self) -> None:
        creation = self._create()
        service = ProjectService.open_encrypted(
            self.container,
            password=PASSWORD,
        )
        service.update_target("WEB-01", name="Backed up portal")
        backup = service.create_encrypted_backup(self.root / "backup-copy")
        self.assertTrue(is_encrypted_project(backup))
        service.close()

        restored = restore_encrypted_project_backup(
            backup,
            self.root / "restored-copy",
        )
        restored_service = ProjectService.open_encrypted(
            restored,
            recovery_key=creation.recovery_key,
        )
        try:
            self.assertEqual(
                restored_service.get_target("WEB-01").name,
                "Backed up portal",
            )
        finally:
            restored_service.close()


if __name__ == "__main__":
    unittest.main()
