# chipmunk-dashboard

A Plotly Dash interface for visualizing mouse behavioral data from the `chipmunk` task using `labdata`.

## Prerequisites

1. **VPN**: You must be connected to the lab network/VPN to access the DataJoint database.
2. **Conda**

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

Copy the chipmunk folder to the `plugins` folder in your local `labdata` directory:
```bash
git clone https://github.com/churchlandlab/chipmunk.git
cd chipmunk
cp . ~/labdata/plugins/
```

### Option 2: Pip Installation

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

## Updating Your Environment

If the environment.yml file is updated in the repository:

```bash
git pull
conda env update -f environment.yml --prune
```

To update to the latest commit on main:

```bash
cd chipmunk-dashboard
git switch main
git pull origin main
conda env update -f environment.yml --prune
```
