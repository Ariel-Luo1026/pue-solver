"""Validate Configuration Library equipment workbook alias resolution."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from configuration_library_loader import (  # noqa: E402
    DEFAULT_LIBRARY_ROOT,
    _records,
    load_equipment_aliases,
    read_xlsx_sheets,
    resolve_equipment_alias,
)

VALID_CURVE_SHEETS = ("Solver_Curve", "Solver_Curve_Normal", "Solver_Curve_Failure", "Solver", "Performance_Map")


def validate_configuration_library(library_root=None):
    root = Path(library_root) if library_root else DEFAULT_LIBRARY_ROOT
    aliases = load_equipment_aliases()
    results = []
    if not root.is_dir():
        return [{
            "configuration": None,
            "equipment_id": None,
            "resolved_id": None,
            "status": "error",
            "message": f"Configuration Library root missing: {root}",
        }]

    for configuration_dir in sorted(child for child in root.iterdir() if child.is_dir()):
        configuration_workbook = configuration_dir / "configuration.xlsx"
        if not configuration_workbook.is_file():
            continue
        try:
            configuration_sheets = read_xlsx_sheets(configuration_workbook)
            equipment_rows = _records(configuration_sheets.get("Equipment_List", []))
        except Exception as exc:
            results.append({
                "configuration": configuration_dir.name,
                "equipment_id": None,
                "resolved_id": None,
                "status": "error",
                "message": f"Could not read configuration.xlsx: {exc}",
            })
            continue

        for row in equipment_rows:
            equipment_id = str(row.get("Equipment") or "").strip()
            resolved_id = resolve_equipment_alias(equipment_id, aliases)
            workbook = configuration_dir / "equipment" / resolved_id / f"{resolved_id}.xlsx"
            alias_used = resolved_id != equipment_id
            if not workbook.is_file():
                results.append({
                    "configuration": configuration_dir.name,
                    "equipment_id": equipment_id,
                    "resolved_id": resolved_id,
                    "status": "error",
                    "message": f"Missing workbook: {workbook}",
                    "alias_used": alias_used,
                })
                continue
            try:
                sheets = read_xlsx_sheets(workbook)
            except Exception as exc:
                results.append({
                    "configuration": configuration_dir.name,
                    "equipment_id": equipment_id,
                    "resolved_id": resolved_id,
                    "status": "error",
                    "message": f"Could not read workbook: {exc}",
                    "alias_used": alias_used,
                })
                continue
            curve_sheets = [
                sheet_name
                for sheet_name in VALID_CURVE_SHEETS
                if sheet_name in sheets and _records(sheets.get(sheet_name, []))
            ]
            if not curve_sheets:
                results.append({
                    "configuration": configuration_dir.name,
                    "equipment_id": equipment_id,
                    "resolved_id": resolved_id,
                    "status": "error",
                    "message": "Missing valid Solver_Curve, scenario Solver_Curve, Solver, or Performance_Map rows.",
                    "alias_used": alias_used,
                    "workbook": str(workbook),
                    "available_sheets": list(sheets),
                })
                continue
            results.append({
                "configuration": configuration_dir.name,
                "equipment_id": equipment_id,
                "resolved_id": resolved_id,
                "status": "ok",
                "message": f"Resolved workbook with curve sheets: {', '.join(curve_sheets)}",
                "alias_used": alias_used,
                "workbook": str(workbook),
                "curve_sheets": curve_sheets,
            })
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", default=None, help="Path to the Configuration Library root.")
    args = parser.parse_args(argv)
    results = validate_configuration_library(args.library_root)
    errors = [item for item in results if item["status"] != "ok"]
    for item in results:
        alias_note = " alias" if item.get("alias_used") else ""
        print(
            f"[{item['status'].upper()}]{alias_note} "
            f"{item.get('configuration') or '-'} "
            f"{item.get('equipment_id') or '-'} -> {item.get('resolved_id') or '-'}: "
            f"{item['message']}"
        )
    print(f"Validated {len(results)} equipment bindings; errors={len(errors)}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
