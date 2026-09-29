"""Application defaults and shared settings-file management."""

import json
import sys
import threading
from copy import deepcopy
from pathlib import Path


APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
SETTINGS_FILE = APP_DIR / "settings.json"
SETTINGS_VERSION = 1
_SETTINGS_LOCK = threading.RLock()


# Defaults live in one place. Values from settings.json override these values;
# missing keys are filled in recursively from this mapping.
DEFAULT_SETTINGS = {
    "version": SETTINGS_VERSION,
    "answer_box": {
        "x": 0.0,
        "y": 0.0,
        "width": 450.0,
        "height": 250.0,
        "padding": 15,
        "min_width": 250,
        "min_height": 80,
        "max_width": 900,
        "max_height": 700,
        "set_button_width": 100,
        "set_button_height": 45,
    },
    "effort_colors": {
        "low": "#4CAF50",
        "medium": "#8BC34A",
        "high": "#FFC107",
        "xhigh": "#FF9800",
        "max": "#F44336",
    },
    "ocr": {
        "language": "en",
        "device": "gpu:0",
        "min_confidence": 0.7,
        "region_gap": 150,
        "region_padding": 20,
        "ignored_text": [
            "Home", "IgniteAI Search", "Syllabus", "Modules",
            "Announcements", "Assignments", "Grades", "Lucid (Whiteboard)",
            "Notebook", "Account", "Dashboard", "Courses", "Calendar",
            "Inbox", "History", "Studio", "Help",
        ],
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    },
    "reasoning": {
        "mode": "pro",
        "efforts": ["high", "xhigh", "medium", "low", "max"],
        "default": "high",
        "last_used": "high",
        "title_extraction_effort": "none",
    },
    "models": {
        "answer": "gpt-6-astra",
        "title_extraction": "gpt-5.4-nano",
    },
    "image": {"jpeg_quality": 90},
    "hotkeys": {
        "ocr_capture": "`",
        "image_capture": "f10",
        "configuration": "home",
        "toggle_overlay": "insert",
        "clear_answer": "esc",
        "exit": "delete",
        "cycle_effort": "f9",
    },
    "output": {
        "directory": "Answers",
        "save_markdown": True,
        "save_pdf": True,
    },
    "courses": [],
    "test_info": {"course": None, "test_name": None, "short_test_name": None},
    "title_cache": {},
}


def _read_user_settings() -> dict:
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as file:
            settings = json.load(file)
        return settings if isinstance(settings, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _merge_settings(defaults: dict, overrides: dict) -> dict:
    """Deep-merge valid user values over defaults, preserving extra JSON keys."""
    merged = deepcopy(defaults)
    for key, value in overrides.items():
        if key not in defaults:
            merged[key] = deepcopy(value)
            continue

        default = defaults[key]
        if isinstance(default, dict):
            merged[key] = (
                _merge_settings(default, value)
                if isinstance(value, dict)
                else deepcopy(default)
            )
        elif isinstance(default, list):
            merged[key] = deepcopy(value) if isinstance(value, list) else deepcopy(default)
        elif default is None:
            merged[key] = deepcopy(value)
        elif isinstance(default, bool):
            merged[key] = value if isinstance(value, bool) else default
        elif isinstance(default, int):
            merged[key] = value if isinstance(value, int) and not isinstance(value, bool) else default
        elif isinstance(default, float):
            merged[key] = value if isinstance(value, (int, float)) and not isinstance(value, bool) else default
        else:
            merged[key] = value if isinstance(value, type(default)) else default
    return merged


def _apply_updates(settings: dict, updates: dict) -> None:
    """Apply persisted values without filtering their types or precision."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            _apply_updates(settings[key], value)
        else:
            settings[key] = deepcopy(value)


def load_settings() -> dict:
    """Return defaults recursively overlaid by settings.json values."""
    with _SETTINGS_LOCK:
        return _merge_settings(DEFAULT_SETTINGS, _read_user_settings())


def update_settings(updates: dict) -> None:
    """Merge user changes into the file and atomically save it."""
    if not isinstance(updates, dict):
        raise TypeError("Settings updates must be a dictionary")

    with _SETTINGS_LOCK:
        settings = _read_user_settings()
        _apply_updates(settings, updates)

        temporary_file = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".tmp")
        try:
            with temporary_file.open("w", encoding="utf-8") as file:
                json.dump(settings, file, indent=4, ensure_ascii=False)
            temporary_file.replace(SETTINGS_FILE)
        finally:
            if temporary_file.exists():
                temporary_file.unlink()
