from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import webpentestkit.repository as repository_module
from webpentestkit.common import KitError
from webpentestkit.locking import file_lock
from webpentestkit.repository import ProjectRepository
from webpentestkit.services import ProjectService


class PersistenceSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        service = ProjectService.create_project(
            self.root / "project", "LOCK-TEST", "Lock Test"
        )
        self.project = service.root
        service.create_target(
            "WEB-01",
            "Portal",
            "https://portal.example.test",
        )
        service.close()
        self.repository = ProjectRepository(self.project)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_project_lock_is_reentrant_and_times_out_in_another_thread(self) -> None:
        errors: list[KitError] = []

        def contend() -> None:
            try:
                with self.repository.lock(timeout=0.1):
                    pass
            except KitError as exc:
                errors.append(exc)

        with self.repository.lock():
            with self.repository.lock():
                thread = threading.Thread(target=contend)
                thread.start()
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "PROJECT_LOCK_TIMEOUT")
        self.assertTrue((self.project / ".otter.lock").is_file())

    def test_non_reentrant_session_lock_can_close_on_another_thread(self) -> None:
        lock_path = self.root / "session.lock"
        context = file_lock(lock_path, reentrant=False)
        context.__enter__()
        errors: list[Exception] = []

        def close_session() -> None:
            try:
                context.__exit__(None, None, None)
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        worker = threading.Thread(target=close_session)
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        with file_lock(lock_path, timeout=0.1, reentrant=False):
            pass

    def test_multi_record_write_rolls_back_when_second_write_fails(self) -> None:
        project_path = self.project / "project.json"
        target_path = next(self.project.glob("targets/*/target.json"))
        before_project = project_path.read_text(encoding="utf-8")
        before_target = target_path.read_text(encoding="utf-8")
        project_value = self.repository.load_project()
        target_record = self.repository.get_target("WEB-01")
        project_value["name"] = "Should Roll Back"
        target_value = dict(target_record.data)
        target_value["name"] = "Should Also Roll Back"

        original_write_json = repository_module.write_json
        calls = 0

        def fail_second(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated second write failure")
            original_write_json(path, value)

        with mock.patch.object(repository_module, "write_json", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.repository.write_json_records(
                    ((project_path, project_value), (target_path, target_value))
                )

        self.assertEqual(project_path.read_text(encoding="utf-8"), before_project)
        self.assertEqual(target_path.read_text(encoding="utf-8"), before_target)


if __name__ == "__main__":
    unittest.main()
