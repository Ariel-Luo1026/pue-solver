#!/usr/bin/env python3
"""Build a local master index of online EPW stations.

Scans common Climate.OneBuilding WMO regions, collects country-page EPW links,
merges station coordinates from the region KML files, and writes:

  pue-solver-main/data/epw_master_index.json
"""

from __future__ import annotations

import argparse
import html.parser
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "pue-solver-main"
MASTER_INDEX_PATH = UI_ROOT / "data" / "epw_master_index.json"

USER_AGENT = "pue-solver-epw-master-index/0.1 (local prototype; contact: local-user)"
SOURCE_NAME = "Climate.OneBuilding"

COUNTRY_NAME_ALIASES = {
    "United States of America": "United States",
    "USA": "United States",
}

REGION_URLS = [
    "https://climate.onebuilding.org/WMO_Region_1_Africa/default.html",
    "https://climate.onebuilding.org/WMO_Region_2_Asia/default.html",
    "https://climate.onebuilding.org/WMO_Region_3_South_America/default.html",
    "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/default.html",
    "https://climate.onebuilding.org/WMO_Region_6_Europe/default.html",
    "https://climate.onebuilding.org/WMO_Region_5_Southwest_Pacific/default.html",
]

RECENT_PERIOD_WEIGHTS = (
    ("2011-2025", 60),
    ("2009-2023", 50),
    ("2007-2021", 40),
    ("2004-2018", 30),
    ("TMYx.zip", 20),
    ("TMYx", 10),
    ("CSWD", 0),
)


@dataclass
class LinkRecord:
    download_url: str
    country: str
    city: str
    station: str
    lat: float | None = None
    lon: float | None = None


class LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value.strip())


def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def page_links(url: str) -> list[str]:
    html = http_get(url).decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    return [urllib.parse.urljoin(url, href) for href in parser.links]


def clean_token(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("_", " ").replace(".", " ").strip())
    return text.replace(" - ", "-")


def normalize_country_name(value: str) -> str:
    country = clean_token(value)
    return COUNTRY_NAME_ALIASES.get(country, country)


def country_code_from_filename(url: str) -> str:
    stem = Path(filename_from_url(url)).stem
    first = stem.split("_", 1)[0]
    return first if re.match(r"^[A-Z]{3}$", first) else ""


def country_from_path(url: str, code_to_country: dict[str, str] | None = None) -> str:
    parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    for part in parts:
        if part.lower().endswith((".zip", ".epw")):
            continue
        if part.startswith("WMO_"):
            continue
        if re.match(r"^[A-Z]{3}_.+", part):
            return normalize_country_name(part[4:])
    code = country_code_from_filename(url)
    if code and code_to_country:
        return code_to_country.get(code, "")
    return ""


def filename_from_url(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).name


def parse_filename(url: str) -> tuple[str, str]:
    stem = Path(filename_from_url(url)).stem
    parts = stem.split("_")
    body = "_".join(parts[2:]) if len(parts) >= 3 else stem
    body = re.split(r"_TMY|_CSWD|_IWEC", body, maxsplit=1)[0]
    body = re.sub(r"\.[0-9]{5,6}.*$", "", body)
    station = clean_token(body)
    city = station
    for suffix in [" Intl AP", " AP", " Airport", " Meteo", " Observatory"]:
        city = city.replace(suffix, "")
    city = city.split("-")[0].strip() or station
    return city, station


def period_score(url: str) -> int:
    name = filename_from_url(url)
    for token, score in RECENT_PERIOD_WEIGHTS:
        if token.lower() in name.lower():
            return score
    return 0


