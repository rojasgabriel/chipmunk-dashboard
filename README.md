# chipmunk-dashboard

A Plotly Dash interface for visualizing mouse behavioral data from the `chipmunk` task using `labdata`.

## Prerequisites

1. **VPN**: You must be connected to the lab network/VPN to access our database.
2. `labdata` and this package must share the **same Python environment**. The
   `labdata` tab imports `chipmunk_dashboard`, so a bare `labdata` from another
   env will not see the install.

## Installation

Install into the same environment that already has `labdata`, then register the
bundled adapter in `~/labdata/user_preferences.json`:

```bash
pip install "chipmunk-dashboard @ git+https://github.com/rojasgabriel/chipmunk-dashboard.git"
chipmunk-dashboard install-labdata
```

Then start `labdata` as usual:

```bash
labdata dashboard
```

That registers a native **Chipmunk** page in the Streamlit sidebar. The
separate Chipmunk `labdata` schema plugin is still needed on machines that
ingest raw Chipmunk files; this package supplies the dashboard tab itself.

If you install into a different environment later, run
`chipmunk-dashboard install-labdata` again from that environment before
starting `labdata`.

### Optional: local checkout with uv

For development or tighter env control, use [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard
uv sync --all-groups
uv run chipmunk-dashboard install-labdata
```

With that project env active, `labdata dashboard` is enough. Use
`uv run labdata dashboard` only when you want to force the project `.venv`
without activating it.

## Development verification

```bash
# Quick local loop
uv run ruff check .
uv run pytest -q tests/test_cli.py

# Pre-PR / CI-parity checks (minus browser install)
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90

# Optional browser UI regression checks (opt-in)
RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py
```

## Running the standalone Dash app

```bash
# Run with defaults (localhost:8050)
uv run chipmunk-dashboard run

# Run on a specific port
uv run chipmunk-dashboard run --port 9000

# Enable hot-reloading for development
uv run chipmunk-dashboard run --debug
```

The Streamlit `labdata` page reuses the same figure renderers (Overview, Timing,
Multi Session). The standalone Dash app remains a separate entry point.

## Remote Access

On a remote machine:

```bash
uv run chipmunk-dashboard run --host 0.0.0.0 --port XXXX
```

On your local machine, type `<remote-ip-or-hostname>:XXXX` in your browser.
