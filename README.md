# chipmunk-dashboard

A Plotly Dash interface for visualizing mouse behavioral data from the `chipmunk` task using `labdata`.

## Prerequisites

1. **VPN**: You must be connected to the lab network/VPN to access our database.
2. **Chipmunk plugin**: Ensure the [chipmunk plugin](https://github.com/churchlandlab/chipmunk/tree/labdata) is in your labdata plugins folder.
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) for package and env management.

## Installation

First install . Then...

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard

#this will install all the dependencies on a venv that is initialized when you do `uv run ...`
uv sync
```

## Running the Dashboard

To start the server **while inside the `chipmunk-dashboard` folder**:

```bash
uv run chipmunk-dashboard run
uv run chipmunk-dashboard run --port 9000  # Run on a specific port
uv run chipmunk-dashboard run --debug      # Enable hot-reloading for development
```

## Remote Access

On the remote machine, listen on all interfaces:

```bash
uv run chipmunk-dashboard run --host 0.0.0.0 --port XXXX
```

On your local machine, browse to `http://<remote-ip-or-hostname>:XXXX`.
