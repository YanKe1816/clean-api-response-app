#!/usr/bin/env python3
"""clean-api-response-app: deterministic MCP-style task app."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

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

app = FastAPI()


def _is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def clean_value(value: Any) -> Tuple[Any, bool]:
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
