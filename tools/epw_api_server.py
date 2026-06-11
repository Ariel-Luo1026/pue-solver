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

from fetch_epw_online import FetchEpwError, FetchEpwWarning, fetch_epw_for_location  # noqa: E402


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
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _write_json(self, payload: dict, status: int = 200) -> None:
        self._set_headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json({"ok": True, "service": "EPW API Server"})
            return
        self._write_json({"success": False, "message": "Not found."}, 404)

    def do_POST(self) -> None:
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
        if not location:
            self._write_json({"success": False, "message": "Missing location."}, 400)
            return

        try:
            result = fetch_epw_for_location(location)
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
            "matched_station": result.get("matched_station", ""),
            "distance_km": result.get("distance_km"),
            "confidence": result.get("confidence", ""),
            "source": result.get("source", "Climate.OneBuilding"),
            "epw_file": result.get("epw_file", ""),
            "already_cached": bool(result.get("already_cached")),
            "message": "EPW already cached." if result.get("already_cached") else "EPW downloaded and cached.",
        })


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


if __name__ == "__main__":
    raise SystemExit(main())