def is_country_page(url: str, region_url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc != urllib.parse.urlparse(region_url).netloc:
        return False
    path = parsed.path
    if not path.endswith("/index.html"):
        return False
    return bool(re.search(r"/[A-Z]{3}_[^/]+/index\.html$", path))


def is_download_url(url: str) -> bool:
    return urllib.parse.urlparse(url).path.lower().endswith((".zip", ".epw"))


def is_kml_url(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(".kml") and "epw_processing_locations" in path


def collect_country_links(region_url: str) -> list[str]:
    return sorted({url for url in page_links(region_url) if is_country_page(url, region_url)})


def collect_region_kml_links(region_url: str) -> list[str]:
    return sorted({url for url in page_links(region_url) if is_kml_url(url)})


def collect_country_downloads(country_url: str) -> list[LinkRecord]:
    country = country_from_path(country_url)
    records = []
    for url in page_links(country_url):
        if not is_download_url(url):
            continue
        city, station = parse_filename(url)
        records.append(LinkRecord(download_url=url, country=country, city=city, station=station))
    return records


def parse_kml_records(kml_url: str, code_to_country: dict[str, str]) -> list[LinkRecord]:
    text = http_get(kml_url).decode("utf-8", errors="replace")
    placemarks = re.findall(r"<Placemark\b[^>]*>(.*?)</Placemark>", text, flags=re.IGNORECASE | re.DOTALL)
    records = []
    for placemark in placemarks:
        match = re.search(r"URL\s+(https?://[^\s<]+?\.(?:zip|epw))", placemark, re.IGNORECASE)
        if not match:
            continue
        url = match.group(1)
        coords_match = re.search(r"<coordinates>\s*([^<]+?)\s*</coordinates>", placemark, flags=re.IGNORECASE | re.DOTALL)
        coords_text = coords_match.group(1).strip() if coords_match else ""
        coords_parts = [p.strip() for p in coords_text.split(",")]
        if len(coords_parts) < 2:
            continue
        try:
            lon = float(coords_parts[0])
            lat = float(coords_parts[1])
        except ValueError:
            continue
        city, station = parse_filename(url)
        name_match = re.search(r"<name>\s*([^<]+?)\s*</name>", placemark, flags=re.IGNORECASE | re.DOTALL)
        if name_match:
            station = clean_token(name_match.group(1))
        records.append(LinkRecord(download_url=url, country=country_from_path(url, code_to_country), city=city, station=station, lat=lat, lon=lon))
    return records


def choose_better(existing: dict, candidate: dict) -> dict:
    if existing.get("lat") is None and candidate.get("lat") is not None:
        return candidate
    if period_score(candidate["download_url"]) > period_score(existing["download_url"]):
        return {**existing, **candidate}
    return existing


def build_master_index() -> list[dict]:
    by_url: dict[str, dict] = {}
    country_pages = []
    kml_links = []

    for region_url in REGION_URLS:
        country_pages.extend(collect_country_links(region_url))
        kml_links.extend(collect_region_kml_links(region_url))

    code_to_country = {}
    for country_url in sorted(set(country_pages)):
        path_parts = [p for p in urllib.parse.urlparse(country_url).path.split("/") if p]
        for part in path_parts:
            match = re.match(r"^([A-Z]{3})_(.+)$", part)
            if match:
                code_to_country[match.group(1)] = normalize_country_name(match.group(2))

    for country_url in sorted(set(country_pages)):
        for record in collect_country_downloads(country_url):
            item = {
                "country": record.country,
                "city": record.city,
                "station": record.station,
                "lat": record.lat,
                "lon": record.lon,
                "download_url": record.download_url,
                "source": SOURCE_NAME,
            }
            existing = by_url.get(record.download_url)
            by_url[record.download_url] = choose_better(existing, item) if existing else item

    for kml_url in sorted(set(kml_links)):
        for record in parse_kml_records(kml_url, code_to_country):
            item = {
                "country": record.country,
                "city": record.city,
                "station": record.station,
                "lat": record.lat,
                "lon": record.lon,
                "download_url": record.download_url,
                "source": SOURCE_NAME,
            }
            existing = by_url.get(record.download_url)
            by_url[record.download_url] = choose_better(existing, item) if existing else item

    rows = [item for item in by_url.values() if item.get("lat") is not None and item.get("lon") is not None]
    rows.sort(key=lambda item: (item.get("country") or "", item.get("city") or "", item.get("station") or "", item.get("download_url") or ""))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Climate.OneBuilding EPW master index.")
    parser.parse_args(argv)

    rows = build_master_index()
    MASTER_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_INDEX_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    countries = sorted({item["country"] for item in rows if item.get("country")})
    cities = sorted({item["city"] for item in rows if item.get("city")})
    print(f"Generated master EPW records: {len(rows)}")
    print(f"Covered countries: {len(countries)}")
    print(f"Supported cities/station-city names: {len(cities)}")
    print(f"Output: {MASTER_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
