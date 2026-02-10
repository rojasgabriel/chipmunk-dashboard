# chipmunk-dashboard

A web dashboard for visualizing chipmunk behavioral data using `labdata2`.

## Install

```bash
pip install -e .
```

## Usage

```bash
chipmunk-dashboard run              # http://localhost:8050
chipmunk-dashboard run --port 9000  # custom port
chipmunk-dashboard run --debug      # hot-reload on code changes
```

## Features

- **Subject selector** — multi-select subjects to overlay on the same plots
- **Session picker** — choose which session to inspect (psychometric curves, reaction times)
- **Sessions-back slider** — control how many recent sessions appear in cross-session analyses
- Interactive Plotly charts: fraction correct, P(right), reaction times, performance, early-withdrawal rate, trial counts
