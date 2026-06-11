#!/usr/bin/env python3
"""Fetch and cache a nearby EPW file for the local PUE Solver UI.

Prototype Phase 3A flow:
  Location -> geocode -> Climate.OneBuilding station match -> download ZIP/EPW
  -> cache under pue-solver-main/data/epw/ -> rebuild epw_index.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "pue-solver-main"
EPW_DIR = UI_ROOT / "data" / "epw"
DOWNLOAD_LOG_PATH = UI_ROOT / "data" / "epw_download_log.json"
GEOCODE_CACHE_PATH = UI_ROOT / "data" / "epw_geocode_cache.json"
MASTER_INDEX_PATH = UI_ROOT / "data" / "epw_master_index.json"
LOCAL_INDEX_PATH = UI_ROOT / "data" / "epw_index.json"
BUILD_INDEX_SCRIPT = REPO_ROOT / "tools" / "build_epw_index.py"

USER_AGENT = "pue-solver-epw-fetcher/0.1 (local prototype; contact: local-user)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MAX_REPRESENTATIVE_DISTANCE_KM = 500.0

COUNTRY_ALIASES = {
    "中国": "China",
    "中华人民共和国": "China",
    "People's Republic of China": "China",
    "PRC": "China",
    "日本": "Japan",
    "日本国": "Japan",
    "新加坡": "Singapore",
    "新加坡共和国": "Singapore",
    "Deutschland": "Germany",
    "Deutschland Bundesrepublik": "Germany",
    "France métropolitaine": "France",
    "Éire / Ireland": "Ireland",
    "UK": "United Kingdom",
    "المملكة المتحدة": "United Kingdom",
    "United States of America": "United States",
    "USA": "United States",
    "UAE": "United Arab Emirates",
    "الإمارات العربية المتحدة": "United Arab Emirates",
    "भारत": "India",
    "भारत गणराज्य": "India",
}

RECENT_PERIOD_WEIGHTS = (
    ("2011-2025", 60),
    ("2009-2023", 50),
    ("2007-2021", 40),
    ("2004-2018", 30),
    ("TMYx.zip", 20),
    ("TMYx", 10),
    ("CSWD", 0),
)


class FetchEpwError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class FetchEpwWarning(Exception):
    def __init__(self, code: str, message: str, details: dict):
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass
class Candidate:
    filename: str
    url: str
    station: str
    country: str
    city: str = ""
    score: int = 0
    lat: float | None = None
    lon: float | None = None
    distance_km: float | None = None
    confidence: str = "low"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except Exception as exc:
        raise FetchEpwError("download failed", f"download failed: {url} ({exc})") from exc


def normalize_text(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def station_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.split("_")
    body = "_".join(parts[2:]) if len(parts) >= 3 else stem
    body = body.split("_TMY")[0].split("_CSWD")[0]
    body = body.replace(".Intl.AP", " Intl AP")
    body = body.replace(".AP", " AP")
    body = body.replace(".", " ").replace("-", " ")
    body = " ".join(piece for piece in body.split() if not piece.isdigit())
    return body.strip() or stem


def filename_from_url(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).name


def period_score(filename: str) -> int:
    for token, score in RECENT_PERIOD_WEIGHTS:
        if token.lower() in filename.lower():
            return score
    return 0


def geocode(location: str) -> dict:
    cache = load_json(GEOCODE_CACHE_PATH, {})
    cache_key = normalize_text(location)
    if cache_key in cache:
        return cache[cache_key]

    params = {
        "q": location,
        "format": "jsonv2",
        "limit": "1",
        "addressdetails": "1",
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    time.sleep(1.1)
    data = http_get(url, timeout=30)
    try:
        results = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise FetchEpwError("geocode failed", f"geocode failed: invalid response for {location}") from exc
    if not results:
        raise FetchEpwError("geocode failed", f"geocode failed: {location}")

    first = results[0]
    address = first.get("address", {}) if isinstance(first, dict) else {}
    country = COUNTRY_ALIASES.get(address.get("country", ""), address.get("country", ""))
    item = {
        "query": location,
        "display_name": first.get("display_name", ""),
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
        "country": country,
    }
    cache[cache_key] = item
    write_json(GEOCODE_CACHE_PATH, cache)
    return item


def load_master_candidates() -> list[Candidate]:
    data = load_json(MASTER_INDEX_PATH, [])
    if not isinstance(data, list) or not data:
        raise FetchEpwError(
            "no EPW station found",
            f"no EPW station found: missing {MASTER_INDEX_PATH}. Run python tools/build_online_epw_master_index.py first.",
        )
    candidates = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("download_url") or "")
        lat = item.get("lat")
        lon = item.get("lon")
        if not url or lat is None or lon is None:
            continue
        try:
            lat_num = float(lat)
            lon_num = float(lon)
        except (TypeError, ValueError):
            continue
        filename = filename_from_url(url)
        candidates.append(
            Candidate(
                filename=filename,
                url=url,
                station=str(item.get("station") or station_from_filename(filename)),
                country=str(item.get("country") or ""),
                city=str(item.get("city") or ""),
                lat=lat_num,
                lon=lon_num,
            )
        )
    if not candidates:
        raise FetchEpwError("no EPW station found", "no EPW station found: master index has no usable stations.")
    return candidates


def score_name_match(query: str, candidate: Candidate) -> int:
    q = normalize_text(query)
    station = normalize_text(candidate.station)
    city = normalize_text(candidate.city)
    filename = normalize_text(candidate.filename)
    score = period_score(candidate.filename)
    if q and (q == station or q == city):
        score += 120
    elif q and (q in station or station in q or q in city or city in q):
        score += 100
    elif q and q in filename:
        score += 90
    return score


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def confidence_for(distance_km: float | None, exact_name: bool) -> str:
    if exact_name:
        return "high"
    if distance_km is None:
        return "low"
    if distance_km <= 75:
        return "high"
    if distance_km <= 250:
        return "medium"
    return "low"


def choose_candidate(query: str, query_geo: dict, candidates: list[Candidate]) -> Candidate:
    for candidate in candidates:
        candidate.score = score_name_match(query, candidate)
        candidate.distance_km = haversine_km(query_geo["lat"], query_geo["lon"], candidate.lat, candidate.lon)
        candidate.confidence = confidence_for(candidate.distance_km, exact_name=candidate.score >= 100)
    return sorted(
        candidates,
        key=lambda c: (
            c.distance_km if c.distance_km is not None else 999999,
            -c.score,
            -period_score(c.filename),
        ),
    )[0]


def parse_epw_location(epw_path: Path) -> dict:
    try:
        first = epw_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except Exception as exc:
        raise FetchEpwError("EPW parse failed", f"EPW parse failed: cannot read {epw_path.name}") from exc
    row = next(csv.reader([first]))
    if len(row) < 10 or row[0].strip().upper() != "LOCATION":
        raise FetchEpwError("EPW parse failed", f"EPW parse failed: missing LOCATION line in {epw_path.name}")
    data_rows = max(0, sum(1 for _ in epw_path.open("r", encoding="utf-8", errors="replace")) - 8)
    if data_rows < 8760:
        raise FetchEpwError("EPW parse failed", f"EPW parse failed: expected at least 8760 hourly rows, found {data_rows}")
    return {
        "station": row[1].strip(),
        "country": row[3].strip(),
        "lat": row[6].strip(),
        "lon": row[7].strip(),
        "hourly_rows": data_rows,
    }


def cached_epw_path(candidate: Candidate) -> Path:
    name = Path(candidate.filename).with_suffix(".epw").name if candidate.filename.lower().endswith(".zip") else candidate.filename
    return EPW_DIR / name


def download_and_cache(candidate: Candidate) -> tuple[Path, bool]:
    EPW_DIR.mkdir(parents=True, exist_ok=True)
    target = cached_epw_path(candidate)
    if target.exists():
        parse_epw_location(target)
        return target, True

    payload = http_get(candidate.url)
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        download_path = tmp_path / candidate.filename
        download_path.write_bytes(payload)
        if candidate.filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(download_path) as archive:
                    epw_members = [m for m in archive.namelist() if m.lower().endswith(".epw")]
                    if not epw_members:
                        raise FetchEpwError("zip extract failed", "zip extract failed: no .epw file in archive")
                    archive.extract(epw_members[0], tmp_path)
                    extracted = tmp_path / epw_members[0]
            except FetchEpwError:
                raise
            except Exception as exc:
                raise FetchEpwError("zip extract failed", f"zip extract failed: {candidate.filename} ({exc})") from exc
        elif candidate.filename.lower().endswith(".epw"):
            extracted = download_path
        else:
            raise FetchEpwError("download failed", f"download failed: unsupported file type {candidate.filename}")

        parse_epw_location(extracted)
        shutil.copyfile(extracted, target)
    return target, False


def run_build_index() -> None:
    try:
        subprocess.run([sys.executable, str(BUILD_INDEX_SCRIPT)], cwd=REPO_ROOT, check=True)
    except Exception as exc:
        raise FetchEpwError("index update failed", f"index update failed: {exc}") from exc


def append_download_log(entry: dict) -> None:
    existing = load_json(DOWNLOAD_LOG_PATH, [])
    if isinstance(existing, dict):
        existing = [existing]
    if not isinstance(existing, list):
        existing = []
    existing.append(entry)
    write_json(DOWNLOAD_LOG_PATH, existing)


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


def add_aliases_to_local_index(epw_file: str, aliases: list[str]) -> None:
    index = load_json(LOCAL_INDEX_PATH, [])
    if not isinstance(index, list):
        return
    changed = False
    for item in index:
        if not isinstance(item, dict):
            continue
        item_file = item.get("epw_file") or Path(str(item.get("epw_path", ""))).name
        if item_file != epw_file:
            continue
        existing_aliases = item.get("aliases", [])
        if not isinstance(existing_aliases, list):
            existing_aliases = []
        merged = unique_keep_order(existing_aliases + aliases)
        if merged != existing_aliases:
            item["aliases"] = merged
            changed = True
    if changed:
        write_json(LOCAL_INDEX_PATH, index)


def fetch_epw(location: str) -> dict:
    query_geo = geocode(location)
    candidates = load_master_candidates()
    candidate = choose_candidate(location, query_geo, candidates)
    if candidate.distance_km is not None and candidate.distance_km > MAX_REPRESENTATIVE_DISTANCE_KM:
        raise FetchEpwWarning(
            "no suitable EPW station found",
            f"No suitable EPW station found within {int(MAX_REPRESENTATIVE_DISTANCE_KM)} km.",
            {
                "query_location": location,
                "nearest_station": candidate.station,
                "distance_km": round(candidate.distance_km, 1),
                "source": "Climate.OneBuilding",
            },
        )
    epw_path, already_cached = download_and_cache(candidate)
    epw_meta = parse_epw_location(epw_path)
    if candidate.distance_km is None and epw_meta.get("lat") and epw_meta.get("lon"):
        try:
            candidate.distance_km = haversine_km(query_geo["lat"], query_geo["lon"], float(epw_meta["lat"]), float(epw_meta["lon"]))
        except Exception:
            candidate.distance_km = None
    candidate.confidence = confidence_for(candidate.distance_km, normalize_text(location) in normalize_text(candidate.station))

    log_entry = {
        "query_location": location,
        "matched_station": epw_meta.get("station") or candidate.station,
        "distance_km": round(candidate.distance_km, 1) if candidate.distance_km is not None else None,
        "source": "Climate.OneBuilding",
        "download_url": candidate.url,
        "epw_file": epw_path.name,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "confidence": candidate.confidence,
        "already_cached": already_cached,
        "master_index_records": len(candidates),
    }
    run_build_index()
    add_aliases_to_local_index(
        epw_path.name,
        [
            location,
            log_entry["matched_station"],
            candidate.station,
            candidate.city,
            epw_meta.get("station", ""),
        ],
    )
    append_download_log(log_entry)
    return log_entry


def fetch_epw_for_location(location: str) -> dict:
    """Import-friendly API used by the local EPW HTTP server."""
    return fetch_epw(location)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a nearby EPW file and rebuild the local EPW index.")
    parser.add_argument("location", help='Location query, e.g. "Shanghai"')
    args = parser.parse_args(argv)

    try:
        result = fetch_epw_for_location(args.location)
    except FetchEpwWarning as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps(exc.details, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except FetchEpwError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        print("Please upload EPW manually.", file=sys.stderr)
        return 1

    if result.get("already_cached"):
        print("EPW already cached.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("distance_km") is not None and result["distance_km"] > 250:
        print("Warning: matched EPW station is far from the requested location; please confirm before using it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
