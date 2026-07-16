from __future__ import annotations

import json
import re
import string
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QSettings

from webpentestkit.errors import KitError
from webpentestkit.localization import (
    LanguagePackError,
    LocalizationManager,
    configure_localization,
    localize_error,
    normalize_locale,
    value_label,
)
from webpentestkit.qt_gui.localization import configure_ui_localization


class LocalizationTest(unittest.TestCase):
    def tearDown(self) -> None:
        configure_localization("ko-KR")

    def _write_pack(self, root: Path, payload: dict) -> Path:
        path = root / f"{payload.get('locale', 'invalid')}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_external_pack_uses_stable_keys_and_korean_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_pack(
                root,
                {
                    "schemaVersion": 1,
                    "locale": "en-US",
                    "name": "English",
                    "fallback": "ko-KR",
                    "messages": {
                        "ui": {
                            "nav.dashboard": "Dashboard",
                            "sample.count": "Count: {count}",
                        },
                        "errors": {
                            "PROJECT_NOT_OPEN": "Open a project first."
                        },
                    },
                },
            )
            manager = LocalizationManager(
                locale="en_US",
                pack_directories=(root,),
            )
            self.assertEqual(manager.locale, "en-US")
            self.assertEqual(
                manager.translate("nav.dashboard", "대시보드"),
                "Dashboard",
            )
            self.assertEqual(
                manager.translate("nav.targets", "fallback missing"),
                "진단 대상",
            )
            self.assertEqual(
                manager.translate(
                    "sample.count",
                    "개수: {count}",
                    params={"count": 3},
                ),
                "Count: 3",
            )
            self.assertEqual(
                [(option.locale, option.name) for option in manager.options()],
                [("en-US", "English"), ("ko-KR", "한국어")],
            )

    def test_builtin_english_pack_is_complete_and_placeholder_safe(self) -> None:
        locale_root = Path(__file__).resolve().parents[1] / "webpentestkit" / "locales"
        korean = json.loads((locale_root / "ko-KR.json").read_text(encoding="utf-8"))
        english = json.loads((locale_root / "en-US.json").read_text(encoding="utf-8"))
        formatter = string.Formatter()

        def placeholders(template: str) -> set[str]:
            return {
                field_name.split(".", 1)[0].split("[", 1)[0]
                for _literal, field_name, _spec, _conversion in formatter.parse(template)
                if field_name
            }

        for domain in ("ui", "errors"):
            korean_messages = korean["messages"][domain]
            english_messages = english["messages"][domain]
            self.assertEqual(set(english_messages), set(korean_messages))
            for key, text in english_messages.items():
                self.assertIsNone(re.search(r"[가-힣]", text), key)
                self.assertEqual(
                    placeholders(text),
                    placeholders(korean_messages[key]),
                    key,
                )

        manager = LocalizationManager(locale="en-US")
        self.assertEqual(manager.translate("nav.dashboard", "대시보드"), "Dashboard")
        self.assertIn(
            ("en-US", "English"),
            [(option.locale, option.name) for option in manager.options()],
        )

        configure_localization("ko-KR")
        self.assertEqual(value_label("severity", "Critical"), "치명적")
        configure_localization("en-US")
        self.assertEqual(value_label("severity", "Critical"), "Critical")

    def test_error_code_can_be_localized_without_changing_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_pack(
                root,
                {
                    "schemaVersion": 1,
                    "locale": "en-US",
                    "name": "English",
                    "fallback": "ko-KR",
                    "messages": {
                        "ui": {},
                        "errors": {
                            "ITEM_UNKNOWN": "Unknown item: {item_id}"
                        },
                    },
                },
            )
            configure_localization("en-US", pack_directories=(root,))
            error = KitError(
                "항목을 찾을 수 없습니다.",
                code="ITEM_UNKNOWN",
                params={"item_id": "WEB-01"},
            )
            self.assertEqual(localize_error(error), "Unknown item: WEB-01")
            self.assertEqual(error.message, "항목을 찾을 수 없습니다.")
            self.assertEqual(error.to_dict()["params"], {"item_id": "WEB-01"})

    def test_invalid_pack_is_rejected_and_unknown_locale_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_pack(
                root,
                {
                    "schemaVersion": 99,
                    "locale": "en-US",
                    "name": "English",
                    "messages": {},
                },
            )
            with self.assertRaises(LanguagePackError):
                LocalizationManager(pack_directories=(root,))
        manager = LocalizationManager(locale="xx-YY")
        self.assertEqual(manager.locale, "en-US")
        self.assertEqual(normalize_locale("en_us"), "en-US")

    def test_new_install_defaults_to_english(self) -> None:
        manager = LocalizationManager()
        self.assertEqual(manager.locale, "en-US")
        self.assertEqual(normalize_locale(None), "en-US")

    def test_ui_locale_is_loaded_from_app_settings_at_startup_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_pack(
                root,
                {
                    "schemaVersion": 1,
                    "locale": "en-US",
                    "name": "English",
                    "fallback": "ko-KR",
                    "messages": {"ui": {}, "errors": {}},
                },
            )
            settings = QSettings(
                str(root / "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.setValue("appearance/uiLanguage", "en-US")
            settings.sync()
            with mock.patch.dict(
                "os.environ",
                {"OTTER_LANGUAGE_PATHS": str(root)},
            ):
                manager = configure_ui_localization(settings)
            self.assertEqual(manager.locale, "en-US")
            self.assertEqual(
                settings.value("appearance/uiLanguage", type=str),
                "en-US",
            )

    def test_ui_locale_defaults_to_english_when_setting_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "settings.ini"),
                QSettings.Format.IniFormat,
            )
            manager = configure_ui_localization(settings)
            self.assertEqual(manager.locale, "en-US")
            self.assertIsNone(settings.value("appearance/uiLanguage"))


if __name__ == "__main__":
    unittest.main()
