# PUE Solver Dev

Browser-based data center PUE and thermal-source simulation platform.

Built with:

- Pyodide (Python in browser)
- VS Code + Live Server
- Curve-driven equipment models
- Interactive COP / UPS editors

---

## Features

### Thermal Source Architecture
Cooling load is dynamically assembled from:

- Liquid-cooled IT load
- Air-cooled IT load
- Pump heat
- Airflow / fan heat
- Lighting heat
- Envelope / infiltration / misc heat

---

### Curve-Driven Equipment Models

#### UPS Efficiency Curves
- 1D interpolation
- PCHIP / linear support
- Interactive editing

#### Chiller COP Surfaces
- 2D COP surface interpolation
- PLR × OAT driven
- Real-time visualization

---

### Equipment Models

#### Chillers
```text
Power = Cooling_Load / COP(PLR, OAT)

Stack
HTML + JavaScript
        ↓
Pyodide Runtime
        ↓
solver.py
        ↓
PUE / Thermal Simulation
