#!/usr/bin/env python3
"""clean-api-response-app: deterministic MCP-style task app."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Awaitable, Callable, Dict, List, Tuple

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

HandlerFn = Callable[..., Any]


class JSONResponse:
    def __init__(self, content: Dict[str, Any], status_code: int = 200):
        self.content = content
        self.status_code = status_code

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Awaitable[Dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        body = json.dumps(self.content, separators=(",", ":")).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [[b"content-type", b"application/json"], [b"content-length", str(len(body)).encode("ascii")]],
            }
        )
        await send({"type": "http.response.body", "body": body})


class PlainTextResponse:
    def __init__(self, content: str, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Awaitable[Dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        body = self.content.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [[b"content-type", b"text/plain; charset=utf-8"], [b"content-length", str(len(body)).encode("ascii")]],
            }
        )
        await send({"type": "http.response.body", "body": body})


class Request:
    def __init__(self, scope: Dict[str, Any], receive: Callable[..., Awaitable[Dict[str, Any]]]):
        self.scope = scope
        self._receive = receive

    async def json(self) -> Any:
        chunks: List[bytes] = []
        while True:
            message = await self._receive()
            if message["type"] != "http.request":
                continue
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        raw = b"".join(chunks)
        return json.loads(raw.decode("utf-8"))


class FastAPI:
    def __init__(self):
        self.routes: Dict[Tuple[str, str], HandlerFn] = {}

    def get(self, path: str) -> Callable[[HandlerFn], HandlerFn]:
        def decorator(fn: HandlerFn) -> HandlerFn:
            self.routes[("GET", path)] = fn
            return fn

        return decorator

    def post(self, path: str) -> Callable[[HandlerFn], HandlerFn]:
        def decorator(fn: HandlerFn) -> HandlerFn:
            self.routes[("POST", path)] = fn
            return fn

        return decorator

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Awaitable[Dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        if scope.get("type") != "http":
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        handler = self.routes.get((method, path))
        if handler is None:
            response = JSONResponse({"error": "not found"}, status_code=404)
            await response(scope, receive, send)
            return

        if method == "POST":
            result = handler(Request(scope, receive))
        else:
            result = handler()

        if hasattr(result, "__await__"):
            result = await result

        if isinstance(result, (JSONResponse, PlainTextResponse)):
            response = result
        elif isinstance(result, str):
            response = PlainTextResponse(result)
        else:
            response = JSONResponse(result)

        await response(scope, receive, send)


app = FastAPI()


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


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/privacy")
def privacy() -> PlainTextResponse:
    return PlainTextResponse("no data stored")


@app.get("/terms")
def terms() -> PlainTextResponse:
    return PlainTextResponse("Use only with valid JSON input containing a data field.")


@app.get("/support")
def support() -> PlainTextResponse:
    return PlainTextResponse(SUPPORT_EMAIL)


@app.get("/.well-known/openai-apps-challenge")
def challenge() -> PlainTextResponse:
    return PlainTextResponse(CHALLENGE_TOKEN)


@app.get("/mcp")
def get_mcp() -> Dict[str, Any]:
    return manifest()


@app.post("/mcp")
async def post_mcp(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=INVALID_INPUT)

    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content=INVALID_INPUT)

    method = payload.get("method")
    request_id = payload.get("id")

    if method == "tools/list":
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": manifest()["tools"]},
            }
        )

    if method == "tools/call":
        params = payload.get("params")
        if not isinstance(params, dict):
            result = INVALID_INPUT
        else:
            name = params.get("name")
            arguments = params.get("arguments")
            result = handle_tool_call(arguments) if name == TOOL_NAME else INVALID_INPUT

        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        )

    return JSONResponse(
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "result": INVALID_INPUT,
        }
    )
