"""labdata dashboard adapter bundled with chipmunk-dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

dashboard_name = "**Chipmunk**"

# Directory of the chipmunk_dashboard package that owns this adapter.
_PACKAGE_DIR = Path(__file__).resolve().parent.parent
# Parent that must be on sys.path so `import chipmunk_dashboard` resolves here.
_IMPORT_ROOT = _PACKAGE_DIR.parent


def _module_is_from_bundled_tree(module: object) -> bool:
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return False
    try:
        return Path(module_file).resolve().is_relative_to(_PACKAGE_DIR)
    except (OSError, ValueError):
        return False


def ensure_bundled_package() -> Path:
    """Make imports resolve to this adapter's package tree.

    labdata loads this adapter by filesystem path from user preferences, then the
    adapter imports ``chipmunk_dashboard``. If another install is already on
    ``sys.path`` (or already in ``sys.modules``), that older copy wins — so the
    standalone Dash app can show a fix while ``labdata dashboard`` still shows
    the previous behavior. Prefer the tree that registered this adapter.
    """
    root = str(_IMPORT_ROOT)
    while root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)

    for name in list(sys.modules):
        if name != "chipmunk_dashboard" and not name.startswith("chipmunk_dashboard."):
            continue
        module = sys.modules[name]
        if not _module_is_from_bundled_tree(module):
            del sys.modules[name]

    return _PACKAGE_DIR


def dashboard_function(schema=None):
    """Render the Chipmunk dashboard inside labdata's Streamlit app."""
    ensure_bundled_package()
    from chipmunk_dashboard.streamlit_page import render_dashboard

    return render_dashboard(schema=schema)
