import ast
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

from AI import (
    AIFramework,
    AggressivePersonalityCoresAI,
    DisableAI,
    KillOneByOneAI,
    PerfectPlay,
    PersonalityCores,
    PlayerInput,
    Random,
    StrategicPersonalityCoresAI,
    SurvivalPersonalityCoresAI,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
INSERT_DIR = ROOT_DIR / 'insert'
CUSTOM_AI_DIR = INSERT_DIR / 'custom-ai'
REGISTRY_PATH = CUSTOM_AI_DIR / 'ai_registry.json'
TEMPLATE_PATH = CUSTOM_AI_DIR / 'Ai_template.py'
LEGACY_REGISTRY_PATH = INSERT_DIR / 'ai_registry.json'
LEGACY_TEMPLATE_PATH = INSERT_DIR / 'Ai_template.py'

BUILTIN_AI: list[tuple[str, type[AIFramework]]] = [
    ('Player Input', PlayerInput),
    ('Baseline AI', PerfectPlay),
    ('Random AI', Random),
    ('Personality Cores AI', PersonalityCores),
    ('Aggressive Personality Cores AI', AggressivePersonalityCoresAI),
    ('Strategic Personality Cores AI', StrategicPersonalityCoresAI),
    ('Survival Personality Cores AI', SurvivalPersonalityCoresAI),
    ('Kill One By One AI', KillOneByOneAI),
    ('Disable AI', DisableAI),
]

AI_LIST: list[type[AIFramework]] = [cls for _, cls in BUILTIN_AI]
AI_LABELS: list[str] = [label for label, _ in BUILTIN_AI]
AI_METADATA: list[dict[str, Any]] = []


def _safe_module_name(stem: str) -> str:
    cleaned = re.sub(r'[^0-9a-zA-Z_]+', '_', stem)
    return f'custom_ai_{cleaned}'


def _load_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists() and LEGACY_REGISTRY_PATH.exists():
        CUSTOM_AI_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LEGACY_REGISTRY_PATH, REGISTRY_PATH)
    if not REGISTRY_PATH.exists():
        return []
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except Exception:
        pass
    return []


def _save_registry(entries: list[dict[str, Any]]) -> None:
    CUSTOM_AI_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')


