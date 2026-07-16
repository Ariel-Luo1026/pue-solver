#!/usr/bin/env python3
"""Local EPW fetch API server for the PUE Solver UI.

Runs a development-only HTTP API on 127.0.0.1:8011 and calls
tools.fetch_epw_online directly to geocode, download, cache, and index EPW files.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
PUE_SOLVER_DIR = TOOLS_DIR.parent / "pue-solver-main"
if str(PUE_SOLVER_DIR) not in sys.path:
    sys.path.insert(0, str(PUE_SOLVER_DIR))

from fetch_epw_online import FetchEpwError, FetchEpwWarning, fetch_epw_for_coordinates  # noqa: E402
from ashrae_proxy import query_ashrae_design_condition  # noqa: E402


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8011


class EpwApiHandler(BaseHTTPRequestHandler):
    server_version = "PueEpwApi/0.1"

    def log_message(self, format: str, *args) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _set_headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _write_json(self, payload: dict, status: int = 200) -> None:
        self._set_headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json({"ok": True, "service": "PUE Local API Server"})
            return
        if self.path.startswith("/api/ashrae_design_condition"):
            self._handle_ashrae_lookup_from_query()
            return
        self._write_json({"success": False, "message": "Not found."}, 404)

    def do_POST(self) -> None:
        if self.path == "/api/ashrae_design_condition":
            self._handle_ashrae_lookup_from_body()
            return
        if self.path != "/api/fetch_epw":
            self._write_json({"success": False, "message": "Not found."}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception:
            self._write_json({"success": False, "message": "Invalid JSON request."}, 400)
            return

        location = str(payload.get("location") or "").strip()
        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        if latitude is None or longitude is None:
            self._write_json({
                "success": False,
                "query_location": location,
                "message": "Latitude and Longitude are required for EPW matching.",
            }, 200)
            return
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            self._write_json({
                "success": False,
                "query_location": location,
                "message": "Latitude and Longitude are required for EPW matching.",
            }, 200)
            return

        try:
            result = fetch_epw_for_coordinates(latitude, longitude, query_location=location)
        except FetchEpwWarning as exc:
            details = dict(exc.details)
            details.update({
                "success": False,
                "query_location": details.get("query_location") or location,
                "message": str(exc),
            })
            self._write_json(details, 200)
            return
        except FetchEpwError as exc:
            self._write_json({
                "success": False,
                "query_location": location,
                "message": str(exc),
                "error_code": exc.code,
            }, 200)
            return
        except Exception as exc:
            self._write_json({
                "success": False,
                "query_location": location,
                "message": f"EPW fetch failed: {exc}",
            }, 500)
            return

        self._write_json({
            "success": True,
            "query_location": result.get("query_location", location),
            "project_latitude": result.get("project_latitude"),
            "project_longitude": result.get("project_longitude"),
            "matched_station": result.get("matched_station", ""),
            "distance_km": result.get("distance_km"),
            "confidence": result.get("confidence", ""),
            "source": result.get("source", "Climate.OneBuilding"),
            "epw_file": result.get("epw_file", ""),
            "already_cached": bool(result.get("already_cached")),
            "message": "EPW already cached." if result.get("already_cached") else "EPW downloaded and cached.",
        })

    def _handle_ashrae_lookup_from_query(self) -> None:
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(self.path).query)
        payload = {
            "latitude": _first_query_value(query, "latitude", "lat"),
            "longitude": _first_query_value(query, "longitude", "lon", "lng", "long"),
        }
        self._handle_ashrae_lookup(payload)

    def _handle_ashrae_lookup_from_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception:
            self._write_json({
                "success": False,
                "lookup_status": "failed",
                "online_status": "failed",
                "failure_reason": "Invalid JSON request.",
                "fallback_status": "manual_override_required",
            }, 400)
            return
        self._handle_ashrae_lookup(payload)

    def _handle_ashrae_lookup(self, payload: dict) -> None:
        latitude = payload.get("latitude", payload.get("lat"))
        longitude = payload.get("longitude", payload.get("lon", payload.get("lng", payload.get("long"))))
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            self._write_json({
                "success": False,
                "lookup_status": "failed",
                "online_status": "failed",
                "failure_reason": "Latitude and Longitude are required for ASHRAE lookup.",
                "fallback_status": "manual_override_required",
                "source": "ASHRAE_online_proxy",
            }, 200)
            return

        result = query_ashrae_design_condition(latitude, longitude)
        result = dict(result or {})
        result["success"] = result.get("lookup_status") == "success"
        self._write_json(result, 200)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local EPW fetch API server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), EpwApiHandler)
    print("EPW API Server running at:")
    print(f"http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EPW API Server.")
    finally:
        server.server_close()
    return 0


def _first_query_value(query: dict, *keys: str):
    for key in keys:
        values = query.get(key)
        if values:
            return values[0]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
