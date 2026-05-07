PUE Solver Dev v0.4.1
A browser-based data center PUE / thermal source simulation platform built with:


Pyodide (Python running in browser)


VS Code + Live Server


Curve-driven equipment models


Interactive COP / UPS curve editors


Heat-source-based cooling load architecture


This project is designed for:


Data center energy prediction


PUE / pPUE / ERE studies


Liquid + air cooling architecture analysis


Chiller COP sensitivity studies


Dry cooler / cooling tower future integration


CFD / thermal digital twin workflow integration



Current Version
v0.4.1 Features
PUE Core


Instant PUE calculation


Partial PUE (pPUE)


ERE placeholder structure


Facility power breakdown


Curve-Driven Equipment


UPS efficiency curves (1D)


Chiller COP surfaces (2D)


Interactive curve editing


PCHIP / linear interpolation


Cooling Heat Source Architecture
Cooling load is no longer assumed to equal IT load.
Cooling load is dynamically assembled from:


Liquid-cooled IT heat


Air-cooled IT heat


Pump heat


Airflow / fan heat


Lighting heat


Envelope / infiltration / misc heat


Chiller Allocation
Supports:


Multiple chillers


Capacity-based load sharing


Curve-based COP evaluation


Browser-Based Development
No backend required.
Runs entirely in browser using:


HTML


JavaScript


Python (Pyodide)



Project Structure
pue-solver-main/│├── index.html├── ui.js├── editor.js├── solver.py├── curves.json├── README.md

Main Components
solver.py
Core PUE / thermal calculation engine.
Contains:


PUE calculation


Equipment power models


COP surface interpolation


Heat source assembly


Chiller load allocation



curves.json
Curve library.
Contains:


UPS efficiency curves


Chiller COP surfaces


Example:
"UPS_EFF_1": {  "method": "pchip",  "points": [    [0.2, 0.94],    [0.5, 0.96],    [1.0, 0.955]  ]}

editor.js
Interactive engineering curve editor.
Supports:


Dragging points


Live preview


COP surface visualization


Export / save curve library



ui.js
Frontend runtime controller.
Responsible for:


Loading Pyodide


Executing solver.py


Passing JSON input


Displaying outputs and logs



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

4. Launch with Live Server
Right-click:
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


or use interactive editor


Save → Run.

GitHub Update
git add .git commit -m "update message"git push

Current Cooling Load Logic
Total Cooling Load
Cooling Load =IT Liquid Heat+ IT Air Heat+ Pump Heat+ Airflow Heat+ Lighting Heat+ Envelope Heat+ Infiltration Heat+ Misc Heat

Current Equipment Models
UPS
Loss = Output / η(load_ratio)
Curve-driven.

Chiller
Power = Cooling_Load / COP(PLR, OAT)
COP is evaluated from:


PLR


Outdoor Air Temperature (OAT)


using interpolated 2D surfaces.

Pumps / Airflow
Current model:
Power = Rated × speed_ratio³
(VFD affinity-law approximation)

Example Input
"cooling": {  "it_heat_split": {    "liquid_cooling_it_kw": 900,    "air_cooling_it_kw": 500  },  "heat_sources": {    "pumps_kw": null,    "airflow_kw": null,    "lighting_kw": null,    "people_kw": 0,    "infiltration_kw": 0,    "envelope_kw": 0,    "misc_kw": 0  }}

Planned Roadmap
v0.4.2


Cooling tower VFD model


Dry cooler fan model


Ambient derating


v0.5


CDU model


Waterside economizer


Free cooling logic


Hybrid cooling topology


v0.6


Dynamic PUE(t)


Thermal storage coupling


Transient cooling simulation


Future


CFD coupling


Digital twin integration


PDE-based thermal transport


AI surrogate models



Notes
This project is intended as an engineering-oriented simulation sandbox for:


thermal architecture exploration


cooling system optimization


predictive PUE analysis


liquid-air hybrid cooling research


Not intended for:


utility billing


compliance certification


production BMS replacement



License
Internal development / research use.
