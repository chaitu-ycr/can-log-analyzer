# CAN Log Analyzer

A web-based tool for analyzing CAN log files using NiceGui, Plotly, and cantools.

## Features

- Upload and parse CAN log files (`.asc`, `.blf`)
- Load CAN database files (`.dbc`)
- Visualize and plot selected CAN signals interactively
- User-friendly web interface with sidebar controls
- Interactive signal selection and customizable plots (scatter, line, heatmap)
- Grid and axis customization for detailed analysis

## Notes

- Ensure you are using Python >= 3.10 as specified in the project requirements.
- Only `.dbc` files are supported for CAN database input.

## Usage - Web App

To start the web application, run:

```powershell
python -m can_log_analyzer.run_web_app
```

- The app will launch in your default web browser at `http://localhost:8501` (unless otherwise configured).
- Use the sidebar to upload your CAN log files (`.asc`, `.blf`) and CAN database files (`.dbc`).
- Select channels, messages, and signals to visualize.
- Choose plot type and customize grid/axis options as needed.
- Interactive plots and analysis will be available after loading your files.

## [source manual](https://chaitu-ycr.github.io/can-log-analyzer/source-manual/)
