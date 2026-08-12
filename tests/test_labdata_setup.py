import json
import sys
import types
from pathlib import Path

from chipmunk_dashboard.labdata_setup import register_labdata_plugin


def test_register_labdata_plugin_preserves_existing_plugins(tmp_path):
    preferences_path = tmp_path / "labdata" / "user_preferences.json"
    preferences_path.parent.mkdir()
    preferences_path.write_text(
        json.dumps(
            {
                "database": {"database.name": "lab_data"},
                "plugins": {"chipmunk": "/old/plugin"},
            }
        ),
        encoding="utf-8",
    )
    plugin_path = tmp_path / "adapter"
    plugin_path.mkdir()
    (plugin_path / "__init__.py").write_text(
        "dashboard_name = '**Chipmunk**'\n", encoding="utf-8"
    )

    path, changed = register_labdata_plugin(preferences_path, plugin_path)

    preferences = json.loads(path.read_text(encoding="utf-8"))
    assert path == preferences_path
    assert changed is True
    assert preferences["database"]["database.name"] == "lab_data"
    assert preferences["plugins"] == {
        "chipmunk": "/old/plugin",
        "chipmunk_dashboard_plugin": str(plugin_path.resolve()),
    }


def test_register_labdata_plugin_is_idempotent(tmp_path):
    preferences_path = tmp_path / "user_preferences.json"
    plugin_path = tmp_path / "adapter"
    plugin_path.mkdir()
    (plugin_path / "__init__.py").write_text("", encoding="utf-8")

    register_labdata_plugin(preferences_path, plugin_path)
    path, changed = register_labdata_plugin(preferences_path, plugin_path)

    assert path == preferences_path
    assert changed is False


def test_bundled_adapter_exports_labdata_dashboard_contract():
    from chipmunk_dashboard import labdata_plugin

    assert labdata_plugin.dashboard_name == "**Chipmunk**"
    assert callable(labdata_plugin.dashboard_function)


def test_ensure_bundled_package_prefers_adapter_tree_over_other_install(
    tmp_path, monkeypatch
):
    from chipmunk_dashboard import labdata_plugin

    other_root = tmp_path / "other-site"
    other_pkg = other_root / "chipmunk_dashboard"
    other_pkg.mkdir(parents=True)
    other_init = other_pkg / "__init__.py"
    other_init.write_text("", encoding="utf-8")

    stale = types.ModuleType("chipmunk_dashboard")
    stale.__file__ = str(other_init)
    monkeypatch.setitem(sys.modules, "chipmunk_dashboard", stale)
    monkeypatch.setattr(sys, "path", [str(other_root), *sys.path])

    package_dir = labdata_plugin.ensure_bundled_package()

    assert package_dir == Path(labdata_plugin.__file__).resolve().parent.parent
    assert sys.path[0] == str(package_dir.parent)
    assert (
        "chipmunk_dashboard" not in sys.modules
        or labdata_plugin._module_is_from_bundled_tree(
            sys.modules["chipmunk_dashboard"]
        )
    )

    import chipmunk_dashboard

    assert Path(chipmunk_dashboard.__file__).resolve().is_relative_to(package_dir)
