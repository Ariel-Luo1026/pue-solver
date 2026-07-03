# Excel Replicated Hourly Mode 8760-Hour Audit

Status: PASS

Workbook: `C:\Users\Ariel\Downloads\Annual_PUE_detailed_calculation_JUNO Field.xlsx`
Program hourly export: `C:\ArielLuoProjectspue-solver\pue-solver-main\audit_outputs\excel_replicated_hourly_program_results.csv`
ACC factor comparison export: `C:\ArielLuoProjectspue-solver\pue-solver-main\audit_outputs\excel_replicated_hourly_acc_factor_comparison.csv`

## Located Excel formulas

- Sheet `05_Appendix01`, range `F31:F8790`: outdoor dry-bulb cached hourly values; no formulas in sampled data cells.
- Sheet `05_Appendix01`, range `H31:H8790`: ACC hourly factor formula.
- Sheet `05_Appendix01`, range `I31:I8790`: separate clamped factor; not used by current hourly ACC power.
- Sheet `05_Appendix01`, range `J31:J8790`: cubic factor based on I; not used by current hourly ACC power.
- Sheet `05_Appendix01`, range `K31:K8790`: H / annual hours; contributes to cumulative annual ACC factor only.
- Sheet `05_Appendix01`, range `L31:L8790`: J / annual hours; separate cumulative factor, not ACC power.
- Sheet `05_Appendix01`, range `M31:M8790`: cumulative sum of K.
- Sheet `05_Appendix01`, range `N31:N8790`: cumulative sum of L.

- `H31` formula='$B$9*($B$11+(1-$B$11)*MIN(1,MAX(0,(F31-$B$10)/($B$8-$B$10))))', attrs={'t': 'shared', 'ref': 'H31:H94', 'si': '8'}, cached value=0.34290000000000004
- `I31` formula='MAX($B$12,MIN(1,MAX(0,(F31-$B$13)/($B$8-$B$13))))', attrs={'t': 'shared', 'ref': 'I31:I94', 'si': '9'}, cached value=0.2
- `J31` formula='$B$9*I31^3', attrs={'t': 'shared', 'ref': 'J31:J94', 'si': '10'}, cached value=0.0072000000000000015
- `K31` formula='H31/$B$5', attrs={'t': 'shared', 'ref': 'K31:K94', 'si': '11'}, cached value=3.914383561643836e-05
- `L31` formula='J31/$B$5', attrs={'t': 'shared', 'ref': 'L31:L94', 'si': '12'}, cached value=8.219178082191783e-07
- `M31` formula='SUM($K$31:K31)', attrs={}, cached value=3.914383561643836e-05
- `N31` formula='SUM($L$31:L31)', attrs={}, cached value=8.219178082191783e-07
- `H8790` formula=None, attrs={'t': 'shared', 'si': '688'}, cached value=0.8377837226277371
- `I8790` formula=None, attrs={'t': 'shared', 'si': '689'}, cached value=0.8951576062128825
- `J8790` formula=None, attrs={'t': 'shared', 'si': '690'}, cached value=0.6455665631237232
- `K8790` formula=None, attrs={'t': 'shared', 'si': '691'}, cached value=9.56374112588741e-05
- `L8790` formula=None, attrs={'t': 'shared', 'si': '692'}, cached value=7.369481314197753e-05
- `M8790` formula='SUM($K$31:K8790)', attrs={}, cached value=0.5301997383761575
- `N8790` formula='SUM($L$31:L8790)', attrs={}, cached value=0.10863187136291992

## ACC factor 8760 comparison statistics

- Maximum absolute error: 0
- Mean absolute error: 0
- RMSE: 0
- Number of mismatched hours: 0
- Largest mismatch hour: 1
- Largest mismatch value: 0

## Annual and peak checks

| Metric | Excel | Program | Difference |
|---|---:|---:|---:|
| Annual ACC Energy kWh | 5016113.6848291755 | 5016113.6848291969 | 2.1420419216156006e-08 |
| Annual Facility Energy kWh | 42772191.781256773 | 42772191.781256795 | 2.2351741790771484e-08 |
| Annual PUE | 1.2329975491575795 | 1.2329975491575802 | 6.6613381477509392e-16 |
| Peak Facility Hour | 8586 | 8586 | 0 |
| Peak Facility Power kW | 5216.2271130947056 | 5216.2271130947056 | 0 |
| Peak Hourly PUE | 1.3172290689633095 | 1.3172290689633095 | 0 |

## Source lines reviewed

- `pue-solver-main/acc_excel_benchmark.py:225`: `compute_acc_excel_replicated_hourly`.
- `pue-solver-main/acc_excel_benchmark.py:242-252`: replicated H-column factor using B8/B10/B11 and IT annual factor B9.
- `pue-solver-main/acc_excel_benchmark.py:252-259`: ACC power and electrical-loss ordering.
- `pue-solver-main/ui.js:4869`: Pyodide call dispatches to `compute_acc_excel_replicated_hourly(dc)` for this mode.

## Conclusion

The audited Normal scenario is a 1:1 replication of the workbook ACC hourly factor. Annual energy differences are only 2e-08 kWh order floating-point summation noise and are within floating-point precision; annual PUE and peak metrics match.
