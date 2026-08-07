"""Register the bundled dashboard adapter with LabData."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile


PLUGIN_NAME = "chipmunk_dashboard_plugin"


def _preferences_path() -> Path:
    labdata_path = os.environ.get("LABDATA_PATH")
    root = Path(labdata_path) if labdata_path else Path.home() / "labdata"
    return root / "user_preferences.json"


def _plugin_path() -> Path:
    return Path(__file__).with_name("labdata_plugin").resolve()


def _write_preferences(path: Path, preferences: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(preferences, stream, indent=2)
            stream.write("\n")
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def register_labdata_plugin(
    preferences_path: str | Path | None = None,
    plugin_path: str | Path | None = None,
) -> tuple[Path, bool]:
    """Add the bundled adapter to LabData preferences.

    Returns the preferences path and whether its contents changed. Existing
    plugins, including the full Chipmunk schema plugin, are left untouched.
    """
    preferences_file = (
        Path(preferences_path) if preferences_path else _preferences_path()
    )
    adapter_path = Path(plugin_path).resolve() if plugin_path else _plugin_path()
    if not (adapter_path / "__init__.py").is_file():
        raise FileNotFoundError(f"LabData plugin adapter not found: {adapter_path}")

    if preferences_file.exists():
        preferences = json.loads(preferences_file.read_text(encoding="utf-8"))
        if not isinstance(preferences, dict):
            raise ValueError(
                f"LabData preferences must contain a JSON object: {preferences_file}"
            )
    else:
        preferences = {}

    plugins = preferences.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise ValueError(
            f"LabData preferences['plugins'] must be an object: {preferences_file}"
        )

    adapter_value = str(adapter_path)
    changed = plugins.get(PLUGIN_NAME) != adapter_value
    if changed:
        plugins[PLUGIN_NAME] = adapter_value
        _write_preferences(preferences_file, preferences)
    return preferences_file, changed