def _import_module_from_path(file_path: Path) -> ModuleType:
    module_name = _safe_module_name(file_path.stem)
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ValueError('Unable to load AI module.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_ai_class(module: ModuleType) -> type[AIFramework]:
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if not isinstance(attr, type):
            continue
        if attr is AIFramework:
            continue
        if not issubclass(attr, AIFramework):
            continue
        if attr.__module__ != module.__name__:
            continue
        if 'calculate' not in attr.__dict__ or 'activate' not in attr.__dict__:
            continue
        return attr
    raise ValueError('AI class not found. Your file must define a class inheriting AIFramework with calculate() and activate().')


def _validate_ai_source(source_code: str) -> None:
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        raise ValueError(f'Syntax error in Python file: {e}')

    valid = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        inherits_framework = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'AIFramework':
                inherits_framework = True
                break
            if isinstance(base, ast.Attribute) and base.attr == 'AIFramework':
                inherits_framework = True
                break
        if not inherits_framework:
            continue

        methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
        if 'calculate' in methods and 'activate' in methods:
            valid = True
            break

    if not valid:
        raise ValueError('Invalid AI file. It must define a class that inherits AIFramework and implements calculate(self) and activate(self, activationNo).')


def _sanitize_dest_name(filename: str) -> str:
    stem = re.sub(r'[^0-9a-zA-Z_\-]+', '_', Path(filename).stem).strip('_') or 'custom_ai'
    return f'{stem}.py'


def _ensure_unique_file(dest_name: str) -> Path:
    CUSTOM_AI_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = CUSTOM_AI_DIR / dest_name
    if not dest_path.exists():
        return dest_path
    stem = Path(dest_name).stem
    suffix = Path(dest_name).suffix
    counter = 1
    while True:
        candidate = CUSTOM_AI_DIR / f'{stem}_{counter}{suffix}'
        if not candidate.exists():
            return candidate
        counter += 1


def import_ai(ai_name: str, description: str, source_file: str) -> dict[str, Any]:
    ai_name = (ai_name or '').strip()
    description = (description or '').strip()

    if not ai_name:
        raise ValueError('AI Name is required.')
    if len(ai_name) > 20:
        raise ValueError('AI Name must be 20 characters or fewer.')
    if len(description) > 1000:
        raise ValueError('Description must be 1000 characters or fewer.')
    if not source_file:
        raise ValueError('Please choose a Python (.py) file to upload.')

    source_path = Path(source_file)
    if not source_path.exists() or not source_path.is_file():
        raise ValueError('Selected file does not exist.')
    if source_path.suffix.lower() != '.py':
        raise ValueError('Only .py files are allowed.')

    source_code = source_path.read_text(encoding='utf-8')
    _validate_ai_source(source_code)

    registry = _load_registry()
    if any(str(item.get('name', '')).strip().lower() == ai_name.lower() for item in registry):
        raise ValueError('AI Name already exists. Please choose a different name.')

    INSERT_DIR.mkdir(parents=True, exist_ok=True)
    CUSTOM_AI_DIR.mkdir(parents=True, exist_ok=True)
    saved_file_path = _ensure_unique_file(_sanitize_dest_name(source_path.name))
    shutil.copyfile(source_path, saved_file_path)

    module = _import_module_from_path(saved_file_path)
    ai_class = _extract_ai_class(module)

    entry = {
        'name': ai_name,
        'description': description,
        'file_path': str(saved_file_path.relative_to(ROOT_DIR)).replace('\\', '/'),
        'class_name': ai_class.__name__,
    }
    registry.append(entry)
    _save_registry(registry)

    refresh_ai_registry()
    return entry


def update_ai(old_name: str, new_name: str, description: str, source_file: str = '') -> dict[str, Any]:
    old_name = (old_name or '').strip()
    new_name = (new_name or '').strip()
    description = (description or '').strip()
    source_file = (source_file or '').strip()

    if not old_name:
        raise ValueError('Original AI Name is required.')
    if not new_name:
        raise ValueError('AI Name is required.')
    if len(new_name) > 20:
        raise ValueError('AI Name must be 20 characters or fewer.')
    if len(description) > 1000:
        raise ValueError('Description must be 1000 characters or fewer.')

    registry = _load_registry()
    entry_index = next((i for i, item in enumerate(registry) if str(item.get('name', '')).strip().lower() == old_name.lower()), -1)
    if entry_index < 0:
        raise ValueError('Custom AI not found.')

    if any(
        i != entry_index and str(item.get('name', '')).strip().lower() == new_name.lower()
        for i, item in enumerate(registry)
    ):
        raise ValueError('AI Name already exists. Please choose a different name.')

    entry = dict(registry[entry_index])
    current_file_path = str(entry.get('file_path', '')).strip()
    current_class_name = str(entry.get('class_name', '')).strip()
    if not current_file_path or not current_class_name:
        raise ValueError('Custom AI record is invalid.')

    abs_path = ROOT_DIR / current_file_path
    if not abs_path.exists() or abs_path.suffix.lower() != '.py':
        raise ValueError('Existing custom AI file is missing.')

    updated_file_path = current_file_path
    updated_class_name = current_class_name

    if source_file:
        source_path = Path(source_file)
        if not source_path.exists() or not source_path.is_file():
            raise ValueError('Selected file does not exist.')
        if source_path.suffix.lower() != '.py':
            raise ValueError('Only .py files are allowed.')

        source_code = source_path.read_text(encoding='utf-8')
        _validate_ai_source(source_code)

        shutil.copyfile(source_path, abs_path)
        module = _import_module_from_path(abs_path)
        ai_class = _extract_ai_class(module)
        updated_class_name = ai_class.__name__

    updated_entry = {
        'name': new_name,
        'description': description,
        'file_path': updated_file_path,
        'class_name': updated_class_name,
    }
    registry[entry_index] = updated_entry
    _save_registry(registry)
    refresh_ai_registry()
    return updated_entry


def delete_ai(ai_name: str) -> None:
    ai_name = (ai_name or '').strip()
    if not ai_name:
        raise ValueError('AI Name is required.')

    registry = _load_registry()
    entry_index = next((i for i, item in enumerate(registry) if str(item.get('name', '')).strip().lower() == ai_name.lower()), -1)
    if entry_index < 0:
        raise ValueError('Custom AI not found.')

    entry = registry.pop(entry_index)
    _save_registry(registry)

    file_path = str(entry.get('file_path', '')).strip()
    if file_path:
        abs_path = ROOT_DIR / file_path
        try:
            if abs_path.exists() and abs_path.is_file():
                abs_path.unlink()
        except Exception:
            pass

    refresh_ai_registry()


def refresh_ai_registry() -> None:
    global AI_LIST, AI_LABELS, AI_METADATA

    ai_classes = [cls for _, cls in BUILTIN_AI]
    labels = [label for label, _ in BUILTIN_AI]
    metadata: list[dict[str, Any]] = []

    registry = _load_registry()
    sanitized_registry: list[dict[str, Any]] = []

    for item in registry:
        name = str(item.get('name', '')).strip()
        file_path = str(item.get('file_path', '')).strip()
        class_name = str(item.get('class_name', '')).strip()
        description = str(item.get('description', '')).strip()

        if not name or not file_path or not class_name:
            continue

        abs_path = ROOT_DIR / file_path
        if not abs_path.exists() or abs_path.suffix.lower() != '.py':
            continue

        try:
            module = _import_module_from_path(abs_path)
            ai_class = getattr(module, class_name, None)
            if not isinstance(ai_class, type) or not issubclass(ai_class, AIFramework):
                continue
            if 'calculate' not in ai_class.__dict__ or 'activate' not in ai_class.__dict__:
                continue
        except Exception:
            continue

        if name.lower() in {label.lower() for label in labels}:
            continue

        labels.append(name)
        ai_classes.append(ai_class)
        metadata.append(
            {
                'name': name,
                'description': description,
                'file_path': file_path,
                'class_name': class_name,
            }
        )
        sanitized_registry.append(
            {
                'name': name,
                'description': description,
                'file_path': file_path,
                'class_name': class_name,
            }
        )

    AI_LIST = ai_classes
    AI_LABELS = labels
    AI_METADATA = metadata
    _save_registry(sanitized_registry)


def get_ai_list() -> list[type[AIFramework]]:
    return list(AI_LIST)


def get_ai_labels() -> list[str]:
    return list(AI_LABELS)


def get_ai_metadata() -> list[dict[str, Any]]:
    return [dict(item) for item in AI_METADATA]


def download_template() -> Path:
    if not TEMPLATE_PATH.exists() and LEGACY_TEMPLATE_PATH.exists():
        CUSTOM_AI_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LEGACY_TEMPLATE_PATH, TEMPLATE_PATH)
    if not TEMPLATE_PATH.exists():
        raise ValueError('AI template file is missing.')

    downloads = Path.home() / 'Downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    target = downloads / 'AI_template.py'
    shutil.copyfile(TEMPLATE_PATH, target)
    return target


refresh_ai_registry()
