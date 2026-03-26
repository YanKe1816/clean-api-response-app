#!/usr/bin/env python3

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

APP_NAME = "clean-api-response-app"
APP_VERSION = "1.0.0"
SUPPORT_EMAIL = "sidcraigau@gmail.com"
CHALLENGE_TOKEN = os.environ.get("OPENAI_APPS_CHALLENGE", "clean-api-response-app-token")

TOOL_NAME = "clean_api_response"
TOOL_DESCRIPTION = (
    "Clean API response by removing null, empty, and unnecessary fields."
)


# ========= 核心逻辑 =========

def is_empty(value):
    return value is None or value == "" or value == {} or value == []


def clean_value(value):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            cleaned, keep = clean_value(v)
            if keep:
                out[k] = cleaned
        return out, not is_empty(out)

    if isinstance(value, list):
        out = []
        for item in value:
            cleaned, keep = clean_value(item)
            if keep:
                out.append(cleaned)
        return out, not is_empty(out)

    if is_empty(value):
        return value, False

    return value, True


def run_tool(input_json_string):
    try:
        data = json.loads(input_json_string)
    except Exception:
        return {"error": "Invalid JSON input"}

    cleaned, _ = clean_value(data)
    return cleaned


def manifest_tool():
    return {
        "tools": [
            {
                "name": TOOL_NAME,
                "description": TOOL_DESCRIPTION,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "json": {"type": "string"}
                    },
                    "required": ["json"]
                }
            }
        ]
    }


# ========= HTTP Handler =========

class Handler(BaseHTTPRequestHandler):

    def _send_json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return

        if self.path == "/privacy":
            self._send_json({"message": "No data stored"})
            return

        if self.path == "/terms":
            self._send_json({"message": "Use at your own risk"})
            return

        if self.path == "/support":
            self._send_json({"email": SUPPORT_EMAIL})
            return

        if self.path == "/.well-known/openai-apps-challenge":
            self._send_json({"challenge": CHALLENGE_TOKEN})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            request = json.loads(body)
        except Exception:
            self._send_json({"error": "Invalid JSON"})
            return

        method = request.get("method")
        request_id = request.get("id")

        # tools/list
        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": manifest_tool()
            }
            self._send_json(response)
            return

        # tools/call
        if method == "tools/call":
            params = request.get("params", {})
            arguments = params.get("arguments", {})
            json_input = arguments.get("json", "")

            result = run_tool(json_input)

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            self._send_json(response)
            return

        # fallback
        self._send_json({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found"}
        })


# ========= 启动 =========

def run():
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
