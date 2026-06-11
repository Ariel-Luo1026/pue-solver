#!/usr/bin/env python3
"""Build the local EPW city index for the PUE Solver UI.

Scans pue-solver-main/data/epw/**/*.epw, reads each EPW LOCATION line, and
generates:
  - pue-solver-main/data/epw_index.json
  - pue-solver-main/data/epw_inventory.md

The script preserves manually added aliases from the existing index.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "pue-solver-main"
EPW_DIR = UI_ROOT / "data" / "epw"
INDEX_PATH = UI_ROOT / "data" / "epw_index.json"
INVENTORY_PATH = UI_ROOT / "data" / "epw_inventory.md"


COUNTRY_NAMES = {
    "CHN": "China",
    "CHINA": "China",
    "FRA": "France",
    "FRANCE": "France",
    "JPN": "Japan",
    "JAPAN": "Japan",
    "SGP": "Singapore",
    "SINGAPORE": "Singapore",
    "USA": "United States",
    "UNITED STATES": "United States",
    "GBR": "United Kingdom",
    "UK": "United Kingdom",
    "DEU": "Germany",
    "GERMANY": "Germany",
    "IND": "India",
    "INDIA": "India",
    "AUS": "Australia",
    "AUSTRALIA": "Australia",
    "CAN": "Canada",
    "CANADA": "Canada",
}


STATION_SUFFIXES = {
    "AB",
    "AP",
    "APT",
    "AIRPORT",
    "INTL",
    "INTERNATIONAL",
    "METEOROLOGICAL",
    "OBSERVATORY",
    "STATION",
}


def read_existing_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        return {}
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    existing = {}
    if not isinstance(data, list):
        return existing
    for item in data:
        if not isinstance(item, dict):
            continue
        key = item.get("epw_file") or Path(str(item.get("epw_path", ""))).name
        if key:
            existing[key] = item
    return existing


def first_line(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return handle.readline().strip()


def parse_location(line: str) -> dict | None:
    row = next(csv.reader([line]))
    if len(row) < 10 or row[0].strip().upper() != "LOCATION":
        return None
    station = row[1].strip()
    state = row[2].strip()
    country_raw = row[3].strip()
    source = row[4].strip()
    wmo = row[5].strip()
    lat = to_float(row[6])
    lon = to_float(row[7])
    tz = to_float(row[8])
    elevation = to_float(row[9])
    return {
        "station": station,
        "state": state,
        "country_raw": country_raw,
        "country": COUNTRY_NAMES.get(country_raw.upper(), country_raw),
        "source_id": source,
        "wmo": wmo,
        "lat": lat,
        "lon": lon,
        "time_zone": tz,
        "elevation_m": elevation,
    }


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def clean_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace(".", " ").replace("_", " ").strip())


def title_station(value: str) -> str:
    text = clean_token(value)
    text = re.sub(r"\b(AP|AB|APT)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace(" - ", "-")


def infer_city(station: str, filename: str) -> str:
    station_clean = title_station(station)
    if station_clean:
        for sep in ["-", " "]:
            parts = [p for p in station_clean.split(sep) if p]
            if parts:
                first = parts[0].strip()
                if first.upper() not in STATION_SUFFIXES:
                    return first
    stem_parts = re.split(r"[_.-]+", Path(filename).stem)
    for part in stem_parts:
        if part and not part.isdigit() and part.upper() not in STATION_SUFFIXES:
            if len(part) > 2 and part.upper() not in COUNTRY_NAMES:
                return part
    return station_clean or Path(filename).stem


def readable_filename_aliases(filename: str) -> list[str]:
    stem = Path(filename).stem
    aliases = {stem, clean_token(stem), stem.replace(".", "-"), stem.replace(".", " ")}
    parts = [p for p in re.split(r"[_.-]+", stem) if p]
    if len(parts) >= 2:
        aliases.add(" ".join(parts[:2]))
    if len(parts) >= 3:
        aliases.add(" ".join(parts[:3]))
    return sorted(a for a in aliases if a)


def unique_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def data_period(filename: str) -> str:
    stem = Path(filename).stem
    match = re.search(r"(TMYx\.[0-9]{4}-[0-9]{4}|TMY[0-9]?|IWEC[0-9]?|[0-9]{4}-[0-9]{4})", stem, re.IGNORECASE)
    return match.group(1) if match else "N/A"


def ui_relative_path(path: Path) -> str:
    rel = path.relative_to(UI_ROOT).as_posix()
    return f"./{rel}"


def build_entry(path: Path, location: dict, existing: dict | None) -> dict:
    epw_file = path.name
    station = title_station(location["station"])
    city = infer_city(station, epw_file)
    country = location["country"]
    aliases = [
        station,
        city,
        f"{country} {station}" if country and station else "",
        location.get("wmo", ""),
        location.get("source_id", ""),
        *readable_filename_aliases(epw_file),
    ]
    if existing:
        aliases.extend(existing.get("aliases", []))
    entry = {
        "city": city,
        "country": country,
        "aliases": unique_keep_order(aliases),
        "station": station,
        "source": "Local EPW",
        "epw_path": ui_relative_path(path),
        "epw_file": epw_file,
    }
    if location.get("wmo"):
        entry["wmo"] = location["wmo"]
    if location.get("lat") is not None:
        entry["lat"] = location["lat"]
    if location.get("lon") is not None:
        entry["lon"] = location["lon"]
    return entry


def inventory_markdown(entries: list[dict], skipped: list[tuple[Path, str]]) -> str:
    countries = sorted({e.get("country", "") for e in entries if e.get("country")})
    cities = sorted({e.get("city", "") for e in entries if e.get("city")})
    lines = [
        "# EPW Inventory",
        "",
        "This inventory is generated by `tools/build_epw_index.py` from EPW files under `pue-solver-main/data/epw/`.",
        "",
        "## Summary",
        "",
        f"- EPW files scanned into index: {len(entries)}",
        f"- Skipped invalid EPW files: {len(skipped)}",
        f"- Covered countries: {', '.join(countries) if countries else 'N/A'}",
        f"- Covered cities: {', '.join(cities) if cities else 'N/A'}",
        "- Static frontend EPW directory: `pue-solver-main/data/epw/`",
        "- Active index file: `pue-solver-main/data/epw_index.json`",
        "",
        "## Files",
        "",
        "| EPW File | City | Weather Station | Country | Data Period | Static File Path | In epw_index.json |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| `{epw_file}` | {city} | {station} | {country} | {period} | `{path}` | Yes |".format(
                epw_file=entry.get("epw_file", ""),
                city=entry.get("city", ""),
                station=entry.get("station", ""),
                country=entry.get("country", ""),
                period=data_period(entry.get("epw_file", "")),
                path=f"pue-solver-main/{entry.get('epw_path', './').removeprefix('./')}",
            )
        )
    if skipped:
        lines.extend(["", "## Skipped Files", "", "| Path | Reason |", "|---|---|"])
        for path, reason in skipped:
            lines.append(f"| `{path.as_posix()}` | {reason} |")
    lines.extend(
        [
            "",
            "## Maintenance Notes",
            "",
            "To add a new city:",
            "",
            "1. Place the `.epw` file under `pue-solver-main/data/epw/`.",
            "2. Run `python tools/build_epw_index.py` from the repository root.",
            "3. If needed, add local-language aliases manually to `pue-solver-main/data/epw_index.json`.",
            "4. Re-run Auto Match EPW in the browser to test the new city.",
            "",
            "Manual aliases are preserved when this script is run again.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    existing = read_existing_index()
    entries = []
    skipped = []
    epw_files = sorted(EPW_DIR.glob("**/*.epw"))
    for path in epw_files:
        try:
            location = parse_location(first_line(path))
            if not location:
                skipped.append((path.relative_to(REPO_ROOT), "Missing or invalid LOCATION line"))
                continue
            old = existing.get(path.name)
            entries.append(build_entry(path, location, old))
        except Exception as exc:
            skipped.append((path.relative_to(REPO_ROOT), str(exc)))

    entries.sort(key=lambda item: (item.get("country", ""), item.get("city", ""), item.get("station", "")))
    INDEX_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    INVENTORY_PATH.write_text(inventory_markdown(entries, skipped), encoding="utf-8")

    countries = sorted({e.get("country", "") for e in entries if e.get("country")})
    cities = sorted({e.get("city", "") for e in entries if e.get("city")})
    print(f"Scanned EPW files: {len(epw_files)}")
    print(f"Generated index records: {len(entries)}")
    print(f"Skipped invalid files: {len(skipped)}")
    print(f"Countries: {', '.join(countries) if countries else 'N/A'}")
    print(f"Cities: {', '.join(cities) if cities else 'N/A'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
