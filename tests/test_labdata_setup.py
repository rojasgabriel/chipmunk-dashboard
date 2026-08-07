import json

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
