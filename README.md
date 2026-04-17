# chipmunk-dashboard

A Plotly Dash interface for visualizing mouse behavioral data from the `chipmunk` task using `labdata`.

## Prerequisites

1. **VPN**: You must be connected to the lab network/VPN to access our database.
2. **Chipmunk plugin**: Ensure the [chipmunk plugin](https://github.com/churchlandlab/chipmunk/tree/labdata) is in your labdata plugins folder.
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) for package and env management.

## Installation

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard

# Install runtime + development dependencies (matches local dev and CI toolchain)
uv sync --all-groups
```

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

## Running the Dashboard

To start the server **while inside the `chipmunk-dashboard` folder**:

```bash
# Run with defaults (localhost:8050)
uv run chipmunk-dashboard run

# Run on a specific port
uv run chipmunk-dashboard run --port 9000

# Enable hot-reloading for development
uv run chipmunk-dashboard run --debug
```

## Remote Access

On a remote machine:

```bash
uv run chipmunk-dashboard run --host 0.0.0.0 --port XXXX
```

On your local machine, type `<remote-ip-or-hostname>:XXXX` in your browser.
