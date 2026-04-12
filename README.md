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

# Installs dependencies on a venv initialized with `uv run ...`
uv sync # "--group dev" for developing
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
