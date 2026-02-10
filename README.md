# chipmunk-dashboard

A Plotly Dash interface for visualizing mouse behavioral data from the `chipmunk` task.

## Prerequisites

1.  **VPN**: You must be connected to the lab network/VPN to access the DataJoint database.
2.  **Environment**: Ensure `labdata` and the `chipmunk` schema libraries are installed in your Python environment.

## Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard
pip install -e .
```

## Running the Dashboard

Start the server:

```bash
chipmunk-dashboard run
```

Open your browser to [http://localhost:8050](http://localhost:8050).

**Options:**

```bash
chipmunk-dashboard run --port 9000  # Run on a specific port
chipmunk-dashboard run --debug      # Enable hot-reloading for development
```

## Features

- **Multi-Subject Comparison**: Select multiple subjects to overlay performance metrics.
- **Session Inspector**: Deep dive into specific sessions (Psychometric curves, Response times, Wait times).
- **Longitudinal Tracking**: Visualize performance trends, bias, and water intake across recent sessions.
- **Auto-Refresh**: Dashboard updates automatically every 5 minutes during experiments.
