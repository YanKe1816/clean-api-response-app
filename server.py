#!/usr/bin/env python3
"""clean-api-response-app: deterministic MCP-style task app."""

from __future__ import annotations

import json
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple

APP_NAME = "clean-api-response-app"
APP_VERSION = "1.0.0"
SUPPORT_EMAIL = "your@email.com"
CHALLENGE_TOKEN = "clean-api-response-app-token"

TOOL_NAME = "Clean API Response for Use"
TOOL_DESCRIPTION = (
    "Use this when API response data contains null, empty, or unnecessary "
    "fields and needs to be cleaned into usable JSON."
)

INVALID_INPUT = {
    "error": {
        "code": "INVALID_INPUT",
        "message": "Invalid or missing data field",
    }
}


def _is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def clean_value(value: Any) -> Tuple[Any, bool]:
    """Recursively remove null/empty values from JSON-like structures.

    Returns (cleaned_value, keep_flag) where keep_flag determines whether the
    cleaned_value should remain in the parent structure.
    """
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, child in value.items():
            cleaned_child, keep = clean_value(child)
            if keep:
                cleaned[key] = cleaned_child
        return cleaned, not _is_empty_value(cleaned)

    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item, keep = clean_value(item)
            if keep:
                cleaned_list.append(cleaned_item)
        return cleaned_list, not _is_empty_value(cleaned_list)

    if _is_empty_value(value):
        return value, False

    return value, True


def handle_tool_call(arguments: Any) -> Dict[str, Any]:
    if not isinstance(arguments, dict) or "data" not in arguments:
        return INVALID_INPUT

    before = arguments["data"]
    after, keep = clean_value(before)
    if not keep:
        after = {} if isinstance(before, dict) else [] if isinstance(before, list) else before

    return {
        "structuredContent": {
            "before": deepcopy(before),
            "after": after,
        }
    }


def manifest() -> Dict[str, Any]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "tools": [
            {
                "name": TOOL_NAME,
                "description": TOOL_DESCRIPTION,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"}
                    },
                    "required": ["data"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                },
            }
        ],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "CleanAPIResponseApp/1.0"

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Optional[Dict[str, Any]]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if self.path == "/privacy":
            self._send_text(200, "no data stored")
            return

        if self.path == "/terms":
            self._send_text(200, "Use only with valid JSON input containing a data field.")
            return

        if self.path == "/support":
            self._send_text(200, SUPPORT_EMAIL)
            return

        if self.path == "/.well-known/openai-apps-challenge":
            self._send_text(200, CHALLENGE_TOKEN)
            return

        if self.path == "/mcp":
            self._send_json(200, manifest())
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send_json(404, {"error": "not found"})
            return

        request = self._read_json()
        if request is None:
            self._send_json(400, INVALID_INPUT)
            return

        method = request.get("method")
        request_id = request.get("id")

        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": manifest()["tools"],
                },
            }
            self._send_json(200, response)
            return

        if method == "tools/call":
            params = request.get("params")
            if not isinstance(params, dict):
                result = INVALID_INPUT
            else:
                name = params.get("name")
                arguments = params.get("arguments")
                if name != TOOL_NAME:
                    result = INVALID_INPUT
                else:
                    result = handle_tool_call(arguments)

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
            self._send_json(200, response)
            return

        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": INVALID_INPUT,
        }
        self._send_json(200, response)


def run() -> None:
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    server.serve_forever()


if __name__ == "__main__":
    run()
