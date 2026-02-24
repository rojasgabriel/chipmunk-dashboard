# chipmunk-dashboard

A Plotly Dash interface for visualizing mouse behavioral data from the `chipmunk` task using `labdata`.

## Prerequisites

1. **VPN**: You must be connected to the lab network/VPN to access the DataJoint database.
2. **Conda**: Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution) if you don't have it.

## Installation

### Option 1: Conda Environment (Recommended)

Clone the repository and create the conda environment:

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard
conda env create -f environment.yml
conda activate chipmunk-dashboard
```

For development, install the package in editable mode:

```bash
pip install -e .
```

**Note**: If you need the chipmunk plugin (optional), install it manually:
```bash
git clone https://github.com/churchlandlab/chipmunk.git
cd chipmunk
git checkout labdata
# Follow installation instructions from chipmunk repository
```

### Option 2: Pip Installation (Legacy)

Install in editable mode with pip:

```bash
pip install -e .
```

**Important**: This method requires manual installation of dependencies. Ensure you have compatible versions, especially `datajoint<2.0`.

## Running the Dashboard

Start the server:

```bash
chipmunk-dashboard run
```

Open your browser to `http://localhost:8050`.

**Options:**

```bash
chipmunk-dashboard run --port 9000  # Run on a specific port
chipmunk-dashboard run --debug      # Enable hot-reloading for development
```

## Remote Access

**On the remote machine**, listen on all interfaces:

```bash
chipmunk-dashboard run --host 0.0.0.0 --port 8050
```

**On your local machine**, browse to `http://<remote-ip-or-hostname>:8050`.

## Features

- **Multi-Subject Comparison**: Select multiple subjects to overlay performance metrics.
- **Session Inspector**: Deep dive into specific sessions (Psychometric curves, Response times, Wait times).
- **Longitudinal Tracking**: Visualize performance trends, bias, and water intake across recent sessions.
- **Auto-Refresh**: Dashboard updates automatically every 5 minutes during experiments.

## Known issues

- This does not work if your `datajoint` version is `>2.0`. It was developed and currently works in `0.14.1`.

## Updating Your Environment

If the environment.yml file is updated in the repository:

```bash
git pull
conda env update -f environment.yml --prune
```

To update to the latest commit on main:

```bash
cd chipmunk-dashboard
git checkout main
git pull origin main
conda env update -f environment.yml --prune
```
