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
