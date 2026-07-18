from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import string
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = ROOT / "webpentestkit" / "qt_gui"
PRESENTATION_CONTRACT = ROOT / "webpentestkit" / "presentation_engine" / "contracts.py"
KO_CATALOG = ROOT / "webpentestkit" / "locales" / "ko-KR.json"
EN_CATALOG = ROOT / "webpentestkit" / "locales" / "en-US.json"
EN_SOURCE = ROOT / "translations" / "en-US"
HANGUL = re.compile(r"[\uac00-\ud7a3]")
FORMATTER = string.Formatter()


def target_paths() -> list[Path]:
    return sorted(
        path
        for path in GUI_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts and path.name not in {"theme.py"}
    )


def _module_key(path: Path) -> str:
    relative = path.relative_to(GUI_ROOT).with_suffix("")
    return "_".join(relative.parts)


def _placeholders(template: str) -> set[str]:
    return {
        field_name.split(".", 1)[0].split("[", 1)[0]
        for _literal, field_name, _format_spec, _conversion in FORMATTER.parse(template)
        if field_name
    }


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _has_ancestor(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
    predicate,
) -> bool:
    current = parents.get(node)
    while current is not None:
        if predicate(current):
            return True
        current = parents.get(current)
    return False


def _is_docstring(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    expression = parents.get(node)
    owner = parents.get(expression) if isinstance(expression, ast.Expr) else None
    return isinstance(owner, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and bool(owner.body) and owner.body[0] is expression


def _index(lines: list[str], offsets: list[int], line: int, byte_column: int) -> int:
    prefix = lines[line - 1].encode("utf-8")[:byte_column].decode("utf-8")
    return offsets[line - 1] + len(prefix)


def _span(node: ast.AST, lines: list[str], offsets: list[int]) -> tuple[int, int]:
    return (
        _index(lines, offsets, node.lineno, node.col_offset),
        _index(lines, offsets, node.end_lineno, node.end_col_offset),
    )


def _key(module: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"generated.{module}.{digest}"


def _joined_template(
    node: ast.JoinedStr,
    source: str,
) -> tuple[str, list[tuple[str, str]]]:
    parts: list[str] = []
    parameters: list[tuple[str, str]] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value.replace("{", "{{").replace("}", "}}"))
            continue
        if not isinstance(value, ast.FormattedValue):
            continue
        name = f"value{len(parameters)}"
        expression = ast.get_source_segment(source, value.value) or ast.unparse(value.value)
        format_spec = ""
        if value.format_spec is not None:
            format_spec, _unused = _joined_template(value.format_spec, source)
        conversion = f"!{chr(value.conversion)}" if value.conversion >= 0 else ""
        parts.append("{" + name + conversion + (f":{format_spec}" if format_spec else "") + "}")
        parameters.append((name, expression))
    return "".join(parts), parameters


def _ensure_import(source: str) -> str:
    if re.search(r"from \.\.localization import .*\btr\b", source):
        return source
    if "from ..localization import localize_error" in source:
        return source.replace(
            "from ..localization import localize_error",
            "from ..localization import localize_error, tr",
            1,
        )
    tree = ast.parse(source)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    insert_line = max((node.end_lineno for node in imports), default=1)
    lines = source.splitlines(keepends=True)
    lines.insert(insert_line, "from ..localization import tr\n")
    return "".join(lines)


def collect(path: Path) -> tuple[list[tuple[ast.AST, str, str]], str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents = _parents(tree)
    results: list[tuple[ast.AST, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            template, _parameters = _joined_template(node, source)
            if HANGUL.search(template) and not _has_ancestor(
                node,
                parents,
                lambda item: isinstance(item, ast.Call) and _call_name(item) == "tr",
            ):
                results.append((node, _key(_module_key(path), template), template))
            continue
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if not HANGUL.search(node.value) or _is_docstring(node, parents):
            continue
        if _has_ancestor(node, parents, lambda item: isinstance(item, ast.JoinedStr)):
            continue
        if _has_ancestor(
            node,
            parents,
            lambda item: isinstance(item, ast.Call) and _call_name(item) == "tr",
        ):
            continue
        results.append((node, _key(_module_key(path), node.value), node.value))
    return results, source


def translation_calls(path: Path) -> list[tuple[int, str]]:
    return [(line, key) for line, key, _default in translation_entries(path)]


def translation_entries(path: Path) -> list[tuple[int, str, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node) != "tr" or len(node.args) < 2:
            continue
        key = node.args[0]
        default = node.args[1]
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(default, ast.Constant)
            and isinstance(default.value, str)
        ):
            calls.append((node.lineno, key.value, default.value))
    return calls


def presentation_error_codes() -> list[tuple[Path, int, str]]:
    results: list[tuple[Path, int, str]] = []
    package = ROOT / "webpentestkit"
    for path in sorted(package.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) != "KitError":
                continue
            for keyword in node.keywords:
                if keyword.arg != "code":
                    continue
                value = keyword.value
                if (
                    isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and value.value.startswith("PRESENTATION_")
                ):
                    results.append((path, node.lineno, value.value))
    return results


def presentation_error_entries() -> list[tuple[Path, int, str, str]]:
    results: list[tuple[Path, int, str, str]] = []
    package = ROOT / "webpentestkit"
    for path in sorted(package.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) != "KitError":
                continue
            message = node.args[0] if node.args else None
            if not isinstance(message, ast.Constant) or not isinstance(message.value, str):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "code"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                    and keyword.value.value.startswith("PRESENTATION_")
                ):
                    results.append((path, node.lineno, keyword.value.value, message.value))
    return results


def presentation_contract_entries() -> dict[str, str]:
    """Return fixed role and slot labels declared by the presentation contract."""

    tree = ast.parse(PRESENTATION_CONTRACT.read_text(encoding="utf-8"))
    entries: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"_role", "_slot"} or len(node.args) < 3:
            continue
        code, label, description = (ast.literal_eval(item) for item in node.args[:3])
        if not all(isinstance(item, str) for item in (code, label, description)):
            raise ValueError("presentation role and slot labels must use string literals")
        if node.func.id == "_role":
            key = code.replace("-", "_")
            entries[f"presentations.role.{key}"] = label
            entries[f"presentations.roleDescription.{key}"] = description
        else:
            key = code.replace(".", "_")
            entries[f"presentations.slot.{key}"] = label
            entries[f"presentations.slotDescription.{key}"] = description
    # evidence.N is an indexed slot family rather than a single SlotSpec.
    entries.update(
        {
            "presentations.slot.evidence": "증적 이미지",
            "presentations.slotDescription.evidence": "보고서용 이미지 증적",
        }
    )
    return entries


def wrap() -> int:
    catalog = json.loads(KO_CATALOG.read_text(encoding="utf-8"))
    messages = catalog["messages"]["ui"]
    total = 0
    for path in target_paths():
        nodes, source = collect(path)
        if not nodes:
            continue
        lines = source.splitlines(keepends=True)
        offsets: list[int] = []
        offset = 0
        for line in lines:
            offsets.append(offset)
            offset += len(line)
        replacements: list[tuple[int, int, str]] = []
        for node, key, default in nodes:
            start, end = _span(node, lines, offsets)
            if isinstance(node, ast.JoinedStr):
                template, parameters = _joined_template(node, source)
                arguments = "".join(f", {name}={expression}" for name, expression in parameters)
                replacement = f"tr({key!r}, {template!r}{arguments})"
            else:
                original = source[start:end]
                replacement = f"tr({key!r}, {original})"
            replacements.append((start, end, replacement))
            messages.setdefault(key, default)
        for start, end, replacement in sorted(replacements, reverse=True):
            source = source[:start] + replacement + source[end:]
        path.write_text(_ensure_import(source), encoding="utf-8")
        total += len(replacements)
    KO_CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrapped {total} messages")
    return 0


def audit() -> int:
    failures: list[str] = []
    for path in target_paths():
        nodes, _source = collect(path)
        for node, _key_value, default in nodes:
            preview = default.replace("\n", " ")[:80]
            failures.append(f"{path.relative_to(ROOT)}:{node.lineno}: {preview}")
    if failures:
        print("\n".join(failures))
        print(f"{len(failures)} untranslated GUI strings")
        return 1
    if not EN_CATALOG.is_file():
        print("English language pack is missing")
        return 1
    korean = json.loads(KO_CATALOG.read_text(encoding="utf-8"))
    english = json.loads(EN_CATALOG.read_text(encoding="utf-8"))
    korean_ui = korean["messages"]["ui"]
    for key, default in presentation_contract_entries().items():
        if key not in korean_ui:
            failures.append(f"presentation contract missing ui.{key}")
        elif korean_ui[key] != default:
            failures.append(f"presentation contract default mismatch in ui.{key}")
    for path in target_paths():
        for line, key in translation_calls(path):
            if key not in korean_ui:
                failures.append(
                    f"{path.relative_to(ROOT)}:{line}: language pack missing ui.{key}"
                )
    korean_errors = korean["messages"]["errors"]
    for path, line, code in presentation_error_codes():
        if code not in korean_errors:
            failures.append(
                f"{path.relative_to(ROOT)}:{line}: language pack missing errors.{code}"
            )
    for domain in ("ui", "errors"):
        korean_messages = korean["messages"][domain]
        english_messages = english.get("messages", {}).get(domain, {})
        expected = set(korean_messages)
        actual = set(english_messages)
        for key in sorted(expected - actual):
            failures.append(f"en-US missing {domain}.{key}")
        for key in sorted(actual - expected):
            failures.append(f"en-US has unknown {domain}.{key}")
        for key, value in english_messages.items():
            if HANGUL.search(value):
                failures.append(f"en-US contains Hangul in {domain}.{key}")
            if key in korean_messages:
                korean_fields = _placeholders(korean_messages[key])
                english_fields = _placeholders(value)
                if korean_fields != english_fields:
                    failures.append(
                        f"placeholder mismatch in {domain}.{key}: "
                        f"ko={sorted(korean_fields)}, en={sorted(english_fields)}"
                    )
    if failures:
        print("\n".join(failures))
        return 1
    print("GUI translation audit passed")
    return 0


def build() -> int:
    korean = json.loads(KO_CATALOG.read_text(encoding="utf-8"))
    existing_english = (
        json.loads(EN_CATALOG.read_text(encoding="utf-8"))
        if EN_CATALOG.is_file()
        else {"messages": {"ui": {}, "errors": {}}}
    )
    translations: dict[str, str] = {}
    key_translations: dict[str, str] = {}
    errors: dict[str, str] = {}
    for path in sorted(EN_SOURCE.glob("*.json")):
        source = json.loads(path.read_text(encoding="utf-8"))
        translations.update(source.get("sources", {}))
        key_translations.update(source.get("keys", {}))
        errors.update(source.get("errors", {}))
    existing_ui = existing_english.get("messages", {}).get("ui", {})
    missing = sorted(
        key
        for key, value in korean["messages"]["ui"].items()
        if key not in key_translations
        and value not in translations
        and key not in existing_ui
    )
    if missing:
        for key in missing:
            print(f"missing source translation for key: {key}")
        return 1
    existing_errors = existing_english.get("messages", {}).get("errors", {})
    missing_errors = sorted(
        set(korean["messages"]["errors"]) - set(errors) - set(existing_errors)
    )
    if missing_errors:
        for key in missing_errors:
            print(f"missing error translation: {key}")
        return 1
    catalog = {
        "schemaVersion": 1,
        "locale": "en-US",
        "name": "English",
        "fallback": "ko-KR",
        "messages": {
            "ui": {
                key: key_translations.get(key, translations.get(value, existing_ui.get(key, value)))
                for key, value in korean["messages"]["ui"].items()
            },
            "errors": {
                key: errors.get(key, existing_errors.get(key, value))
                for key, value in korean["messages"]["errors"].items()
            },
        },
    }
    EN_CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"built {EN_CATALOG.relative_to(ROOT)}")
    return 0


def sync() -> int:
    """Add statically declared UI and presentation error defaults to ko-KR."""

    catalog = json.loads(KO_CATALOG.read_text(encoding="utf-8"))
    ui = catalog["messages"]["ui"]
    errors = catalog["messages"]["errors"]
    ui_added = 0
    ui_updated = 0
    errors_added = 0
    conflicts: list[str] = []
    original_ui = set(ui)
    for path in target_paths():
        for line, key, default in translation_entries(path):
            existing = ui.get(key)
            if key in original_ui and existing is not None and existing != default:
                conflicts.append(
                    f"{path.relative_to(ROOT)}:{line}: ui.{key} default differs from catalog"
                )
            elif existing is None:
                ui[key] = default
                ui_added += 1
    for key, default in presentation_contract_entries().items():
        existing = ui.get(key)
        if existing is None:
            ui[key] = default
            ui_added += 1
        elif existing != default:
            ui[key] = default
            ui_updated += 1
    for path, line, code, default in presentation_error_entries():
        existing = errors.get(code)
        if existing is None:
            errors[code] = default
            errors_added += 1
    if conflicts:
        print("\n".join(conflicts))
        return 1
    KO_CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"added {ui_added} UI messages, updated {ui_updated} contract messages, "
        f"and added {errors_added} presentation errors"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "build", "sync", "wrap"))
    args = parser.parse_args()
    if args.command == "audit":
        return audit()
    if args.command == "build":
        return build()
    if args.command == "sync":
        return sync()
    return wrap()


if __name__ == "__main__":
    raise SystemExit(main())
