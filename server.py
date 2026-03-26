import json
from http.server import BaseHTTPRequestHandler, HTTPServer

APP_NAME = "clean-api-response-app"
APP_VERSION = "1.0.0"
TOOL_NAME = "clean_api_response"
TOOL_DESCRIPTION = "Use this tool when API response data contains null, empty, or unnecessary fields, and needs to be cleaned into usable JSON."
CHALLENGE_TOKEN = "clean-api-response-app-token"


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
    if not isinstance(input_json_string, str):
        return {"error": "Invalid JSON input"}
    try:
        data = json.loads(input_json_string)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON input"}
    cleaned, keep = clean_value(data)
    if not keep:
        cleaned = {} if isinstance(data, dict) else [] if isinstance(data, list) else data
    return {"content": [], "structuredContent": {"output": cleaned}}


def manifest_tool():
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"],
            "additionalProperties": False
        }
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def do_GET(self):
        if self.path == "/health":
            self.send_json({"status": "ok"})
            return
        if self.path == "/privacy":
            self.send_text("Privacy Policy\n\nWe do not store your submitted API payloads. Requests are processed in-memory and returned immediately. No analytics identifiers or tracking data are persisted by this service.")
            return
        if self.path == "/terms":
            self.send_text("Terms of Use\n\nThis service cleans valid JSON input by removing null and empty values. You are responsible for the data you submit and for validating the cleaned output before production use.")
            return
        if self.path == "/support":
            self.send_text("Support\n\nFor help with clean-api-response-app, contact support@clean-api-response-app.local. Include request time, endpoint, and payload shape (without sensitive values).")
            return
        if self.path == "/.well-known/openai-apps-challenge":
            self.send_text(CHALLENGE_TOKEN)
            return
        self.send_json({"error": "not found"}, status=404)

    def do_POST(self):
        if self.path != "/mcp":
            self.send_json({"error": "not found"}, status=404)
            return
        req = self.read_json()
        if req is None:
            self.send_json({"error": "Invalid JSON input"}, status=400)
            return
        request_id = req.get("id")
        method = req.get("method")
        params = req.get("params")

        if method == "initialize":
            self.send_json({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": APP_NAME, "version": APP_VERSION}
                }
            })
            return

        if method == "notifications/initialized":
            self.send_json({"jsonrpc": "2.0", "id": request_id, "result": {}})
            return

        if method == "tools/list":
            self.send_json({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": [manifest_tool()]}
            })
            return

        if method == "tools/call":
            if not isinstance(params, dict):
                result = {"error": "Invalid JSON input"}
            else:
                name = params.get("name")
                arguments = params.get("arguments")
                if name != TOOL_NAME or not isinstance(arguments, dict):
                    result = {"error": "Invalid JSON input"}
                else:
                    result = run_tool(arguments.get("input"))
            self.send_json({"jsonrpc": "2.0", "id": request_id, "result": result})
            return

        if method == "ping":
            self.send_json({"jsonrpc": "2.0", "id": request_id, "result": {}})
            return

        self.send_json({"jsonrpc": "2.0", "id": request_id, "result": {"error": "Invalid JSON input"}})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
