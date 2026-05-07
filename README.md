# PUE Solver Dev

Browser-based data center PUE and thermal-source simulation platform.

Built with:

- Pyodide (Python running in browser)
- VS Code + Live Server
- Curve-driven equipment models
- Interactive COP / UPS editors

---

# Overview

PUE Solver Dev is an engineering-oriented simulation sandbox for:

- Predictive PUE analysis
- Data center cooling architecture studies
- Liquid + air hybrid cooling research
- Chiller COP sensitivity studies
- Thermal source decomposition
- Future transient / dynamic thermal modeling

The project runs entirely in the browser using Pyodide and does not require a backend server.

---

# Features

## Thermal Source Architecture

Cooling load is dynamically assembled from:

- Liquid-cooled IT load
- Air-cooled IT load
- Pump heat
- Airflow / fan heat
- Lighting heat
- Envelope heat
- Infiltration heat
- Miscellaneous heat sources

---

## Curve-Driven Equipment Models

### UPS Efficiency Curves

- 1D interpolation
- PCHIP / linear support
- Interactive editing
- Real-time response

### Chiller COP Surfaces

- 2D COP interpolation
- PLR × OAT driven
- Interactive visualization
- Multi-chiller support

---

## Equipment Models

### Chillers

```text
Power = Cooling_Load / COP(PLR, OAT)
Pumps / Fans
Power = Rated × speed_ratio³

(VFD affinity-law approximation)

Technology Stack
HTML + JavaScript
        ↓
Pyodide Runtime
        ↓
solver.py
        ↓
PUE / Thermal Simulation
Project Structure
pue-solver-main/
│
├── index.html
├── ui.js
├── editor.js
├── solver.py
├── curves.json
└── README.md
Main Components
solver.py

Core simulation engine.

Contains:

PUE calculation
Cooling load assembly
Equipment power models
COP surface interpolation
Multi-chiller load allocation
Thermal source decomposition
curves.json

Curve library.

Contains:

UPS efficiency curves
Chiller COP surfaces

Example:

{
  "UPS_EFF_1": {
    "method": "pchip",
    "points": [
      [0.2, 0.94],
      [0.5, 0.96],
      [1.0, 0.955]
    ]
  }
}
editor.js

Interactive engineering curve editor.

Supports:

Point dragging
Real-time curve preview
COP surface visualization
Curve export / import
ui.js

Frontend runtime controller.

Responsible for:

Loading Pyodide
Executing solver.py
Passing JSON input
Displaying logs and outputs
Installation
1. Install VS Code

https://code.visualstudio.com/

2. Install Live Server Extension

Extension:

Live Server
Author: Ritwick Dey
3. Open Project Folder

Open the entire folder:

pue-solver-main

Do NOT open only index.html.

4. Launch

Right click:

index.html → Open with Live Server

Browser should open:

http://127.0.0.1:5500
Development Workflow
Modify Logic

Edit:

solver.py

Save → browser auto refresh → Run.

Modify Curves

Edit:

curves.json
or use the interactive editor

Save → Run.

GitHub Workflow
Initial Setup
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin <repo-url>
git push -u origin main --force
Normal Update
git add .
git commit -m "update"
git push
Current Cooling Logic
Total Cooling Load
Cooling Load =
IT Liquid Heat
+ IT Air Heat
+ Pump Heat
+ Airflow Heat
+ Lighting Heat
+ Envelope Heat
+ Infiltration Heat
+ Misc Heat
Example Input
"cooling": {
  "it_heat_split": {
    "liquid_cooling_it_kw": 900,
    "air_cooling_it_kw": 500
  },

  "heat_sources": {
    "pumps_kw": null,
    "airflow_kw": null,
    "lighting_kw": null,
    "people_kw": 0,
    "infiltration_kw": 0,
    "envelope_kw": 0,
    "misc_kw": 0
  }
}
Current Version
v0.4.1

Includes:

Liquid / air IT split
Cooling heat-source assembly
Multi-chiller load allocation
Curve-driven COP evaluation
Browser-based Python execution
Interactive engineering curve editor
Roadmap
v0.4.2
Cooling tower models
Dry cooler models
Ambient derating
Fan curve integration
v0.5
CDU models
Waterside economizer
Hybrid cooling topology
Liquid cooling loop expansion
Future
Dynamic PUE(t)
Thermal transient simulation
PDE-based thermal transport
CFD coupling
Digital twin integration
AI surrogate models
Notes

This project is intended for:

Data center thermal architecture studies
Predictive PUE analysis
Cooling optimization workflows
Liquid-air hybrid cooling research

Not intended for:

Compliance certification
Utility billing
Production BMS replacement
License

Internal development / research use.
